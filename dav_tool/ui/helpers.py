import datetime
import os
import glob
import logging
import streamlit as st
import polars as pl
from dav_tool._parsers import (
    parse_fixed_width_chunks, preview_flattened_multiline,
    preview_flattened_multiline_fixed,
)
from dav_tool._observability import ProcessingRecord, MAX_HISTORY
from dav_tool.config import FALLBACK_ENCODING
from dav_tool.io import safe_read_csv

logger = logging.getLogger(__name__)


def display_execution_summary(metrics):
    st.divider()
    st.markdown("### Execution Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Files Processed", metrics.files_processed)
        st.metric("Rows Processed", f"{metrics.rows_processed:,}")
        st.metric("Unique Stores", f"{metrics.stores_processed:,}")
        st.metric("Unique UPCs", f"{metrics.upcs_processed:,}")
    with c2:
        st.metric("Parse Time", f"{metrics.parse_time:.2f}s")
        st.metric("Aggregation Time", f"{metrics.aggregation_time:.2f}s")
        st.metric("Validation Time", f"{metrics.validation_time:.2f}s")
        st.metric("Report Time", f"{metrics.report_time:.2f}s")
    with c3:
        st.metric("Total Time", f"{metrics.total_execution_time:.2f}s")
        st.metric("Peak Memory", f"{metrics.peak_memory:.1f} MB")
        st.metric("Peak CPU", f"{metrics.peak_cpu:.1f}%")
    if metrics.warnings:
        for w in metrics.warnings:
            st.caption(f":warning: {w}")
    if metrics.errors:
        for e in metrics.errors:
            st.caption(f":x: {e}")


def display_dev_diagnostics(ctx):
    st.sidebar.divider()
    st.sidebar.markdown("### Developer Diagnostics")
    m = ctx.metrics
    st.sidebar.markdown(f"**Phase:** {ctx.phase}")
    st.sidebar.markdown(f"**Parser Type:** {getattr(ctx, 'file_type', 'N/A')}")
    if hasattr(ctx, 'prod') and hasattr(ctx, 'test'):
        st.sidebar.markdown(f"**BAU Type:** {ctx.prod.file_type or '—'}")
        st.sidebar.markdown(f"**Test Type:** {ctx.test.file_type or '—'}")
    layout = getattr(ctx, 'layout', None) or getattr(ctx, 'schema', None)
    if layout:
        st.sidebar.markdown(f"**Schema/Columns:** {layout}")
    st.sidebar.markdown(f"**Current Memory:** {m.current_memory:.1f} MB")
    st.sidebar.markdown(f"**Peak Memory:** {m.peak_memory:.1f} MB")
    st.sidebar.markdown(f"**Current CPU:** {m.current_cpu:.1f}%")
    st.sidebar.markdown(f"**Chunks Processed:** {m.chunks_processed}")
    if hasattr(ctx, 'store_agg') and ctx.store_agg is not None and not ctx.store_agg.is_empty():
        st.sidebar.markdown(f"**Store Agg:** {len(ctx.store_agg)} rows")
    if hasattr(ctx, 'item_agg') and ctx.item_agg is not None and not ctx.item_agg.is_empty():
        st.sidebar.markdown(f"**Item Agg:** {len(ctx.item_agg)} rows")
    done = getattr(ctx, 'done', None) or getattr(ctx, 'validation_done', None)
    st.sidebar.markdown(f"**Validation Done:** {bool(done)}")


COLUMN_SYNONYMS = {
    "Store": [
        "store", "store number", "store_id", "store id",
        "store code", "store_code", "store_number", "store num",
        "location", "location code",
    ],
    "UPC": [
        "upc", "upc_code", "upc code", "item upc", "item_upc",
        "upc number", "upc_number", "barcode", "upc12", "gtin",
        "ean", "product code",
    ],
    "Description": [
        "description", "desc", "item description", "item_description",
        "product description", "product_description", "product name",
        "item name", "name", "description of goods",
    ],
    "Units": [
        "units", "qty", "quantity", "sold", "units sold",
        "units_sold", "quantity sold", "sales quantity", "qty sold",
        "unit sold", "sale quantity",
    ],
    "Price": [
        "price", "total price", "total_price", "sales", "amount",
        "dollars", "total dollars", "total_dollars", "revenue",
        "total revenue", "selling price", "sales amount",
        "sale price", "price sold",
    ],
}


def find_best_column_index(cols, target, synonyms):
    if not cols:
        return 0
    col_lower = [c.lower().strip() for c in cols]
    target_lower = target.lower()

    if target_lower in col_lower:
        return col_lower.index(target_lower)

    for syn in synonyms:
        syn_lower = syn.lower()
        if syn_lower in col_lower:
            return col_lower.index(syn_lower)

    for i, col in enumerate(col_lower):
        for syn in synonyms:
            syn_lower = syn.lower()
            if syn_lower in col or col in syn_lower:
                return i

    for i, col in enumerate(col_lower):
        if target_lower in col or col in target_lower:
            return i

    return 0


def smart_column_indices(cols):
    indices = {}
    for target, synonyms in COLUMN_SYNONYMS.items():
        idx = find_best_column_index(cols, target, synonyms)
        key = target.lower()
        if idx < len(cols):
            indices[key] = (idx, cols[idx])
        else:
            indices[key] = (0, cols[0] if cols else None)
    return indices


def validate_column_mapping(store_col, upc_col, desc_col, units_col, price_col):
    errors = []
    selected = [store_col, upc_col, desc_col, units_col, price_col]
    labels = ["Store", "UPC", "Description", "Units", "Price"]

    for label, val in zip(labels, selected):
        if not val:
            errors.append(f"{label} column is not selected.")

    seen = {}
    for label, val in zip(labels, selected):
        if val:
            if val in seen:
                errors.append(
                    f"Duplicate column: '{val}' is selected for both "
                    f"'{seen[val]}' and '{label}'. Each column must be unique."
                )
            seen[val] = label

    return errors


def clean_path(path):
    if not path:
        return path
    path = path.strip().replace('"', "").replace("'", "")
    path = "".join(c for c in path if c.isprintable())
    return os.path.abspath(os.path.normpath(path))


def get_file_list(path):
    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*")))
    return []


def load_storelist(path, delimiter):
    ext = os.path.splitext(path)[-1].lower()
    if ext in [".xlsx", ".xls"]:
        return pl.read_excel(path)
    return safe_read_csv(path, separator=delimiter)


def get_column_names(paths, file_type, delimiter=",", layout=None, start_line=0,
                     record_type=None, header_prefix=None, header_layout=None):
    if not paths:
        return []
    try:
        if file_type == "delimited":
            df = safe_read_csv(paths[0], separator=delimiter, n_rows=5)
            return df.columns
        elif file_type == "fixed" and layout:
            chunks = list(parse_fixed_width_chunks(paths[:1], layout, start_line, record_type, chunk_size=5))
            if chunks:
                return chunks[0].columns
        elif file_type == "multiline":
            if header_prefix and header_layout:
                flat = preview_flattened_multiline_fixed(
                    paths, header_prefix, header_layout, layout or [], n_rows=5
                )
            else:
                rt_list = record_type.split(",") if record_type else ["H", "D"]
                flat = preview_flattened_multiline(paths, rt_list, delimiter, n_rows=5)
            if not flat.is_empty():
                return flat.columns
    except Exception as e:
        logger.warning("Could not determine column names: %s", e)
    return []


def record_execution(metrics):
    if "execution_history" not in st.session_state:
        st.session_state.execution_history = []
    history = st.session_state.execution_history
    history.append(ProcessingRecord(
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        files_processed=metrics.files_processed,
        rows_processed=metrics.rows_processed,
        execution_time=round(metrics.total_execution_time, 2),
        peak_memory=round(metrics.peak_memory, 1),
        peak_cpu=round(metrics.peak_cpu, 1),
        warnings=len(metrics.warnings),
        errors=len(metrics.errors),
    ))
    if len(history) > MAX_HISTORY:
        st.session_state.execution_history = history[-MAX_HISTORY:]


def display_processing_history():
    if "execution_history" not in st.session_state:
        return
    history = st.session_state.execution_history
    if not history:
        return
    with st.expander("Processing History (last 10 executions)", expanded=False):
        for r in reversed(history):
            st.markdown(
                f"- **{r.timestamp}** — {r.files_processed} files, "
                f"{r.rows_processed:,} rows, "
                f"{r.execution_time}s, "
                f"{r.peak_memory}MB peak, "
                f"{r.peak_cpu}% CPU, "
                f"{r.warnings}w, {r.errors}e"
            )

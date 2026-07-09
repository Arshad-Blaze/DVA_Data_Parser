import datetime
import hashlib
import json
import os
import glob
import logging
from typing import Optional

import streamlit as st
import polars as pl
from dav_tool._parsers import (
    parse_fixed_width_chunks, preview_flattened_multiline,
    preview_flattened_multiline_fixed,
)
from dav_tool._observability import ProcessingRecord, MAX_HISTORY
from dav_tool.config import FALLBACK_ENCODING
from dav_tool.io import safe_read_csv
from dav_tool.datasource.base import IDataSource
from dav_tool.datasource.manager import get_active_source

logger = logging.getLogger(__name__)

_COLUMN_CACHE_KEY = "_column_name_cache"


def _cache_key(paths, file_type, delimiter, record_type) -> str:
    """Deterministic cache key from input parameters."""
    raw = f"{paths}|{file_type}|{delimiter}|{record_type}"
    return hashlib.md5(raw.encode()).hexdigest()


def cached_get_column_names(paths, file_type, delimiter=",", layout=None, start_line=0,
                             record_type=None, header_prefix=None, header_layout=None,
                             trailer_prefix=None, trailer_layout=None,
                             source=None):
    """get_column_names with a session-state cache to avoid re-reading on reruns."""
    if _COLUMN_CACHE_KEY not in st.session_state:
        st.session_state[_COLUMN_CACHE_KEY] = {}
    cache = st.session_state[_COLUMN_CACHE_KEY]
    key = _cache_key(str(paths), file_type, delimiter, record_type)
    if key in cache:
        return cache[key]
    cols = get_column_names(paths, file_type, delimiter, layout, start_line,
                            record_type, header_prefix, header_layout,
                            trailer_prefix, trailer_layout,
                            source=source)
    cache[key] = cols
    return cols


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


def get_file_list(path: str, source: Optional[IDataSource] = None) -> list:
    if source is None:
        source = get_active_source()
    if source is not None:
        try:
            return source.list_files(path)
        except Exception:
            return []
    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*")))
    return []


def resolve_source_paths(paths, source=None):
    """Convert remote paths to local paths the parser can use.

    For LocalDataSource the paths are returned as-is.
    For remote sources (SSH) files are downloaded to temp dirs.
    """
    if source is None:
        source = get_active_source()
    if source is None:
        return paths
    local = []
    for p in paths:
        local.append(source.download_if_required(p))
    return local


def load_storelist(path, delimiter, source=None):
    if source is None:
        source = get_active_source()
    local_path = path
    if source is not None:
        try:
            local_path = source.download_if_required(path)
        except Exception:
            pass
    ext = os.path.splitext(local_path)[-1].lower()
    if ext in [".xlsx", ".xls"]:
        return pl.read_excel(local_path)
    return safe_read_csv(local_path, separator=delimiter)


def get_column_names(paths, file_type, delimiter=",", layout=None, start_line=0,
                     record_type=None, header_prefix=None, header_layout=None,
                     trailer_prefix=None, trailer_layout=None,
                     source=None):
    if not paths:
        return []
    try:
        if file_type == "delimited":
            df = safe_read_csv(paths[0], separator=delimiter, n_rows=5, source=source)
            return df.columns
        elif file_type == "fixed" and layout:
            chunks = list(parse_fixed_width_chunks(paths[:1], layout, start_line, record_type, chunk_size=5, source=source))
            if chunks:
                return chunks[0].columns
        elif file_type == "multiline":
            if header_prefix and header_layout:
                flat = preview_flattened_multiline_fixed(
                    paths, header_prefix, header_layout, layout or [], n_rows=5,
                    trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
                    source=source,
                )
            else:
                rt_list = record_type.split(",") if record_type else ["H", "D"]
                flat = preview_flattened_multiline(paths, rt_list, delimiter, n_rows=5, source=source)
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


def display_config_review(cfg):
    """Render a read-only configuration summary in the UI."""
    from dav_tool.config_builder import config_to_summary_dict

    sections = config_to_summary_dict(cfg)

    editable = not cfg.locked
    st.subheader("Configuration" + (" (Locked)" if cfg.locked else ""))

    for section_name, items in sections.items():
        with st.expander(section_name, expanded=not cfg.locked):
            for key, val in items.items():
                st.markdown(f"**{key}:** {val}")

    with st.expander("Validation Configuration", expanded=not cfg.locked):
        vc = cfg.validation_config
        for rule_name in ["store_validation", "item_validation", "compare_store_list", "file_review"]:
            rule = getattr(vc, rule_name)
            st.markdown(f"- **{rule_name}**: {'Enabled' if rule.enabled else 'Disabled'}")

    with st.expander("Raw JSON", expanded=False):
        st.json(asdict(cfg) if hasattr(cfg, 'locked') else {})

    if not cfg.locked:
        st.download_button(
            "Download Config as JSON",
            json.dumps(asdict(cfg), indent=2, default=str),
            file_name=f"{cfg.name or 'config'}.json",
            mime="application/json",
        )


def edit_and_accept_config(cfg, key_prefix=""):
    """Render editable configuration fields and an Accept button.

    User can edit column mapping, price settings, and validation toggles
    directly in the UI. Returns True when the user accepts.
    """
    from dav_tool.format_config import asdict

    changed = False

    with st.expander("Column Mapping", expanded=True):
        if cfg.detected_columns:
            cols = cfg.detected_columns
        elif cfg.schema:
            cols = cfg.schema
        else:
            cols = []

        if cols:
            idx_map = {}
            if cfg.suggested_mapping:
                for role, col in cfg.suggested_mapping.items():
                    if col in cols:
                        idx_map[role] = cols.index(col)

            c1, c2 = st.columns(2)
            with c1:
                new_store = st.selectbox(
                    "Store Column", cols,
                    index=idx_map.get("store", 0),
                    key=f"{key_prefix}_cfg_store",
                )
                new_upc = st.selectbox(
                    "UPC Column", cols,
                    index=idx_map.get("upc", 0),
                    key=f"{key_prefix}_cfg_upc",
                )
                new_desc = st.selectbox(
                    "Description Column", cols,
                    index=idx_map.get("description", 0),
                    key=f"{key_prefix}_cfg_desc",
                )
            with c2:
                new_units = st.selectbox(
                    "Units Column", cols,
                    index=idx_map.get("units", 0),
                    key=f"{key_prefix}_cfg_units",
                )
                new_price = st.selectbox(
                    "Price Column", cols,
                    index=idx_map.get("price", 0),
                    key=f"{key_prefix}_cfg_price",
                )

            if new_store != cfg.store_col:
                cfg.store_col = new_store; changed = True
            if new_upc != cfg.upc_col:
                cfg.upc_col = new_upc; changed = True
            if new_desc != cfg.desc_col:
                cfg.desc_col = new_desc; changed = True
            if new_units != cfg.units_col:
                cfg.units_col = new_units; changed = True
            if new_price != cfg.price_col:
                cfg.price_col = new_price; changed = True

        new_price_type = st.radio(
            "Price Type", ["Total Price", "Unit Price"],
            index=0 if cfg.price_type == "Total Price" else 1,
            key=f"{key_prefix}_cfg_price_type",
        )
        if new_price_type != cfg.price_type:
            cfg.price_type = new_price_type; changed = True

        c1, c2 = st.columns(2)
        with c1:
            new_imp_dol = st.checkbox("Implied Dollars", value=cfg.implied_dollars, key=f"{key_prefix}_cfg_imp_dol")
            if new_imp_dol != cfg.implied_dollars:
                cfg.implied_dollars = new_imp_dol; changed = True
        with c2:
            new_imp_unt = st.checkbox("Implied Units", value=cfg.implied_units, key=f"{key_prefix}_cfg_imp_unt")
            if new_imp_unt != cfg.implied_units:
                cfg.implied_units = new_imp_unt; changed = True

    with st.expander("Validation Configuration", expanded=False):
        vc = cfg.validation_config
        for rule_name, label in [
            ("store_validation", "Store Level Validation"),
            ("item_validation", "Item Level Validation"),
            ("compare_store_list", "Compare Store List"),
            ("file_review", "File Review Report"),
        ]:
            rule = getattr(vc, rule_name)
            enabled = st.checkbox(
                label, value=rule.enabled,
                key=f"{key_prefix}_cfg_val_{rule_name}",
            )
            if enabled != rule.enabled:
                rule.enabled = enabled; changed = True

    accepted = st.button(
        "Accept Configuration" if not cfg.locked else "Configuration Locked",
        use_container_width=True, type="primary",
        disabled=cfg.locked,
        key=f"{key_prefix}_accept_cfg",
    )

    return accepted


# ── Progressive Stage Helpers ──────────────────────────────────────


def render_progressive_stage(
    cfg,
    section,
    key_prefix="",
    detected_columns=None,
    file_paths=None,
):
    """Render editable fields for one config section (stage).

    Returns True when the user confirms this stage.
    """
    from dav_tool.format_config import (
        ConfigSection, get_section_fields, OutputConfig,
    )
    from dav_tool.config_validator import validate_section

    fields = get_section_fields(section)
    changed = False

    if section == ConfigSection.GENERAL:
        st.markdown("**General Settings**")
        cols = st.columns(2)
        with cols[0]:
            new_name = st.text_input("Configuration Name", value=cfg.name or "", key=f"{key_prefix}_g_name")
            if new_name != cfg.name:
                cfg.name = new_name; changed = True
            new_ft = st.selectbox(
                "File Type", ["delimited", "fixed", "multiline"],
                index=["delimited", "fixed", "multiline"].index(cfg.file_type) if cfg.file_type in ["delimited", "fixed", "multiline"] else 0,
                key=f"{key_prefix}_g_ft",
            )
            if new_ft != cfg.file_type:
                cfg.file_type = new_ft; changed = True
        with cols[1]:
            new_enc = st.text_input("Encoding", value=cfg.encoding or "utf-8", key=f"{key_prefix}_g_enc")
            if new_enc != cfg.encoding:
                cfg.encoding = new_enc; changed = True
            new_hdr = st.checkbox("Has Header", value=cfg.has_header, key=f"{key_prefix}_g_hdr")
            if new_hdr != cfg.has_header:
                cfg.has_header = new_hdr; changed = True

    elif section == ConfigSection.FILE:
        st.markdown("**File Format Settings**")
        if cfg.file_type == "delimited":
            new_delim = st.selectbox(
                "Delimiter", [",", "|", "\t", ";"],
                index=[",", "|", "\t", ";"].index(cfg.delimiter) if cfg.delimiter in [",", "|", "\t", ";"] else 0,
                key=f"{key_prefix}_f_delim",
            )
            if new_delim != cfg.delimiter:
                cfg.delimiter = new_delim; changed = True

        elif cfg.file_type == "fixed":
            new_layout = st.text_input("Layout CSV Path", value=cfg.layout_file or "", key=f"{key_prefix}_f_layout")
            if new_layout != cfg.layout_file:
                cfg.layout_file = new_layout; changed = True
            new_start = st.number_input("Start Line", min_value=0, value=cfg.start_line, key=f"{key_prefix}_f_start")
            if new_start != cfg.start_line:
                cfg.start_line = new_start; changed = True

        elif cfg.file_type == "multiline":
            new_ml_delim = st.selectbox(
                "Multiline Delimiter", [",", "|", "\t", ";"],
                index=[",", "|", "\t", ";"].index(cfg.delimiter) if cfg.delimiter in [",", "|", "\t", ";"] else (0 if not cfg.ml_delimiter else [",", "|", "\t", ";"].index(cfg.ml_delimiter) if cfg.ml_delimiter in [",", "|", "\t", ";"] else 0),
                key=f"{key_prefix}_f_ml_delim",
            )
            if cfg.file_type == "multiline":
                cfg.ml_delimiter = new_ml_delim; changed = True

            if cfg.header_prefix:
                st.info(f"HDR prefix: **{cfg.header_prefix}**")
                hp = st.text_input("Header Prefix", value=cfg.header_prefix or "", key=f"{key_prefix}_f_hp")
                if hp != cfg.header_prefix:
                    cfg.header_prefix = hp; changed = True
                hf = st.text_input("Header Layout CSV", value="", key=f"{key_prefix}_f_hl")
            else:
                new_rts = st.text_input(
                    "Record Types (comma-separated, e.g. H,D)",
                    value=",".join(cfg.ml_record_types or ["H", "D"]),
                    key=f"{key_prefix}_f_rts",
                )
                if new_rts != ",".join(cfg.ml_record_types or []):
                    cfg.ml_record_types = [r.strip() for r in new_rts.split(",") if r.strip()]; changed = True

    elif section == ConfigSection.SCHEMA:
        st.markdown("**Schema & Columns**")
        cols_to_show = detected_columns or cfg.detected_columns or cfg.schema or []
        if cols_to_show:
            st.markdown(f"**Detected Columns ({len(cols_to_show)}):**")
            st.markdown(", ".join(cols_to_show))
        else:
            st.info("No columns detected yet. Load a sample file first.")

        if cfg.detected_data_types:
            st.markdown("**Data Types:**")
            for k, v in cfg.detected_data_types.items():
                st.markdown(f"- {k}: `{v}`")

        if cols_to_show:
            new_schema = st.text_area(
                "Edit schema (one column per line, or comma-separated)",
                value="\n".join(cols_to_show),
                key=f"{key_prefix}_s_schema",
            )
            parsed = [c.strip() for c in new_schema.replace("\n", ",").split(",") if c.strip()]
            if parsed and parsed != (cfg.detected_columns or cfg.schema):
                cfg.schema = parsed
                cfg.detected_columns = parsed
                changed = True

    elif section == ConfigSection.BUSINESS_RULES:
        st.markdown("**Business Rules (Column Mapping)**")
        cols_list = detected_columns or cfg.detected_columns or cfg.schema or []
        if cols_list:
            suggested = cfg.suggested_mapping or {}
            idx_map = {}
            for role in ["store", "upc", "description", "units", "price"]:
                col = suggested.get(role)
                if col in cols_list:
                    idx_map[role] = cols_list.index(col)

            c1, c2 = st.columns(2)
            with c1:
                new_store = st.selectbox("Store Column", cols_list, index=idx_map.get("store", 0), key=f"{key_prefix}_b_store")
                new_upc = st.selectbox("UPC Column", cols_list, index=idx_map.get("upc", 0), key=f"{key_prefix}_b_upc")
                new_desc = st.selectbox("Description Column", cols_list, index=idx_map.get("description", 0), key=f"{key_prefix}_b_desc")
            with c2:
                new_units = st.selectbox("Units Column", cols_list, index=idx_map.get("units", 0), key=f"{key_prefix}_b_units")
                new_price = st.selectbox("Price Column", cols_list, index=idx_map.get("price", 0), key=f"{key_prefix}_b_price")

            if new_store != cfg.store_col:
                cfg.store_col = new_store; changed = True
            if new_upc != cfg.upc_col:
                cfg.upc_col = new_upc; changed = True
            if new_desc != cfg.desc_col:
                cfg.desc_col = new_desc; changed = True
            if new_units != cfg.units_col:
                cfg.units_col = new_units; changed = True
            if new_price != cfg.price_col:
                cfg.price_col = new_price; changed = True

            new_pt = st.radio("Price Type", ["Total Price", "Unit Price"], index=0 if cfg.price_type == "Total Price" else 1, key=f"{key_prefix}_b_pt", horizontal=True)
            if new_pt != cfg.price_type:
                cfg.price_type = new_pt; changed = True

            cc1, cc2 = st.columns(2)
            with cc1:
                new_imp_dol = st.checkbox("Implied Dollars", value=cfg.implied_dollars, key=f"{key_prefix}_b_imp_dol")
                if new_imp_dol != cfg.implied_dollars:
                    cfg.implied_dollars = new_imp_dol; changed = True
            with cc2:
                new_imp_unt = st.checkbox("Implied Units", value=cfg.implied_units, key=f"{key_prefix}_b_imp_unt")
                if new_imp_unt != cfg.implied_units:
                    cfg.implied_units = new_imp_unt; changed = True

    elif section == ConfigSection.VALIDATION:
        st.markdown("**Validation Settings**")
        vc = cfg.validation_config
        for rule_name, label in [
            ("store_validation", "Store Level Validation"),
            ("item_validation", "Item Level Validation"),
            ("compare_store_list", "Compare Store List"),
            ("file_review", "File Review Report"),
        ]:
            rule = getattr(vc, rule_name)
            enabled = st.checkbox(label, value=rule.enabled, key=f"{key_prefix}_v_{rule_name}")
            if enabled != rule.enabled:
                rule.enabled = enabled; changed = True
            if enabled:
                gb = st.text_input(
                    f"Group By Columns for {rule_name}",
                    value=", ".join(rule.group_by_columns or []),
                    key=f"{key_prefix}_v_gb_{rule_name}",
                )
                new_gb = [c.strip() for c in gb.split(",") if c.strip()]
                if new_gb != rule.group_by_columns:
                    rule.group_by_columns = new_gb; changed = True

    elif section == ConfigSection.OUTPUT:
        st.markdown("**Output Settings**")
        oc = cfg.output_config
        new_fmt = st.selectbox(
            "Output Format", ["csv", "parquet", "excel"],
            index=["csv", "parquet", "excel"].index(oc.format) if oc.format in ["csv", "parquet", "excel"] else 0,
            key=f"{key_prefix}_o_fmt",
        )
        if new_fmt != oc.format:
            oc.format = new_fmt; changed = True
        new_fr = st.checkbox("Include File Review in Output", value=oc.include_file_review, key=f"{key_prefix}_o_fr")
        if new_fr != oc.include_file_review:
            oc.include_file_review = new_fr; changed = True
        new_vd = st.checkbox("Include Validation Details", value=oc.include_validation_details, key=f"{key_prefix}_o_vd")
        if new_vd != oc.include_validation_details:
            oc.include_validation_details = new_vd; changed = True
        new_dl = st.checkbox("Download Results After Processing", value=oc.download_results, key=f"{key_prefix}_o_dl")
        if new_dl != oc.download_results:
            oc.download_results = new_dl; changed = True

    # Section validation
    section_errors = validate_section(cfg, section)
    for err in section_errors:
        st.warning(f"⚠ {err}")

    confirmed = st.button(
        f"Confirm {cfg.section_label(section)}",
        use_container_width=True, type="primary",
        disabled=bool(section_errors),
        key=f"{key_prefix}_confirm_{section.value}",
    )
    return confirmed


def progressive_config_wizard(cfg, detected_columns=None, key_prefix="", file_paths=None):
    """Run the full progressive config wizard for a FormatConfig.

    Returns True when all stages are complete.
    """
    from dav_tool.format_config import iter_sections

    for section in iter_sections():
        if cfg.section_complete(section):
            continue

        st.markdown(f"### {cfg.section_label(section)}")
        confirmed = render_progressive_stage(
            cfg, section,
            key_prefix=key_prefix,
            detected_columns=detected_columns,
            file_paths=file_paths,
        )
        if confirmed:
            cfg.mark_section_complete(section)
            st.rerun()
        break  # only show one incomplete section

    if cfg.is_config_complete():
        return True
    return False


# ── Phase 8-9: UI Steps + Memory ──────────────────────────────────


PHASE_LABELS = {
    0: "1. Connection",
    1: "2. Discovery",
    2: "3. Configuration",
    3: "4. Validate Config",
    4: "5. Processing",
    5: "6. Validation",
    6: "7. Reports",
}

PHASE_ICONS = {
    0: "🔌",
    1: "🔍",
    2: "⚙️",
    3: "✅",
    4: "⚡",
    5: "📊",
    6: "📄",
}


def render_phase_progress(current_phase: int, max_phase: int = 6):
    """Render a visual progress indicator for the 7-step workflow.

    Shows completed steps (clickable to revisit), current step highlighted,
    and future steps grayed out.
    """
    PHASE_COLORS = {
        0: "#6c757d",  # Connection
        1: "#0d6efd",  # Discovery
        2: "#6f42c1",  # Configuration
        3: "#198754",  # Validate Config
        4: "#fd7e14",  # Processing
        5: "#dc3545",  # Validation
        6: "#20c997",  # Reports
    }

    steps_html = '<div style="display: flex; align-items: center; gap: 4px; padding: 8px 0; overflow-x: auto;">'

    for phase in range(7):
        label = PHASE_LABELS.get(phase, f"Step {phase+1}")
        icon = PHASE_ICONS.get(phase, "•")
        color = PHASE_COLORS.get(phase, "#6c757d")

        if phase < current_phase:
            bg = color
            text = "white"
            border = color
            hover = f"opacity: 0.8;"
        elif phase == current_phase:
            bg = color
            text = "white"
            border = color
            hover = ""
        else:
            bg = "#e9ecef"
            text = "#6c757d"
            border = "#dee2e6"
            hover = ""

        steps_html += (
            f'<div style="'
            f'  background: {bg}; color: {text}; border: 2px solid {border};'
            f'  border-radius: 20px; padding: 4px 12px; font-size: 12px;'
            f'  font-weight: {"600" if phase <= current_phase else "400"};'
            f'  white-space: nowrap; {hover}'
            f'">{icon} {label}</div>'
        )
        if phase < 6:
            arrow_color = color if phase < current_phase else "#dee2e6"
            steps_html += f'<span style="color: {arrow_color}; font-size: 14px;">→</span>'

    steps_html += "</div>"
    st.markdown(steps_html, unsafe_allow_html=True)
    st.markdown("---")


def validate_config_before_processing(cfg, key_prefix=""):
    """Render configuration validation results and allow user to proceed.

    Returns True if config is valid and user clicks proceed.
    """
    from dav_tool.config_validator import validate_config

    errors = validate_config(cfg)
    if errors:
        st.error("**Configuration has errors — fix before proceeding:**")
        for err in errors:
            st.warning(f"⚠ {err}")
        return False
    else:
        st.success("Configuration is valid. Ready to process.")
        return st.button(
            "Proceed to Processing →",
            use_container_width=True, type="primary",
            key=f"{key_prefix}_proceed_processing",
        )


def cleanup_dataframes(ctx, keep_attrs=None):
    """Delete large DataFrames from context and force garbage collection.

    Preserves attributes listed in *keep_attrs* (default: None = clear all).
    """
    import gc

    df_attrs = [
        "store_agg", "item_agg", "upc_summary", "file_review",
        "store_df", "comparison_df", "summary_df",
        "fr_prod", "fr_test",
    ]
    if keep_attrs is None:
        keep_attrs = []

    for attr in df_attrs:
        if attr in keep_attrs:
            continue
        df = getattr(ctx, attr, None)
        if df is not None:
            del df
            try:
                setattr(ctx, attr, None)
            except Exception:
                pass
    gc.collect()

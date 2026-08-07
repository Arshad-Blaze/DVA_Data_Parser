import datetime
import hashlib
import os
import glob
import logging
from typing import Optional

import streamlit as st
import polars as pl
from dav_tool._observability import ProcessingRecord, MAX_HISTORY, release_df
from dav_tool.config_validator import validate_config
from dav_tool.datasource.manager import is_connected, get_active_source
from dav_tool.options import OutputMode
from dav_tool.workflow.preview import (
    parse_fixed_width_chunks, preview_flattened_multiline,
    preview_flattened_multiline_fixed, preview_raw, preview_raw_lines,
)
from dav_tool._column_utils import (
    find_best_column_index as _find_best_column_index,
    smart_column_indices as _smart_column_indices,
)
from dav_tool.io import safe_read_csv
from dav_tool.datasource.base import IDataSource
from dav_tool.workflow import PHASE_LABELS, PHASE_ICONS
from dav_tool.workflow.discovery import DiscoveryResult, recommend_parser

logger = logging.getLogger(__name__)

_COLUMN_CACHE_KEY = "_column_name_cache"


MAX_CACHE_ENTRIES = 50


def _cache_put(cache, key, value):
    if len(cache) >= MAX_CACHE_ENTRIES:
        cache.pop(next(iter(cache)))
    cache[key] = value


def _source_id(source) -> str:
    return str(id(source)) if source else ""


def _cache_key(paths, file_type, delimiter, record_type, layout=None,
               start_line=0, header_prefix=None, header_layout=None,
               trailer_prefix=None, trailer_layout=None,
               source=None) -> str:
    layout_str = str(layout) if layout else ""
    rt = record_type or ""
    hp = header_prefix or ""
    raw = f"{paths}|{file_type}|{delimiter}|{rt}|{layout_str}|{start_line}|{hp}|{header_layout}|{trailer_prefix}|{trailer_layout}|{_source_id(source)}"
    return hashlib.md5(raw.encode()).hexdigest()


def cached_get_column_names(paths, file_type, delimiter=",", layout=None, start_line=0,
                             record_type=None, header_prefix=None, header_layout=None,
                             trailer_prefix=None, trailer_layout=None,
                             source=None):
    if _COLUMN_CACHE_KEY not in st.session_state:
        st.session_state[_COLUMN_CACHE_KEY] = {}
    cache = st.session_state[_COLUMN_CACHE_KEY]
    key = _cache_key(str(paths), file_type, delimiter, record_type,
                      layout=layout, start_line=start_line,
                      header_prefix=header_prefix,
                      header_layout=header_layout,
                      trailer_prefix=trailer_prefix,
                      trailer_layout=trailer_layout,
                      source=source)
    if key in cache:
        return cache[key]
    cols = get_column_names(paths, file_type, delimiter, layout, start_line,
                            record_type, header_prefix, header_layout,
                            trailer_prefix, trailer_layout,
                            source=source)
    _cache_put(cache, key, cols)
    return cols


_PREVIEW_CACHE_KEY = "_preview_cache"


def _preview_cache_key(paths, file_type, delimiter, layout, n_rows, start_line, record_type, source=None) -> str:
    layout_str = str(layout) if layout else ""
    rt = record_type or ""
    raw = f"{paths}|{file_type}|{delimiter}|{layout_str}|{n_rows}|{start_line}|{rt}|{_source_id(source)}"
    return hashlib.md5(raw.encode()).hexdigest()


def _preview_lines_cache_key(paths, n_rows, source=None) -> str:
    raw = f"{paths}|{n_rows}|{_source_id(source)}"
    return hashlib.md5(raw.encode()).hexdigest()


def cached_preview_raw(paths, file_type="delimited", delimiter=",", layout=None,
                        n_rows=10, start_line=0, record_type="", source=None):
    if _PREVIEW_CACHE_KEY not in st.session_state:
        st.session_state[_PREVIEW_CACHE_KEY] = {}
    cache = st.session_state[_PREVIEW_CACHE_KEY]
    key = _preview_cache_key(str(paths), file_type, delimiter, layout, n_rows, start_line, record_type, source=source)
    if key in cache:
        return cache[key]
    result = preview_raw(paths, file_type, delimiter, layout, n_rows, start_line, record_type, source=source)
    _cache_put(cache, key, result)
    return result


def cached_preview_raw_lines(paths, n_rows=10, source=None):
    if _PREVIEW_CACHE_KEY not in st.session_state:
        st.session_state[_PREVIEW_CACHE_KEY] = {}
    cache = st.session_state[_PREVIEW_CACHE_KEY]
    key = _preview_lines_cache_key(str(paths), n_rows, source=source)
    if key in cache:
        return cache[key]
    result = preview_raw_lines(paths, n_rows=n_rows, source=source)
    _cache_put(cache, key, result)
    return result


def _display_summary_sheets(output, side_label: str = "BAU"):
    """Render summary worksheets from OutputResult."""
    has_any = any([
        output.summary_kpis is not None,
        output.top_stores is not None,
        output.bottom_stores is not None,
        output.top_upcs is not None,
        output.bottom_upcs is not None,
        output.top_upcs_by_qty is not None,
        output.top_brands is not None,
        output.category_summary is not None,
        output.store_validation_summary is not None,
    ])
    if not has_any:
        return

    with st.expander("Summary Worksheets", expanded=True):
        if output.summary_kpis is not None:
            st.subheader("Key Performance Indicators")
            kpi = output.summary_kpis.to_pandas().iloc[0].to_dict()
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Stores", kpi.get(f"Store Count ({side_label})", 0))
                st.metric("UPCs", kpi.get(f"UPC Count ({side_label})", 0))
            with c2:
                st.metric("Total Quantity", f"{kpi.get(f'Total Quantity ({side_label})', 0):,.2f}")
                st.metric("Total Sales", f"${kpi.get(f'Total Sales ({side_label})', 0):,.2f}")
            with c3:
                st.metric("Avg Basket", f"${kpi.get(f'Average Basket (UPC — {side_label})', 0):,.2f}")
                st.metric("Avg Price", f"${kpi.get(f'Average Price (UPC — {side_label})', 0):,.2f}")
            with c4:
                for ek in ["Rows Processed", "Files Processed", "Peak Memory", "Total Time"]:
                    val = kpi.get(ek)
                    if val is not None:
                        st.metric(ek, val)

        if output.top_stores is not None:
            st.subheader("Top Stores")
            st.dataframe(output.top_stores.to_pandas(), use_container_width=True)

        if output.bottom_stores is not None:
            st.subheader("Bottom Stores")
            st.dataframe(output.bottom_stores.to_pandas(), use_container_width=True)

        if output.top_upcs is not None:
            st.subheader("Top UPCs by Sales")
            st.dataframe(output.top_upcs.to_pandas(), use_container_width=True)

        if output.bottom_upcs is not None:
            st.subheader("Bottom UPCs by Sales")
            st.dataframe(output.bottom_upcs.to_pandas(), use_container_width=True)

        if output.top_upcs_by_qty is not None:
            st.subheader("Top UPCs by Quantity")
            st.dataframe(output.top_upcs_by_qty.to_pandas(), use_container_width=True)

        if output.top_brands is not None:
            st.subheader("Top Brands")
            st.dataframe(output.top_brands.to_pandas(), use_container_width=True)

        if output.category_summary is not None:
            st.subheader("Category Summary")
            st.dataframe(output.category_summary.to_pandas(), use_container_width=True)

        if output.store_validation_summary is not None:
            st.subheader("Store Validation Summary")
            st.dataframe(output.store_validation_summary.to_pandas(), use_container_width=True)


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
    with st.sidebar.expander("Developer Diagnostics", expanded=False):
        m = ctx.metrics

        output_mode = getattr(ctx, 'output_mode', OutputMode.VALIDATE)
        if hasattr(output_mode, 'value'):
            output_mode = output_mode.value

        st.markdown(f"**Current Phase:** {ctx.phase}")
        st.markdown(f"**Current Operation:** {output_mode}")

        _engine_info(ctx)

        source = get_active_source()
        conn_status = "Connected" if is_connected() and source is not None else "Disconnected"
        if source is not None:
            try:
                conn_status += f" ({source.get_connection_string()[:50]})"
            except Exception as e:
                logger.debug("Could not get connection string: %s", e)
        st.markdown(f"**Connection Status:** {conn_status}")

        if hasattr(ctx, 'prod') and hasattr(ctx, 'test'):
            st.markdown(f"**BAU Type:** {ctx.prod.file_type or '—'}")
            st.markdown(f"**Test Type:** {ctx.test.file_type or '—'}")
        else:
            st.markdown(f"**Parser Type:** {getattr(ctx, 'file_type', 'N/A')}")

        st.markdown(f"**Rows Sampled:** {getattr(m, 'rows_sampled', 'N/A')}")
        st.markdown(f"**Rows Processed:** {getattr(m, 'rows_processed', 'N/A')}")
        st.markdown(f"**Discovery Time:** {getattr(m, 'discovery_time', 0):.2f}s" if hasattr(m, 'discovery_time') else "")
        st.markdown(f"**Processing Time:** {getattr(m, 'aggregation_time', 0):.2f}s")
        st.markdown(f"**Memory Usage:** {m.current_memory:.1f} MB (peak: {m.peak_memory:.1f} MB)")
        st.markdown(f"**Current CPU:** {m.current_cpu:.1f}%")
        st.markdown(f"**Chunks Processed:** {m.chunks_processed}")
        st.markdown(f"**Streaming Status:** {'Active' if m.chunks_processed > 0 else 'N/A'}")

        conf_status = "Locked" if getattr(ctx, 'config_locked', False) else "Not locked"
        st.markdown(f"**Configuration Status:** {conf_status}")
        val_done = getattr(ctx, 'done', None) or getattr(ctx, 'validation_done', None)
        st.markdown(f"**Validation Status:** {'Done' if val_done else 'Pending'}")




def _engine_info(ctx):
    """Show the bootstrapped WorkflowEngine state (presentation only)."""
    try:
        from dav_tool.ui.platform import get_workflow_engine, get_pipeline_registry
    except Exception:
        return
    try:
        engine = get_workflow_engine()
        reg = get_pipeline_registry()
    except Exception:
        st.markdown("**Platform Engine:** unavailable")
        return

    if engine is None:
        st.markdown("**Platform Engine:** not registered")
        return

    pipelines = sorted(reg.names()) if reg is not None else []
    st.markdown(f"**Platform Engine:** ready")
    st.markdown(f"**Registered Pipelines:** {len(pipelines)}")
    for name in pipelines[:8]:
        st.markdown(f"- `{name}`")
    if len(pipelines) > 8:
        st.markdown(f"  … and {len(pipelines) - 8} more")


def find_best_column_index(cols, target, synonyms):
    return _find_best_column_index(cols, target, synonyms)


def smart_column_indices(cols):
    return _smart_column_indices(cols)


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
    """List files at the given path via the active source.

    When a remote source (SSH) is active, ALWAYS uses the source.
    Never falls back to local filesystem for remote sources.
    Falls back to local filesystem only when source is None (local mode).
    """
    if source is None:
        source = get_active_source()
    if source is not None:
        try:
            return source.list_files(path)
        except Exception as e:
            logger.warning("Failed to list files via source for %s: %s", path, e)
            return []
    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*")))
    return []


def load_storelist(path, delimiter, source=None):
    if source is None:
        source = get_active_source()
    local_path = path
    if source is not None:
        try:
            local_path = source.download_if_required(path)
        except Exception as e:
            logger.warning("Failed to download storelist via source for %s: %s", path, e)
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


def autoparse_context(ctx, file_paths, source=None):
    """Parse the detected file via the Parsing Service — no UI parser decisions.

    Builds a DiscoveryResult from *ctx* (or re-detects when unavailable),
    lets the Parser Factory pick the parser through the workflow Parsing
    Service, and returns the parsed result.

    Returns a :class:`~dav_tool.parser.base.ParsedResult` (or None on failure).
    """
    from dav_tool.workflow.parsing import parse_from_discovery

    discovery = getattr(ctx, "discovery", None) or DiscoveryResult.from_context(ctx)
    if not discovery.file_paths:
        discovery.file_paths = list(file_paths)
    if not discovery.recommended_parser:
        discovery.recommended_parser = recommend_parser(discovery)

    try:
        return parse_from_discovery(discovery, source=source)
    except Exception as e:
        logger.error("Parsing via workflow service failed: %s", str(e), exc_info=True)
        return None


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


# ── Phase 8-9: UI Steps + Memory ──────────────────────────────────



def render_phase_progress(current_phase: int, max_phase: int = 6, on_reset=None):
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

    if on_reset:
        if st.button("🔄 Start Over", use_container_width=True, type="secondary"):
            on_reset()
            st.rerun()
    else:
        st.markdown("---")


def validate_config_before_processing(cfg, key_prefix=""):
    """Render configuration validation results and allow user to proceed.

    Returns True if config is valid and user clicks proceed.
    """
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
    """Delete large DataFrames from context, unregister from registry, and force GC.

    Preserves attributes listed in *keep_attrs* (default: None = clear all).
    """
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
            release_df(df, name=attr, owner="context")
            try:
                setattr(ctx, attr, None)
            except Exception as e:
                logger.debug("Could not clear context attr %s: %s", attr, e)


def display_confidence_breakdown(discovery):
    """Show a confidence breakdown expander with reasons behind the score.

    Call this after detection results are available in the UI.
    """
    if discovery is None:
        return
    confidence = getattr(discovery, "confidence", None)
    breakdown = getattr(discovery, "confidence_breakdown", None)
    if confidence is None and not breakdown:
        return
    with st.expander(f"Detection Confidence: {confidence:.0%}", expanded=False):
        if breakdown:
            for reason in breakdown:
                if "penalty:" in reason or "penalty —" in reason:
                    st.caption(f":warning: {reason}")
                elif "no penalty" in reason:
                    st.caption(f":white_check_mark: {reason}")
                else:
                    st.caption(reason)
        if not breakdown:
            st.caption("No breakdown available")

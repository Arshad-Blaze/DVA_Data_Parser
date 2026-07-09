import gc
import logging
import os
import time
import concurrent.futures
import streamlit as st
import polars as pl

logger = logging.getLogger(__name__)
from dav_tool._parsers import (
    preview_raw, preview_flattened_multiline, preview_flattened_multiline_fixed,
    load_layout,
)
from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate
from dav_tool._reports import generate_file_review
from dav_tool._observability import (
    ProcessingTimer, log_phase, setup_logging,
    print_memory_snapshot, log_dataframe_summary,
)
from dav_tool.validation.store import compare_files
from dav_tool.detection import is_multiline_record, detect_file_type, detect_record_types, detect_hdr_prefix
from dav_tool.ui.helpers import (
    clean_path, get_file_list, load_storelist, get_column_names,
    display_execution_summary, display_dev_diagnostics, record_execution,
    display_processing_history, smart_column_indices, validate_column_mapping,
    resolve_source_paths,
    render_phase_progress, validate_config_before_processing, cleanup_dataframes,
)
from dav_tool.datasource.manager import get_active_source
from dav_tool.processing_context import ProcessingContext
from dav_tool.format_config import apply_format_config, load_format_config, save_format_config, config_from_ctx
from dav_tool.config_builder import build_config
from dav_tool.ui.helpers import (
    display_config_review, edit_and_accept_config,
    progressive_config_wizard,
)

# Phase constants matching the 7-step workflow
PHASE_DISCOVERY = 1
PHASE_CONFIG = 2
PHASE_CONFIG_VALIDATED = 3
PHASE_PROCESSING = 4
PHASE_VALIDATION = 5
PHASE_REPORTS = 6


def _get_validation_config(ctx):
    """Return ValidationConfig from context or a default instance."""
    cfg = getattr(ctx, '_generated_config', None)
    if cfg is not None and hasattr(cfg, 'validation_config'):
        return cfg.validation_config
    from dav_tool.format_config import ValidationConfig
    return ValidationConfig()


def _reset_phase():
    old = st.session_state.get("onb_ctx")
    if old is not None:
        for attr_name in ["store_agg", "item_agg", "upc_summary", "file_review",
                          "store_df", "comparison_df", "summary_df",
                          "fr_prod", "fr_test"]:
            df = getattr(old, attr_name, None)
            if df is not None:
                del df
        del old
        gc.collect()
    st.session_state.onb_ctx = ProcessingContext()
    st.session_state.pop("onb_cfg_accepted", None)
    keys = list(st.session_state.keys())
    for k in keys:
        if k.startswith("onb_cfg_") or k == "_show_config":
            st.session_state.pop(k, None)


def run():
    setup_logging()
    log_phase("Page Loaded — Onboarding")

    st.title("Onboarding")

    if "onb_ctx" not in st.session_state:
        st.session_state.onb_ctx = ProcessingContext()
    ctx = st.session_state.onb_ctx

    render_phase_progress(ctx.phase)

    dev_mode = st.sidebar.checkbox("Developer Mode", key="onb_dev_mode")
    if dev_mode:
        display_dev_diagnostics(ctx)

    # Step 2: Discovery (file detection, preview, schema detection)
    _phase1_discovery(ctx)
    # Step 3: Configuration (progressive config wizard)
    if ctx.phase >= PHASE_CONFIG:
        _phase2_configuration(ctx)
    # Step 4: Config Validation
    if ctx.phase >= PHASE_CONFIG_VALIDATED:
        _phase3_config_validation(ctx)
    # Step 5: Processing (aggregation)
    if ctx.phase >= PHASE_PROCESSING:
        _phase4_processing(ctx)
    # Step 6-7: Validation + Reports
    if ctx.phase >= PHASE_VALIDATION:
        _phase5_validation(ctx)
    if ctx.phase >= PHASE_REPORTS:
        _phase6_reports(ctx)


def _phase1_discovery(ctx):
    st.markdown("### Step 2: Discovery — File Detection & Preview")

    if ctx.phase >= PHASE_CONFIG and ctx.file_paths and ctx.columns:
        return

    _onb_source = get_active_source()

    auto_path = st.session_state.get("_cm_selected_path")
    if auto_path and _onb_source is not None:
        st.info(f"**Folder:** `{auto_path}` *(from Connection Manager)*")
        if st.button("Change"):
            st.session_state.pop("_cm_selected_path", None)
            st.rerun()
        prod_txt = clean_path(auto_path)
    else:
        prod_txt = clean_path(st.text_input("Folder Path", key="onb_folder_path"))

    file_paths = get_file_list(prod_txt, source=_onb_source)

    if prod_txt and not file_paths:
        if auto_path and _onb_source is not None:
            st.error(f"No files found at remote path: `{prod_txt}`")
        else:
            st.error(f"No files found at `{prod_txt}`")

    file_type = None
    prod_delim = None
    layout_list = None
    start_line = 0
    record_type = None
    cols = []

    if prod_txt and file_paths:
        log_phase(f"Folder Selected — {prod_txt} ({len(file_paths)} files)")

        # === Config Load ===
        config_file = clean_path(st.text_input("Optional: Load Config (JSON)", key="onb_config_file"))
        if config_file and os.path.exists(config_file):
            if not getattr(ctx, '_config_applied', False):
                config = load_format_config(config_file)
                apply_format_config(config, ctx, os.path.dirname(config_file), file_paths)
                ctx._config_applied = True
                ctx._config_name = config.name or ''
                st.rerun()
            if getattr(ctx, '_config_applied', False):
                st.success(f"Config '{ctx._config_name or 'unnamed'}' loaded")

        # Use ctx fields when config was applied
        if getattr(ctx, '_config_applied', False):
            if ctx.file_type == "multiline":
                file_type = "multiline"
                if ctx.schema:
                    cols = ctx.schema
                if ctx.header_prefix and ctx.header_layout and ctx.detail_layout:
                    st.subheader("Flattened Preview (from config)")
                    flat = preview_flattened_multiline_fixed(
                        file_paths, ctx.header_prefix, ctx.header_layout,
                        ctx.detail_layout, n_rows=10,
                        trailer_prefix=ctx.trailer_prefix,
                        trailer_layout=ctx.trailer_layout,
                        source=_onb_source,
                    )
                    if not flat.is_empty():
                        st.dataframe(flat.to_pandas().head(10))
                elif ctx.ml_record_types:
                    st.subheader("Flattened Preview (from config)")
                    flat = preview_flattened_multiline(
                        file_paths, ctx.ml_record_types, ctx.ml_delimiter, n_rows=10,
                        source=_onb_source,
                    )
                    if not flat.is_empty():
                        st.dataframe(flat.to_pandas().head(10))
            else:
                file_type = ctx.file_type
                prod_delim = ctx.delimiter
                layout_list = ctx.layout
                start_line = ctx.start_line
                record_type = ctx.record_type or ""
                if file_paths:
                    cols = get_column_names(
                        file_paths, file_type, prod_delim or ",",
                        layout_list, start_line, record_type,
                        header_prefix=ctx.header_prefix,
                        header_layout=ctx.header_layout,
                        trailer_prefix=ctx.trailer_prefix,
                        trailer_layout=ctx.trailer_layout,
                        source=_onb_source,
                    )
                    st.subheader("Data Preview")
                    df_preview = preview_raw(file_paths, file_type, prod_delim or ",", layout_list,
                                              n_rows=10, start_line=start_line, record_type=record_type,
                                              source=_onb_source)
                    if not df_preview.is_empty():
                        st.dataframe(df_preview.to_pandas().head(10))
        else:
            # Normal detection flow
            log_phase("Detection Started")
            if is_multiline_record(file_paths[0], source=_onb_source):
                st.warning("Multi-line structured file detected")
                file_type = "multiline"
                _multiline_flow(file_paths, source=_onb_source)
            else:
                file_type, prod_delim = detect_file_type(file_paths[0], source=_onb_source)
                if file_type == "delimited":
                    st.success(f"Delimited ({prod_delim})")
                else:
                    st.warning("Fixed-width file")
                    file_type = "fixed"
                    layout_file = st.text_input("Layout CSV")
                    if layout_file:
                        layout_file = clean_path(layout_file)
                        if os.path.exists(layout_file):
                            layout_list = load_layout(layout_file)
                            st.success("Layout loaded")

        if file_type == "fixed" and layout_list and file_paths and not is_multiline_record(file_paths[0], source=_onb_source):
            st.subheader("Fixed Width Settings")
            colA, colB = st.columns(2)
            with colA:
                start_line = st.number_input("Start Line", min_value=0, value=start_line)
            with colB:
                record_type = st.text_input("Record Type (e.g., U)", value=record_type or "")

        if file_type and file_type != "multiline" and file_paths and not getattr(ctx, '_config_applied', False):
            st.subheader("Data Preview")
            df_preview = preview_raw(file_paths, file_type, prod_delim or ",", layout_list,
                                      n_rows=10, start_line=start_line, record_type=record_type,
                                      source=_onb_source)
            if not df_preview.is_empty():
                st.dataframe(df_preview.to_pandas().head(10))

        if file_type and not getattr(ctx, '_config_applied', False):
            log_phase(f"Detection Completed — {file_type}")

        if not getattr(ctx, '_config_applied', False):
            if file_type and file_type == "multiline":
                if ctx.ml_flattened and ctx.schema:
                    cols = ctx.schema
                else:
                    cols = []
            elif file_type and file_paths:
                cols = get_column_names(file_paths, file_type, prod_delim or ",", layout_list,
                                         start_line, record_type, source=_onb_source)

    if cols:
        log_phase(f"Schema Generated — {len(cols)} columns")

    parsing_ready = bool(cols)
    if not parsing_ready:
        if file_type is None or (file_type == "multiline" and not ctx.ml_flattened):
            st.info("Complete file detection and flattening above to proceed.")
            st.stop()
        else:
            st.stop()

    if parsing_ready and ctx.phase == 0:
        ctx.file_paths = file_paths
        ctx.file_type = file_type
        ctx.delimiter = prod_delim
        ctx.layout = layout_list
        ctx.start_line = start_line
        ctx.record_type = record_type
        ctx.columns = cols

        if not ctx.config_locked:
            st.success(f"Parsing complete — {len(cols)} column(s) detected")
            if st.button("Progressive Configuration \u2192", use_container_width=True):
                ctx._show_config = True
                ctx.phase = PHASE_CONFIG
                st.rerun()


def _phase2_configuration(ctx):
    if ctx.phase >= PHASE_CONFIG_VALIDATED:
        return

    st.markdown("### Step 3: Configuration")
    _onb_source = get_active_source()

    if getattr(ctx, '_show_config', False) and not ctx.config_locked:
        cfg = build_config(
            ctx.file_paths,
            file_type=ctx.file_type,
            delimiter=ctx.delimiter,
            layout=ctx.layout,
            header_prefix=ctx.header_prefix,
            header_layout=ctx.header_layout,
            detail_layout=ctx.detail_layout,
            trailer_prefix=ctx.trailer_prefix,
            trailer_layout=ctx.trailer_layout,
            ml_record_types=ctx.ml_record_types,
            ml_delimiter=ctx.ml_delimiter or "|",
            source=_onb_source,
        )
        ctx._generated_config = cfg
        all_done = progressive_config_wizard(
            cfg, detected_columns=ctx.columns,
            key_prefix="onb", file_paths=ctx.file_paths,
        )
        if all_done:
            ctx._generated_config = cfg
            ctx.config_locked = True
            ctx._show_config = False
            ctx.store_col = cfg.store_col
            ctx.upc_col = cfg.upc_col
            ctx.desc_col = cfg.desc_col
            ctx.units_col = cfg.units_col
            ctx.price_col = cfg.price_col
            ctx.price_type = cfg.price_type
            ctx.implied_dollars = cfg.implied_dollars
            ctx.implied_units = cfg.implied_units
            ctx.phase = PHASE_CONFIG_VALIDATED
            st.rerun()

    if ctx.config_locked:
        st.success("Configuration complete. Proceed to validation.")
        if st.button("Validate Configuration \u2192", use_container_width=True):
            ctx.phase = PHASE_CONFIG_VALIDATED
            st.rerun()


def _phase3_config_validation(ctx):
    if ctx.phase >= PHASE_PROCESSING:
        return

    st.markdown("### Step 4: Validate Configuration")
    cfg = getattr(ctx, '_generated_config', None)
    if cfg is not None:
        if validate_config_before_processing(cfg, key_prefix="onb"):
            cleanup_dataframes(ctx)
            ctx.phase = PHASE_PROCESSING
            st.rerun()
    else:
        st.warning("No configuration found. Complete the configuration step first.")


def _phase4_processing(ctx):
    if ctx.phase >= PHASE_VALIDATION:
        return

    st.markdown("### Step 5: Processing")
    _onb_source = get_active_source()

    fp = ctx.file_paths
    ft = ctx.file_type
    pd = ctx.delimiter
    ll = ctx.layout
    sl = ctx.start_line
    rt = ctx.record_type
    cols = ctx.columns

    st.subheader("Store List Input")
    storelist_path = st.text_input("Store List File Path")
    storelist_delim = st.selectbox("Store List Delimiter", [",", "|", "\t", ";"])

    st.subheader("Column Selection")
    smart_idx = smart_column_indices(cols)
    prod_store_col = st.selectbox("Retailer Store Column", cols, index=smart_idx.get("store", (0,))[0])
    prod_upc_col = st.selectbox("UPC Column", cols, index=smart_idx.get("upc", (0,))[0])
    prod_desc_col = st.selectbox("Description Column", cols, index=smart_idx.get("description", (0,))[0])
    prod_units_col = st.selectbox("Units Column", cols, index=smart_idx.get("units", (0,))[0])
    prod_price_col = st.selectbox("Price Column", cols, index=smart_idx.get("price", (0,))[0])

    storelist_store_col = None
    if storelist_path:
        storelist_df = load_storelist(storelist_path, storelist_delim)
        ext = os.path.splitext(storelist_path)[-1].lower()
        if ext not in [".xlsx", ".xls"]:
            storelist_delim = st.selectbox("Store List Delimiter", [",", "|", "\t", ";"],
                                            key="storelist_delim_sel")
            storelist_store_col = st.selectbox("Storelist Store Column", storelist_df.columns)
        else:
            st.dataframe(storelist_df.head(5))
            storelist_store_col = st.selectbox("Storelist Store Column", storelist_df.columns)

    if not ctx.mapping_confirmed:
        mapping_errors = validate_column_mapping(
            prod_store_col, prod_upc_col, prod_desc_col,
            prod_units_col, prod_price_col,
        )
        if mapping_errors:
            for err in mapping_errors:
                st.error(f"Column Mapping Error: {err}")
            st.info(
                "Please fix the column selections above before confirming. "
                "Each of the 5 required columns must be unique and properly selected."
            )

        if st.button("Confirm Mapping", use_container_width=True, disabled=bool(mapping_errors)):
            log_phase("Column Mapping Confirmed")
            ctx.store_col = prod_store_col
            ctx.upc_col = prod_upc_col
            ctx.desc_col = prod_desc_col
            ctx.units_col = prod_units_col
            ctx.price_col = prod_price_col
            ctx.storelist_path = storelist_path
            ctx.storelist_delim = storelist_delim
            ctx.storelist_store_col = storelist_store_col
            ctx.mapping_confirmed = True
            st.rerun()
    else:
        st.success("Column mapping confirmed. Ready to process.")
        save_path = st.text_input("Save config to (optional)", key="onb_save_config_path")
        if save_path and st.button("Save Config", key="onb_save_config"):
            sp = clean_path(save_path)
            if sp:
                cfg = config_from_ctx(ctx)
                save_format_config(cfg, sp)
                st.success(f"Config saved to {sp}")
        if st.button("Proceed to Processing & Validation  ->", use_container_width=True):
            log_phase("Processing Started")
            cleanup_dataframes(ctx)
            print_memory_snapshot("BEFORE AGGREGATION")
            try:
                with st.spinner("Aggregating data (Store + Item in parallel)..."):
                    def _onb_run(fn, *args, **kw):
                        t0 = time.perf_counter()
                        r = fn(*args, **kw)
                        return r, time.perf_counter() - t0

                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                        futs = [
                            ex.submit(_onb_run, stream_store_aggregate,
                                fp, ft, ctx.store_col, ctx.units_col, ctx.price_col,
                                delimiter=pd, layout=ll,
                                start_line=sl, record_type=rt,
                                multiline_record_types=ctx.ml_record_types, multiline_delimiter=ctx.ml_delimiter,
                                column_names=ctx.schema,
                                header_prefix=ctx.header_prefix, header_layout=ctx.header_layout,
                                detail_layout=ctx.detail_layout,
                                trailer_prefix=ctx.trailer_prefix, trailer_layout=ctx.trailer_layout,
                                source=_onb_source,
                            ),
                            ex.submit(_onb_run, stream_item_aggregate,
                                fp, ft,
                                ctx.upc_col, ctx.desc_col, ctx.units_col, ctx.price_col,
                                delimiter=pd, layout=ll,
                                start_line=sl, record_type=rt,
                                multiline_record_types=ctx.ml_record_types, multiline_delimiter=ctx.ml_delimiter,
                                column_names=ctx.schema,
                                header_prefix=ctx.header_prefix, header_layout=ctx.header_layout,
                                detail_layout=ctx.detail_layout,
                                trailer_prefix=ctx.trailer_prefix, trailer_layout=ctx.trailer_layout,
                                source=_onb_source,
                            ),
                        ]
                        names = ["stream_store_aggregate", "stream_item_aggregate"]
                        results = []
                        for i, future in enumerate(futs):
                            result, elapsed = future.result(timeout=600)
                            ctx.metrics.record("aggregation", names[i], elapsed)
                            results.append(result)

                    store_agg, item_agg = results

                ctx.store_agg = store_agg
                ctx.item_agg = item_agg
                print_memory_snapshot("AFTER AGGREGATION")
                log_dataframe_summary()
                cleanup_dataframes(ctx, keep_attrs=["store_agg", "item_agg"])
                ctx.phase = PHASE_VALIDATION
                st.rerun()
            except Exception as e:
                st.error(
                    f"Data processing failed. This may be due to a column mapping issue, "
                    f"data format mismatch, or file reading error.\n\n"
                    f"**Detail:** {str(e)}\n\n"
                    f"**Suggested fixes:**\n"
                    f"1. Verify your column selections match the actual data columns.\n"
                    f"2. Check that the file format is consistent across all files.\n"
                    f"3. Ensure numeric columns contain valid numbers."
                )
                logger.error("Aggregation failed: %s", str(e), exc_info=True)


def _phase5_validation(ctx):
    if ctx.phase >= PHASE_REPORTS:
        return

    st.markdown("### Step 6: Validation")

    fp = ctx.file_paths
    ft = ctx.file_type
    pd = ctx.delimiter
    ll = ctx.layout
    sl = ctx.start_line
    rt = ctx.record_type
    cols = ctx.columns

    _onb_source = get_active_source()

    prod_store_col = ctx.store_col
    prod_upc_col = ctx.upc_col
    prod_desc_col = ctx.desc_col
    prod_units_col = ctx.units_col
    prod_price_col = ctx.price_col
    storelist_path = ctx.storelist_path
    storelist_delim = ctx.storelist_delim
    storelist_store_col = ctx.storelist_store_col

    with st.expander("Aggregated Data Preview", expanded=False):
        st.subheader("Store-Level Aggregation")
        store_agg = ctx.store_agg
        if store_agg is not None and not store_agg.is_empty():
            st.dataframe(store_agg.to_pandas().head(10))

        st.subheader("UPC-Level Aggregation")
        item_agg = ctx.item_agg
        if item_agg is not None and not item_agg.is_empty():
            st.dataframe(item_agg.to_pandas().head(10))

    with st.expander("Processing Metrics", expanded=False):
        m = ctx.metrics
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Parse Time", f"{m.parse_time:.2f}s")
            st.metric("Aggregation Time", f"{m.aggregation_time:.2f}s")
            st.metric("Current Memory", f"{m.current_memory:.1f} MB")
        with c2:
            st.metric("Validation Time", f"{m.validation_time:.2f}s")
            st.metric("Report Time", f"{m.report_time:.2f}s")
            st.metric("Memory Released", f"{m.memory_released_mb:.1f} MB")
        with c3:
            st.metric("Total Time", f"{m.total_execution_time:.2f}s")
            st.metric("Peak Memory", f"{m.peak_memory:.1f} MB")
            st.metric("Peak Phase", m.peak_memory_phase or "—")

    with st.expander("Schema Details", expanded=False):
        st.markdown(f"**Detected Columns ({len(cols)})**: {', '.join(cols)}")
        st.markdown(f"**Store Column**: {prod_store_col}")
        st.markdown(f"**UPC Column**: {prod_upc_col}")
        st.markdown(f"**Description Column**: {prod_desc_col}")
        st.markdown(f"**Units Column**: {prod_units_col}")
        st.markdown(f"**Price Column**: {prod_price_col}")
        if ctx.storelist_path:
            st.markdown(f"**Store List**: {ctx.storelist_path}")
            st.markdown(f"**Store List Delimiter**: {storelist_delim}")

    vc = _get_validation_config(ctx)
    st.subheader("Select Validations")
    run_onb_compare = st.checkbox(
        "Compare Store List", value=vc.compare_store_list.enabled,
    )
    run_upc_summary = st.checkbox(
        "Generate Unique UPC Summary", value=vc.item_validation.enabled,
    )
    run_onb_file_review = st.checkbox(
        "File Review Report", value=vc.file_review.enabled,
    )

    if st.button("Validate Onboarding", use_container_width=True, type="primary"):
        with st.spinner("Running validations..."):
            _run_validation(
                fp, ft, pd, ll, sl, rt, cols,
                storelist_path, storelist_delim, storelist_store_col,
                run_onb_compare, run_upc_summary, run_onb_file_review,
                prod_store_col, prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
                header_prefix=ctx.header_prefix,
                header_layout=ctx.header_layout,
                trailer_prefix=ctx.trailer_prefix,
                trailer_layout=ctx.trailer_layout,
                source=_onb_source,
            )

    if ctx.done:
        cleanup_dataframes(ctx, keep_attrs=["store_agg", "item_agg"])
        ctx.phase = PHASE_REPORTS
        st.rerun()


def _phase6_reports(ctx):
    st.markdown("### Step 7: Reports")
    _display_results()
    display_processing_history()

    if st.button("Start Over", use_container_width=True):
        _reset_phase()
        st.rerun()


def _multiline_flow(file_paths, source=None):
    ctx = st.session_state.onb_ctx

    # If config already loaded, skip manual inputs
    if getattr(ctx, '_config_applied', False) and ctx.ml_flattened and ctx.schema:
        return

    hdr_prefixes = detect_hdr_prefix(file_paths[0], source=source)

    if hdr_prefixes:
        _hdr_fixed_flow(file_paths, hdr_prefixes, source=source)
    else:
        _delimited_ml_flow(file_paths, source=source)


def _delimited_ml_flow(file_paths, source=None):
    ctx = st.session_state.onb_ctx

    st.subheader("Raw Preview (with record-type prefixes)")
    raw_preview = preview_raw(file_paths, "multiline", n_rows=10, source=source)
    if not raw_preview.is_empty():
        st.dataframe(raw_preview.to_pandas())

    detected_types = detect_record_types(file_paths[0], source=source)
    rt_default = ",".join(detected_types) if detected_types else "H,D"

    ml_record_types = st.text_input(
        "Record Type Flags (comma-separated, e.g. H,D,U,T)",
        value=rt_default, key="onb_ml_rt"
    )
    ml_delim = st.selectbox(
        "Multiline Delimiter", [",", "|", "\t", ";"], index=0, key="onb_ml_delim"
    )

    if st.button("Flatten Records", key="onb_flatten"):
        rt_list = [r.strip() for r in ml_record_types.split(",") if r.strip()]
        if rt_list:
            ctx.ml_record_types = rt_list
            ctx.ml_delimiter = ml_delim
            ctx.ml_flattened = True
            st.rerun()

    if ctx.ml_flattened:
        _show_ml_preview_and_schema(file_paths, source=source)


def _hdr_fixed_flow(file_paths, hdr_prefixes, source=None):
    ctx = st.session_state.onb_ctx
    prefix = hdr_prefixes[0]
    st.warning(f"HDR fixed-width file detected (prefix: {prefix})")

    st.subheader("Raw Preview")
    raw_preview = preview_raw(file_paths, "multiline", n_rows=10, source=source)
    if not raw_preview.is_empty():
        st.dataframe(raw_preview.to_pandas())

    st.subheader("Header Layout CSV")
    header_layout_file = st.text_input("Header Layout CSV Path", key="onb_hdr_header_layout")
    hdr_header_layout = None
    if header_layout_file:
        hl = clean_path(header_layout_file)
        if os.path.exists(hl):
            hdr_header_layout = load_layout(hl)
            st.success(f"Header layout loaded ({len(hdr_header_layout)} fields)")

    st.subheader("Detail Layout CSV")
    detail_layout_file = st.text_input("Detail Layout CSV Path", key="onb_hdr_detail_layout")
    hdr_detail_layout = None
    if detail_layout_file:
        dl = clean_path(detail_layout_file)
        if os.path.exists(dl):
            hdr_detail_layout = load_layout(dl)
            st.success(f"Detail layout loaded ({len(hdr_detail_layout)} fields)")

    st.subheader("Trailer Layout CSV (optional)")
    trailer_prefix_hint = ctx.trailer_prefix or "TRL"
    trailer_prefix_val = st.text_input("Trailer Prefix", value=trailer_prefix_hint, key="onb_tr_prefix")
    trailer_layout_file = st.text_input("Trailer Layout CSV Path (leave empty if no trailer)", key="onb_hdr_trailer_layout")
    hdr_trailer_layout = None
    if trailer_layout_file:
        tl = clean_path(trailer_layout_file)
        if os.path.exists(tl):
            hdr_trailer_layout = load_layout(tl)
            st.success(f"Trailer layout loaded ({len(hdr_trailer_layout)} fields)")

    if st.button("Flatten Records", key="onb_hdr_flatten"):
        if hdr_header_layout and hdr_detail_layout:
            ctx.header_prefix = prefix
            ctx.header_layout = hdr_header_layout
            ctx.detail_layout = hdr_detail_layout
            ctx.trailer_prefix = trailer_prefix_val.strip() or None
            ctx.trailer_layout = hdr_trailer_layout
            ctx.ml_flattened = True
            st.rerun()

    if ctx.ml_flattened:
        _show_hdr_fixed_preview_and_schema(file_paths, prefix, source=source)


def _show_ml_preview_and_schema(file_paths, source=None):
    ctx = st.session_state.onb_ctx

    st.subheader("Flattened Preview")
    rt_list = ctx.ml_record_types
    flat_preview = preview_flattened_multiline(
        file_paths, rt_list, ctx.ml_delimiter, n_rows=10, source=source,
    )
    if not flat_preview.is_empty():
        st.dataframe(flat_preview.to_pandas())

    st.subheader("Define Column Schema")
    default_cols = flat_preview.columns
    schema_names = {}
    for i, col in enumerate(default_cols):
        schema_names[col] = st.text_input(
            f"Rename '{col}' to:", value=col, key=f"onb_schema_{i}"
        )
    if st.button("Apply Schema", key="onb_apply_schema", type="primary"):
        ctx.schema = list(schema_names.values())
        st.rerun()


def _show_hdr_fixed_preview_and_schema(file_paths, prefix, source=None):
    ctx = st.session_state.onb_ctx

    st.subheader("Flattened Preview")
    hdr_header_layout = ctx.header_layout
    hdr_detail_layout = ctx.detail_layout
    flat_preview = preview_flattened_multiline_fixed(
        file_paths, prefix, hdr_header_layout, hdr_detail_layout, n_rows=10,
        trailer_prefix=ctx.trailer_prefix, trailer_layout=ctx.trailer_layout,
        source=source,
    )
    if not flat_preview.is_empty():
        st.dataframe(flat_preview.to_pandas())

    st.subheader("Define Column Schema")
    default_cols = flat_preview.columns
    schema_names = {}
    for i, col in enumerate(default_cols):
        schema_names[col] = st.text_input(
            f"Rename '{col}' to:", value=col, key=f"onb_hdr_schema_{i}"
        )
    if st.button("Apply Schema", key="onb_hdr_apply_schema", type="primary"):
        ctx.schema = list(schema_names.values())
        st.rerun()


def _run_validation(
    file_paths, file_type, prod_delim, layout_list,
    start_line, record_type, cols,
    storelist_path, storelist_delim, storelist_store_col,
    run_onb_compare, run_upc_summary, run_onb_file_review,
    prod_store_col, prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
    header_prefix=None, header_layout=None,
    trailer_prefix=None, trailer_layout=None,
    source=None,
):
    if source is None:
        source = get_active_source()
    ctx = st.session_state.onb_ctx
    log_phase("Validation Started")

    if not any([run_onb_compare, run_upc_summary]):
        st.warning(
            "Please select at least one validation option.\n\n"
            "**Options:** Compare Store List, Generate Unique UPC Summary, "
            "or File Review Report."
        )
        st.stop()

    if run_onb_compare:
        if not storelist_path:
            st.error(
                "Store list file is required for 'Compare Store List' validation.\n\n"
                "**How to fix:** Go back to Phase 2 (Column Mapping) and enter a "
                "valid Store List File Path before running validation."
            )
            st.stop()

        storelist_df = load_storelist(storelist_path, storelist_delim)

        store_agg = ctx.store_agg
        if store_agg is not None and not store_agg.is_empty():
            prod_series = store_agg.select(["STORE_NUMBER"])
            result = compare_files(
                prod_series.to_series().to_frame("store"),
                storelist_df.select([pl.col(storelist_store_col).alias("store")]),
                "store", "store"
            )
        else:
            result = {"missing_in_test": "", "missing_in_prod": ""}

        ctx.compare_result = result

    if run_upc_summary:
        upc_summary = ctx.item_agg
        if upc_summary is not None:
            ctx.upc_summary = upc_summary

    if run_onb_file_review:
        with ProcessingTimer(ctx.metrics, "report", "generate_file_review"):
            fr = generate_file_review(
                file_paths, file_type, prod_store_col, prod_upc_col,
                prod_units_col, prod_price_col,
                delimiter=prod_delim, layout=layout_list,
                start_line=start_line, record_type=record_type,
                multiline_record_types=ctx.ml_record_types,
                multiline_delimiter=ctx.ml_delimiter,
                column_names=ctx.schema,
                header_prefix=header_prefix,
                header_layout=header_layout,
                trailer_prefix=trailer_prefix,
                trailer_layout=trailer_layout,
                precomputed_store_agg=ctx.store_agg,
                precomputed_upc_summary=ctx.item_agg,
                source=source,
            )
        ctx.file_review = fr
        log_phase("Reports Generated")

    print_memory_snapshot("AFTER VALIDATION")
    log_dataframe_summary()
    record_execution(ctx.metrics)
    log_phase("Validation Completed")
    log_phase(f"Execution Summary — {ctx.metrics.rows_processed} rows, "
              f"{ctx.metrics.total_execution_time:.2f}s, "
              f"{ctx.metrics.peak_memory:.1f}MB peak, "
              f"{len(ctx.metrics.warnings)} warnings, {len(ctx.metrics.errors)} errors")
    ctx.done = True
    st.rerun()


def _display_results():
    ctx = st.session_state.onb_ctx
    with st.expander("Onboarding Validation Results", expanded=True):
        if ctx.compare_result is not None:
            res = ctx.compare_result
            st.write(f"Missing in Storelist: {res['missing_in_test']}")
            st.write(f"Missing in Retailer: {res['missing_in_prod']}")

        if ctx.upc_summary is not None:
            df = ctx.upc_summary
            st.dataframe(df.head(100).to_pandas())
            st.download_button("Download UPC Summary", df.write_csv(), "upc_summary.csv")

        if ctx.file_review is not None:
            st.subheader("File Review Report")
            fr = ctx.file_review
            if not fr.is_empty():
                st.dataframe(fr.to_pandas())
                st.download_button("Download File Review", fr.write_csv(), "file_review.csv")

    display_execution_summary(ctx.metrics)

import hashlib
import logging
import os

import polars as pl
import streamlit as st

logger = logging.getLogger(__name__)
from dav_tool.workflow.preview import (
    preview_flattened_multiline, preview_flattened_multiline_fixed,
)
from dav_tool._observability import (
    log_phase, setup_logging,
    print_memory_snapshot, log_dataframe_summary,
)
from dav_tool.detection import (
    detect_record_types,
)
from dav_tool.ui.helpers import (
    clean_path, get_file_list, cached_get_column_names,
    display_execution_summary, _display_summary_sheets,
    display_dev_diagnostics, record_execution,
    display_processing_history, smart_column_indices, validate_column_mapping,
    cached_preview_raw, cached_preview_raw_lines,
    render_phase_progress, validate_config_before_processing, cleanup_dataframes,
    display_confidence_breakdown,
)
from dav_tool.datasource.manager import get_active_source
from dav_tool.processing_context import ProcessingContext, ExistingContext
from dav_tool.format_config import load_format_config, apply_format_config
from dav_tool.workflow.discovery import detect_file
from dav_tool.ui.layout_builder import render_layout_builder
from dav_tool.format_config import ValidationConfig, config_from_ctx
from dav_tool.ui.certification_suite import render_certification_suite
from dav_tool.workflow.flush import flush
from dav_tool.workflow.discovery_compare import compare_discovery
from dav_tool.workflow.schema_comparison import compare_schemas
from dav_tool.workflow.orchestration import run_existing_processing, run_existing_validation
from dav_tool.workflow.output import generate_existing_output, generate_migration_report

PHASE_DISCOVERY = 1
PHASE_DISCOVERY_COMPARE = 2
PHASE_CONFIG = 3
PHASE_SCHEMA_COMPARE = 4
PHASE_CONFIG_VALIDATED = 5
PHASE_PROCESSING = 6
PHASE_VALIDATION = 7
PHASE_REPORTS = 8
PHASE_MIGRATION_REPORT = 9


def _get_ex_validation_config(ctx):
    """Return ValidationConfig from prod/test config or a default."""
    side = getattr(ctx, 'prod', None)
    if side is not None:
        cfg = getattr(side, '_generated_config', None)
        if cfg is not None and hasattr(cfg, 'validation_config'):
            return cfg.validation_config
    return ValidationConfig()


def _reset_phase():
    old = st.session_state.get("ex_ctx")
    if old is not None:
        flush(metrics=old.metrics, clear_session=False, ctx_objects=[old, old.prod, old.test])
        del old
    st.session_state.ex_ctx = ExistingContext()
    keys = list(st.session_state.keys())
    for k in keys:
        if k.startswith("ex_cfg_") or k.startswith("ex_prod_cfg") or k.startswith("ex_test_cfg") or k == "_show_ex_config":
            st.session_state.pop(k, None)


def run():
    setup_logging()
    log_phase("Page Loaded — Format Change")

    st.title("Format Change")

    if "ex_ctx" not in st.session_state:
        st.session_state.ex_ctx = ExistingContext()
    if "_detection_cache" not in st.session_state:
        st.session_state._detection_cache = {}
    ctx = st.session_state.ex_ctx

    render_phase_progress(ctx.phase)

    dev_mode = st.sidebar.checkbox("Developer Mode", key="ex_dev_mode")
    if dev_mode:
        display_dev_diagnostics(ctx)
        render_certification_suite()

    _phase1_discovery(ctx)
    if ctx.phase >= PHASE_DISCOVERY_COMPARE:
        _phase_discovery_compare(ctx)
    if ctx.phase >= PHASE_CONFIG:
        _phase2_configuration(ctx)
    if ctx.phase >= PHASE_SCHEMA_COMPARE:
        _phase_schema_compare(ctx)
    if ctx.phase >= PHASE_CONFIG_VALIDATED:
        _phase3_config_validation(ctx)
    if ctx.phase >= PHASE_PROCESSING:
        _phase4_processing(ctx)
    if ctx.phase >= PHASE_VALIDATION:
        _phase5_validation(ctx)
    if ctx.phase >= PHASE_REPORTS:
        _phase6_reports(ctx)
    if ctx.phase >= PHASE_MIGRATION_REPORT:
        _phase7_migration_report(ctx)


def _phase1_discovery(ctx):
    st.markdown("### Step 2: Discovery — File Detection & Preview")

    if ctx.phase >= PHASE_CONFIG and ctx.prod.file_paths and ctx.test.file_paths:
        return

    _ex_source = get_active_source()

    auto_bau = st.session_state.get("_cm_bau_path")
    auto_test = st.session_state.get("_cm_test_path")
    if auto_bau and auto_test and _ex_source is not None:
        st.info(f"**BAU:** `{auto_bau}`  |  **Test:** `{auto_test}` *(from Connection Manager)*")
        if st.button("Change Paths"):
            st.session_state.pop("_cm_bau_path", None)
            st.session_state.pop("_cm_test_path", None)
            st.rerun()
        prod_txt = clean_path(auto_bau)
        test_txt = clean_path(auto_test)
    else:
        prod_txt = ""
        test_txt = ""

    col1, col2 = st.columns(2)

    prod_file_paths = []
    test_file_paths = []

    with col1:
        st.header("BAU")
        if not auto_bau or not auto_test or _ex_source is None:
            prod_txt = clean_path(st.text_input("BAU Folder Path", key="ex_bau_folder_path"))

        # Try to consume CM's DiscoveryResult FIRST (no file enumeration)
        cm_bau_discovery = st.session_state.get("_cm_bau_discovery")
        cm_bau_has_result = (
            cm_bau_discovery is not None
            and not getattr(cm_bau_discovery, "error", None)
            and cm_bau_discovery.file_type
            and cm_bau_discovery.file_paths
        )

        if prod_txt and cm_bau_has_result:
            discovery = cm_bau_discovery
            prod_file_paths = discovery.file_paths
            if not getattr(ctx.prod, '_config_applied', False):
                ctx.prod.discovery = discovery
                ctx.prod.file_type = discovery.file_type
                ctx.prod.delimiter = discovery.delimiter
                ctx.prod.layout = discovery.layout
                ctx.prod.columns = discovery.columns or []
                ctx.prod.schema = discovery.schema or discovery.columns or []
                ctx.prod.header_prefix = getattr(discovery, 'header_prefix', None)
            log_phase("BAU Discovery consumed from Connection Manager — no re-detection")
        elif prod_txt:
            prod_file_paths = get_file_list(prod_txt, source=_ex_source)

        # Config load for BAU
        bau_config_file = clean_path(st.text_input("Optional: BAU Config (JSON)", key="ex_bau_config_file"))
        if bau_config_file and os.path.exists(bau_config_file):
            if not getattr(ctx.prod, '_config_applied', False):
                bau_cfg = load_format_config(bau_config_file)
                apply_format_config(bau_cfg, ctx.prod, os.path.dirname(bau_config_file), prod_file_paths or None)
                ctx.prod._config_applied = True
                ctx.prod.file_paths = prod_file_paths
                st.success(f"BAU config '{bau_cfg.name or 'unnamed'}' loaded")
                st.rerun()

        # Clear failure flag and stale discovery when path changes
        prev_path = st.session_state.get("ex_bau_prev_path")
        if prod_txt != prev_path:
            st.session_state.pop("ex_bau_detection_failed", None)
            if not getattr(ctx.prod, '_config_applied', False):
                ctx.prod.file_type = None
                ctx.prod.delimiter = None
                ctx.prod.layout = None
                ctx.prod.columns = None
                ctx.prod.schema = None
                ctx.prod.discovery = None
            st.session_state["ex_bau_prev_path"] = prod_txt

        if getattr(ctx.prod, '_config_applied', False):
            st.success(f"Config loaded — {len(ctx.prod.schema or [])} columns") if ctx.prod.ml_flattened else None
        elif prod_txt and not prod_file_paths:
            st.error(f"No files found at path: {prod_txt}")
        elif prod_txt and prod_file_paths and not ctx.prod.file_type and not st.session_state.get("ex_bau_detection_failed"):
            log_phase(f"BAU Folder Selected — {prod_txt} ({len(prod_file_paths)} files)")
            if not _detect_and_set(prod_file_paths, ctx.prod, "BAU", "prod", source=_ex_source):
                st.error(f"Automatic detection failed for BAU files at: {prod_txt}")
                st.session_state["ex_bau_detection_failed"] = True
            else:
                st.session_state.pop("ex_bau_detection_failed", None)
        elif prod_txt and prod_file_paths and ctx.prod.file_type:
            if ctx.prod.file_type == "fixed" and not ctx.prod.layout:
                _detect_and_set(prod_file_paths, ctx.prod, "BAU", "prod", source=_ex_source)
            st.session_state.pop("ex_bau_detection_failed", None)

    with col2:
        _ex_source = get_active_source()
        st.header("Test")
        if not auto_bau or not auto_test or _ex_source is None:
            test_txt = clean_path(st.text_input("Test Folder Path", key="ex_test_folder_path"))

        # Try to consume CM's DiscoveryResult FIRST (no file enumeration)
        cm_test_discovery = st.session_state.get("_cm_test_discovery")
        cm_test_has_result = (
            cm_test_discovery is not None
            and not getattr(cm_test_discovery, "error", None)
            and cm_test_discovery.file_type
            and cm_test_discovery.file_paths
        )

        if test_txt and cm_test_has_result:
            discovery = cm_test_discovery
            test_file_paths = discovery.file_paths
            if not getattr(ctx.test, '_config_applied', False):
                ctx.test.discovery = discovery
                ctx.test.file_type = discovery.file_type
                ctx.test.delimiter = discovery.delimiter
                ctx.test.layout = discovery.layout
                ctx.test.columns = discovery.columns or []
                ctx.test.schema = discovery.schema or discovery.columns or []
                ctx.test.header_prefix = getattr(discovery, 'header_prefix', None)
            log_phase("Test Discovery consumed from Connection Manager — no re-detection")
        elif test_txt:
            test_file_paths = get_file_list(test_txt, source=_ex_source)

        # Config load for Test
        test_config_file = clean_path(st.text_input("Optional: Test Config (JSON)", key="ex_test_config_file"))
        if test_config_file and os.path.exists(test_config_file):
            if not getattr(ctx.test, '_config_applied', False):
                test_cfg = load_format_config(test_config_file)
                apply_format_config(test_cfg, ctx.test, os.path.dirname(test_config_file), test_file_paths or None)
                ctx.test._config_applied = True
                ctx.test.file_paths = test_file_paths
                st.success(f"Test config '{test_cfg.name or 'unnamed'}' loaded")
                st.rerun()

        # Clear failure flag and stale discovery when path changes
        prev_path = st.session_state.get("ex_test_prev_path")
        if test_txt != prev_path:
            st.session_state.pop("ex_test_detection_failed", None)
            if not getattr(ctx.test, '_config_applied', False):
                ctx.test.file_type = None
                ctx.test.delimiter = None
                ctx.test.layout = None
                ctx.test.columns = None
                ctx.test.schema = None
                ctx.test.discovery = None
            st.session_state["ex_test_prev_path"] = test_txt

        if getattr(ctx.test, '_config_applied', False):
            st.success(f"Config loaded — {len(ctx.test.schema or [])} columns") if ctx.test.ml_flattened else None
        elif test_txt and not test_file_paths:
            st.error(f"No files found at path: {test_txt}")
        elif test_txt and test_file_paths and not ctx.test.file_type and not st.session_state.get("ex_test_detection_failed"):
            log_phase(f"Test Folder Selected — {test_txt} ({len(test_file_paths)} files)")
            if not _detect_and_set(test_file_paths, ctx.test, "Test", "test", source=_ex_source):
                st.error(f"Automatic detection failed for Test files at: {test_txt}")
                st.session_state["ex_test_detection_failed"] = True
            else:
                st.session_state.pop("ex_test_detection_failed", None)
        elif test_txt and test_file_paths and ctx.test.file_type:
            if ctx.test.file_type == "fixed" and not ctx.test.layout:
                _detect_and_set(test_file_paths, ctx.test, "Test", "test", source=_ex_source)
            st.session_state.pop("ex_test_detection_failed", None)

    # Retry/manual buttons when detection failed
    if prod_txt and prod_file_paths and not ctx.prod.file_type:
        st.warning("BAU file type could not be automatically detected.")
        cr1, cr2 = st.columns(2)
        with cr1:
            if st.button("Retry BAU Detection", key="ex_bau_retry", use_container_width=True):
                st.session_state.pop("ex_bau_detection_failed", None)
                _clear_detection_cache(prod_file_paths, "prod")
                if _detect_and_set(prod_file_paths, ctx.prod, "BAU", "prod", source=_ex_source):
                    st.rerun()
        with cr2:
            if st.button("Start BAU Detection Manually", key="ex_bau_manual", use_container_width=True):
                st.session_state.pop("ex_bau_detection_failed", None)
                _clear_detection_cache(prod_file_paths, "prod")
                if _detect_and_set(prod_file_paths, ctx.prod, "BAU", "prod", source=_ex_source):
                    st.rerun()

    if test_txt and test_file_paths and not ctx.test.file_type:
        st.warning("Test file type could not be automatically detected.")
        cr1, cr2 = st.columns(2)
        with cr1:
            if st.button("Retry Test Detection", key="ex_test_retry", use_container_width=True):
                st.session_state.pop("ex_test_detection_failed", None)
                _clear_detection_cache(test_file_paths, "test")
                if _detect_and_set(test_file_paths, ctx.test, "Test", "test", source=_ex_source):
                    st.rerun()
        with cr2:
            if st.button("Start Test Detection Manually", key="ex_test_manual", use_container_width=True):
                st.session_state.pop("ex_test_detection_failed", None)
                _clear_detection_cache(test_file_paths, "test")
                if _detect_and_set(test_file_paths, ctx.test, "Test", "test", source=_ex_source):
                    st.rerun()

    if ctx.prod.file_type == "fixed" or ctx.test.file_type == "fixed":
        st.subheader("Fixed Width Settings")
        colA, colB = st.columns(2)
        with colA:
            st.number_input("BAU Start Line", min_value=0, value=0, key="fw_start_prod")
            st.text_input("BAU Record Type", value="", key="fw_rec_prod")
        with colB:
            st.number_input("Test Start Line", min_value=0, value=0, key="fw_start_test")
            st.text_input("Test Record Type", value="", key="fw_rec_test")

    ml_delim = "|"
    if ctx.prod.file_type == "multiline" or ctx.test.file_type == "multiline":
        ml_delim = _multiline_section(prod_file_paths, test_file_paths, source=_ex_source)

    if not (ctx.prod.file_type == "multiline" and ctx.test.file_type == "multiline"):
        _show_regular_previews(
            prod_file_paths, test_file_paths,
            ctx.prod.file_type, ctx.test.file_type,
            ctx.prod.delimiter, ctx.test.delimiter,
            ctx.prod.layout, ctx.test.layout,
            st.session_state.get("fw_start_prod", 0),
            st.session_state.get("fw_start_test", 0),
            st.session_state.get("fw_rec_prod", ""),
            st.session_state.get("fw_rec_test", ""),
            source=_ex_source,
        )

    both_detected = bool(ctx.prod.file_type and ctx.test.file_type)
    if ctx.prod.file_type == "multiline" and not ctx.prod.ml_flattened:
        both_detected = False
    if ctx.test.file_type == "multiline" and not ctx.test.ml_flattened:
        both_detected = False

    if both_detected and ctx.phase == 0:
        ctx.prod.file_paths = prod_file_paths
        ctx.test.file_paths = test_file_paths
        ctx.ml_delimiter = ml_delim

        redetect_c1, redetect_c2 = st.columns(2)
        with redetect_c1:
            if st.button("Re-detect BAU", key="ex_bau_redetect", use_container_width=True):
                _clear_detection_cache(prod_file_paths, "prod")
                ctx.prod.file_type = None
                ctx.prod.discovery = None
                st.rerun()
        with redetect_c2:
            if st.button("Re-detect Test", key="ex_test_redetect", use_container_width=True):
                _clear_detection_cache(test_file_paths, "test")
                ctx.test.file_type = None
                ctx.test.discovery = None
                st.rerun()

        if st.button("Compare Discovery Results \u2192", use_container_width=True):
            ctx.phase = PHASE_DISCOVERY_COMPARE
            st.rerun()


def _phase_discovery_compare(ctx):
    if ctx.phase >= PHASE_CONFIG:
        return

    st.markdown("### Step 3: Discovery Comparison — BAU vs Test")

    prod_detected = bool(ctx.prod.file_type)
    test_detected = bool(ctx.test.file_type)

    if not prod_detected or not test_detected:
        st.warning("Both BAU and Test must complete detection before comparison.")
        return

    _ex_source = get_active_source()

    dc = compare_discovery(ctx.prod, ctx.test)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("BAU")
        st.markdown(f"**File Type:** `{dc.prod_file_type or 'unknown'}`")
        st.markdown(f"**Delimiter:** `{dc.prod_delimiter or 'N/A'}`")
        st.markdown(f"**Columns ({len(dc.prod_columns)}):**")
        for col in dc.prod_columns:
            st.text(f"  {col}")

    with c2:
        st.subheader("Test")
        st.markdown(f"**File Type:** `{dc.test_file_type or 'unknown'}`")
        st.markdown(f"**Delimiter:** `{dc.test_delimiter or 'N/A'}`")
        st.markdown(f"**Columns ({len(dc.test_columns)}):**")
        for col in dc.test_columns:
            st.text(f"  {col}")

    st.subheader("Comparison")

    st.markdown(f"- **File Type Match:** {'✓' if dc.same_type else '✗'} ({dc.prod_file_type} vs {dc.test_file_type})")
    st.markdown(f"- **Delimiter Match:** {'✓' if dc.same_delimiter else '✗'} ({dc.prod_delimiter} vs {dc.test_delimiter})")
    st.markdown(f"- **Column Count Match:** {'✓' if dc.same_col_count else '✗'} ({len(dc.prod_columns)} vs {len(dc.test_columns)})")

    if dc.identical_columns:
        st.success("Columns are identical between BAU and Test.")
    elif dc.same_col_count:
        st.warning("Same column count but different column names.")
        if dc.only_prod:
            st.markdown(f"- Columns only in BAU: {', '.join(dc.only_prod)}")
        if dc.only_test:
            st.markdown(f"- Columns only in Test: {', '.join(dc.only_test)}")
    else:
        st.info("Column counts differ — schema comparison will be available after configuration.")

    if st.button("Proceed to Configuration \u2192", use_container_width=True):
        ctx.phase = PHASE_CONFIG
        st.rerun()


def _render_side_config(side_ctx, side_label, key_prefix, cols):
    smart_idx = smart_column_indices(cols)
    c1, c2 = st.columns(2)
    with c1:
        store_col = st.selectbox("Store Column", cols, index=smart_idx.get("store", (0,))[0], key=f"{key_prefix}_store")
        upc_col = st.selectbox("UPC Column", cols, index=smart_idx.get("upc", (0,))[0], key=f"{key_prefix}_upc")
        desc_col = st.selectbox("Description Column", cols, index=smart_idx.get("description", (0,))[0], key=f"{key_prefix}_desc")
    with c2:
        units_col = st.selectbox("Units Column", cols, index=smart_idx.get("units", (0,))[0], key=f"{key_prefix}_units")
        price_col = st.selectbox("Price Column", cols, index=smart_idx.get("price", (0,))[0], key=f"{key_prefix}_price")

    price_type = st.radio("Price Type", ["Total Price", "Unit Price"], horizontal=True, key=f"{key_prefix}_pt")
    implied_dollars = st.checkbox("Implied Dollars", key=f"{key_prefix}_imp_dol")
    implied_units = st.checkbox("Implied Units", key=f"{key_prefix}_imp_unt")

    errors = validate_column_mapping(store_col, upc_col, desc_col, units_col, price_col)
    if errors:
        for err in errors:
            st.error(err)

    if st.button(f"Accept {side_label} Mapping", type="primary", use_container_width=True, disabled=bool(errors), key=f"{key_prefix}_accept"):
        side_ctx.store_col = store_col
        side_ctx.upc_col = upc_col
        side_ctx.desc_col = desc_col
        side_ctx.units_col = units_col
        side_ctx.price_col = price_col
        side_ctx.price_type = price_type
        side_ctx.implied_dollars = implied_dollars
        side_ctx.implied_units = implied_units
        side_ctx.config_locked = True
        st.rerun()


def _phase2_configuration(ctx):
    if ctx.phase >= PHASE_CONFIG_VALIDATED:
        return

    st.markdown("### Step 4: Column Mapping")
    _ex_source = get_active_source()

    if not ctx.prod.config_locked:
        st.subheader("BAU Column Mapping")
        prod_cols = ctx.prod.schema or cached_get_column_names(
            ctx.prod.file_paths, ctx.prod.file_type,
            ctx.prod.delimiter or ",", ctx.prod.layout,
            source=_ex_source,
        )
        if prod_cols:
            _render_side_config(ctx.prod, "BAU", "ex_prod", prod_cols)
        else:
            st.warning("No columns detected for BAU.")

    elif not ctx.test.config_locked:
        st.subheader("Test Column Mapping")
        test_cols = ctx.test.schema or cached_get_column_names(
            ctx.test.file_paths, ctx.test.file_type,
            ctx.test.delimiter or ",", ctx.test.layout,
            source=_ex_source,
        )
        if test_cols:
            _render_side_config(ctx.test, "Test", "ex_test", test_cols)
        else:
            st.warning("No columns detected for Test.")

    if ctx.prod.config_locked and ctx.test.config_locked:
        st.success("Both mappings confirmed. Ready to compare schemas.")
        if st.button("Compare Schemas \u2192", use_container_width=True):
            ctx.phase = PHASE_SCHEMA_COMPARE
            st.rerun()


def _phase_schema_compare(ctx):
    if ctx.phase >= PHASE_CONFIG_VALIDATED:
        return

    st.markdown("### Step 5: Schema Comparison")

    sd = compare_schemas(
        ctx.prod.schema or ctx.prod.columns,
        ctx.test.schema or ctx.test.columns,
    )

    if not sd.prod_count or not sd.test_count:
        st.warning("Both BAU and Test must have column schemas for comparison.")
        if st.button("Skip Schema Comparison \u2192", use_container_width=True):
            ctx.phase = PHASE_CONFIG_VALIDATED
            st.rerun()
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Common Columns", len(sd.common))
    with c2:
        st.metric("BAU-Only Columns", len(sd.only_prod))
    with c3:
        st.metric("Test-Only Columns", len(sd.only_test))

    if sd.only_prod:
        st.warning(f"Columns present in BAU but missing in Test ({len(sd.only_prod)}):")
        st.text(", ".join(sorted(sd.only_prod)))
    if sd.only_test:
        st.info(f"New columns in Test not present in BAU ({len(sd.only_test)}):")
        st.text(", ".join(sorted(sd.only_test)))

    if sd.identical:
        st.success("Schemas match exactly — no new or removed columns detected.")

    with st.expander("Full Schema Comparison"):
        all_cols = sorted(sd.common | sd.only_prod | sd.only_test)
        rows = []
        for col in all_cols:
            rows.append({
                "Column": col,
                "In BAU": "✓" if col in sd.common or col in sd.only_prod else "—",
                "In Test": "✓" if col in sd.common or col in sd.only_test else "—",
            })
        st.dataframe(pl.DataFrame(rows).to_pandas())

    if st.button("Proceed to Config Validation \u2192", use_container_width=True, type="primary"):
        ctx.phase = PHASE_CONFIG_VALIDATED
        st.rerun()


def _phase3_config_validation(ctx):
    if ctx.phase >= PHASE_PROCESSING:
        return

    st.markdown("### Step 6: Validate Configuration")

    prod_cfg = config_from_ctx(ctx.prod)
    test_cfg = config_from_ctx(ctx.test)
    prod_ok = True
    test_ok = True

    st.subheader("BAU Configuration")
    if prod_cfg is not None:
        prod_ok = validate_config_before_processing(prod_cfg, key_prefix="ex_prod_val")
    else:
        st.warning("No BAU configuration found.")

    st.subheader("Test Configuration")
    if test_cfg is not None:
        test_ok = validate_config_before_processing(test_cfg, key_prefix="ex_test_val")
    else:
        st.warning("No Test configuration found.")

    if prod_ok and test_ok and st.button("Proceed to Processing \u2192", use_container_width=True, type="primary"):
        cleanup_dataframes(ctx)
        ctx.phase = PHASE_PROCESSING
        st.rerun()


def _phase4_processing(ctx):
    if ctx.phase >= PHASE_VALIDATION:
        return

    st.markdown("### Step 7: Processing")
    _ex_source = get_active_source()

    prod_paths = ctx.prod.file_paths
    test_paths = ctx.test.file_paths
    prod_type = ctx.prod.file_type
    test_type = ctx.test.file_type
    prod_delim = ctx.prod.delimiter
    test_delim = ctx.test.delimiter
    prod_layout_list = ctx.prod.layout
    test_layout_list = ctx.test.layout

    prod_start_line = st.session_state.get("fw_start_prod", 0)
    test_start_line = st.session_state.get("fw_start_test", 0)
    prod_record_type = st.session_state.get("fw_rec_prod", "")
    test_record_type = st.session_state.get("fw_rec_test", "")

    ml_delim_val = ctx.ml_delimiter

    eff_prod_type = (
        "multiline" if prod_type == "multiline" and ctx.prod.ml_flattened
        else prod_type
    )
    eff_test_type = (
        "multiline" if test_type == "multiline" and ctx.test.ml_flattened
        else test_type
    )

    eff_delim_prod = ml_delim_val if prod_type == "multiline" else (prod_delim or ",")
    eff_delim_test = ml_delim_val if test_type == "multiline" else (test_delim or ",")

    eff_rt_prod = (
        ",".join(ctx.prod.ml_record_types or [])
        if prod_type == "multiline" else prod_record_type
    )
    eff_rt_test = (
        ",".join(ctx.test.ml_record_types or [])
        if test_type == "multiline" else test_record_type
    )

    hdr_prefix_prod, hdr_header_prod = _get_hdr_params(ctx.prod)
    hdr_prefix_test, hdr_header_test = _get_hdr_params(ctx.test)
    hdr_detail_prod = ctx.prod.detail_layout
    hdr_detail_test = ctx.test.detail_layout
    trailer_prefix_prod = ctx.prod.trailer_prefix
    trailer_layout_prod = ctx.prod.trailer_layout
    trailer_prefix_test = ctx.test.trailer_prefix
    trailer_layout_test = ctx.test.trailer_layout

    eff_layout_prod_cols = hdr_detail_prod if hdr_prefix_prod else prod_layout_list
    eff_layout_test_cols = hdr_detail_test if hdr_prefix_test else test_layout_list

    prod_cols = ctx.prod.schema or cached_get_column_names(
        prod_paths, eff_prod_type, eff_delim_prod,
        eff_layout_prod_cols, prod_start_line, eff_rt_prod,
        header_prefix=hdr_prefix_prod, header_layout=hdr_header_prod,
        trailer_prefix=trailer_prefix_prod, trailer_layout=trailer_layout_prod,
        source=_ex_source,
    )
    test_cols = ctx.test.schema or cached_get_column_names(
        test_paths, eff_test_type, eff_delim_test,
        eff_layout_test_cols, test_start_line, eff_rt_test,
        header_prefix=hdr_prefix_test, header_layout=hdr_header_test,
        trailer_prefix=trailer_prefix_test, trailer_layout=trailer_layout_test,
        source=_ex_source,
    )

    if not ctx.prod.mapping_confirmed:
        st.subheader("Column Mapping")
        prod_smart = smart_column_indices(prod_cols)
        test_smart = smart_column_indices(test_cols)
        c1, c2 = st.columns(2)
        with c1:
            prod_store_col = st.selectbox("Store (BAU)", prod_cols, key="store_prod", index=prod_smart.get("store", (0,))[0])
            prod_units_col = st.selectbox("Units (BAU)", prod_cols, key="units_prod", index=prod_smart.get("units", (0,))[0])
            prod_price_col = st.selectbox("Price (BAU)", prod_cols, key="price_prod", index=prod_smart.get("price", (0,))[0])
            prod_upc_col = st.selectbox("UPC (BAU)", prod_cols, key="upc_prod", index=prod_smart.get("upc", (0,))[0])
            prod_desc_col = st.selectbox("Description (BAU)", prod_cols, key="desc_prod", index=prod_smart.get("description", (0,))[0])
            price_type_bau = st.radio("Price Type (BAU)", ["Total Price", "Unit Price"], key="price_bau")
            st.markdown("<small>Implied Decimal</small>", unsafe_allow_html=True)
            isimplied_dollars_prod = st.checkbox("Implied dollars (BAU)", key="imp_dol_prod")
            isimplied_units_prod = st.checkbox("Implied units (BAU)", key="imp_unt_prod")

        with c2:
            test_store_col = st.selectbox("Store (Test)", test_cols, key="store_test", index=test_smart.get("store", (0,))[0])
            test_units_col = st.selectbox("Units (Test)", test_cols, key="units_test", index=test_smart.get("units", (0,))[0])
            test_price_col = st.selectbox("Price (Test)", test_cols, key="price_test", index=test_smart.get("price", (0,))[0])
            test_upc_col = st.selectbox("UPC (Test)", test_cols, key="upc_test", index=test_smart.get("upc", (0,))[0])
            test_desc_col = st.selectbox("Description (Test)", test_cols, key="desc_test", index=test_smart.get("description", (0,))[0])
            price_type_test = st.radio("Price Type (Test)", ["Total Price", "Unit Price"], key="price_type_test")
            st.markdown("<small>Implied Decimal</small>", unsafe_allow_html=True)
            isimplied_dollars_test = st.checkbox("Implied dollars (Test)", key="imp_dol_test")
            isimplied_units_test = st.checkbox("Implied units (Test)", key="imp_unt_test")

        bau_errors = validate_column_mapping(
            prod_store_col, prod_upc_col, prod_desc_col,
            prod_units_col, prod_price_col,
        )
        test_errors = validate_column_mapping(
            test_store_col, test_upc_col, test_desc_col,
            test_units_col, test_price_col,
        )
        all_errors = []
        if bau_errors:
            all_errors.append("**BAU side:**")
            all_errors.extend(bau_errors)
        if test_errors:
            all_errors.append("**Test side:**")
            all_errors.extend(test_errors)
        if all_errors:
            for err in all_errors:
                st.error(err)
            st.info(
                "Please fix the column selections above before confirming. "
                "Each of the 5 required columns must be unique and properly selected for both sides."
            )

        if st.button("Confirm Mapping", use_container_width=True, disabled=bool(all_errors)):
            log_phase("Column Mapping Confirmed")
            ctx.prod.store_col = prod_store_col
            ctx.prod.units_col = prod_units_col
            ctx.prod.price_col = prod_price_col
            ctx.prod.upc_col = prod_upc_col
            ctx.prod.desc_col = prod_desc_col
            ctx.prod.price_type = price_type_bau
            ctx.prod.implied_dollars = isimplied_dollars_prod
            ctx.prod.implied_units = isimplied_units_prod
            ctx.test.store_col = test_store_col
            ctx.test.units_col = test_units_col
            ctx.test.price_col = test_price_col
            ctx.test.upc_col = test_upc_col
            ctx.test.desc_col = test_desc_col
            ctx.test.price_type = price_type_test
            ctx.test.implied_dollars = isimplied_dollars_test
            ctx.test.implied_units = isimplied_units_test

            ctx.prod.eff_type = eff_prod_type
            ctx.test.eff_type = eff_test_type
            ctx.prod.eff_delimiter = eff_delim_prod
            ctx.test.eff_delimiter = eff_delim_test
            ctx.prod.eff_record_type = eff_rt_prod
            ctx.test.eff_record_type = eff_rt_test
            ctx.prod.header_prefix = hdr_prefix_prod
            ctx.test.header_prefix = hdr_prefix_test
            ctx.prod.header_layout = hdr_header_prod
            ctx.test.header_layout = hdr_header_test
            ctx.prod.trailer_prefix = trailer_prefix_prod
            ctx.test.trailer_prefix = trailer_prefix_test
            ctx.prod.trailer_layout = trailer_layout_prod
            ctx.test.trailer_layout = trailer_layout_test
            ctx.prod.eff_layout = eff_layout_prod_cols
            ctx.test.eff_layout = eff_layout_test_cols
            ctx.prod.mapping_confirmed = True
            ctx.test.mapping_confirmed = True
            st.rerun()
    else:
        st.success("Column mapping confirmed. Ready to process.")
        if st.button("Proceed to Processing & Validation  ->", use_container_width=True):
                if (ctx.prod.store_agg is not None and ctx.test.store_agg is not None
                        and ctx.prod.item_agg is not None and ctx.test.item_agg is not None):
                    ctx.phase = PHASE_VALIDATION
                    st.rerun()
                log_phase("Processing Started")
                cleanup_dataframes(ctx)
                print_memory_snapshot("BEFORE AGGREGATION (EXISTING)")
                try:
                    _ex_source = get_active_source()

                    with st.spinner("Aggregating data (running BAU/Test, Store/Item in parallel)..."):
                        run_existing_processing(ctx, source=_ex_source)

                    print_memory_snapshot("AFTER AGGREGATION (EXISTING)")
                    log_dataframe_summary()
                    ctx.phase = PHASE_VALIDATION
                    st.rerun()
                except Exception as e:
                    st.error(
                        f"Data processing failed. This may be due to a column mapping issue, "
                        f"data format mismatch, or file reading error.\n\n"
                        f"**Detail:** {str(e)}\n\n"
                        f"**Suggested fixes:**\n"
                        f"1. Verify column selections match the actual data columns for both BAU and Test.\n"
                        f"2. Check that the file format is consistent across all files.\n"
                        f"3. Ensure numeric columns contain valid numbers."
                    )
                    logger.error("Aggregation failed: %s", str(e), exc_info=True)


def _phase5_validation(ctx):
    if ctx.phase >= PHASE_REPORTS:
        return

    st.markdown("### Step 8: Validation")
    _ex_source = get_active_source()

    prod_paths = ctx.prod.file_paths
    test_paths = ctx.test.file_paths
    prod_type = ctx.prod.file_type
    test_type = ctx.test.file_type
    prod_delim = ctx.prod.delimiter
    test_delim = ctx.test.delimiter
    prod_layout_list = ctx.prod.layout
    test_layout_list = ctx.test.layout
    prod_start_line = st.session_state.get("fw_start_prod", 0)
    test_start_line = st.session_state.get("fw_start_test", 0)
    prod_record_type = st.session_state.get("fw_rec_prod", "")
    test_record_type = st.session_state.get("fw_rec_test", "")

    ml_delim_val = ctx.ml_delimiter
    eff_prod_type = (
        "multiline" if prod_type == "multiline" and ctx.prod.ml_flattened
        else prod_type
    )
    eff_test_type = (
        "multiline" if test_type == "multiline" and ctx.test.ml_flattened
        else test_type
    )
    eff_delim_prod = ml_delim_val if prod_type == "multiline" else (prod_delim or ",")
    eff_delim_test = ml_delim_val if test_type == "multiline" else (test_delim or ",")
    eff_rt_prod = (
        ",".join(ctx.prod.ml_record_types or [])
        if prod_type == "multiline" else prod_record_type
    )
    eff_rt_test = (
        ",".join(ctx.test.ml_record_types or [])
        if test_type == "multiline" else test_record_type
    )
    hdr_prefix_prod, hdr_header_prod = _get_hdr_params(ctx.prod)
    hdr_prefix_test, hdr_header_test = _get_hdr_params(ctx.test)
    hdr_detail_prod = ctx.prod.detail_layout
    hdr_detail_test = ctx.test.detail_layout
    trailer_prefix_prod = ctx.prod.trailer_prefix
    trailer_layout_prod = ctx.prod.trailer_layout
    trailer_prefix_test = ctx.test.trailer_prefix
    trailer_layout_test = ctx.test.trailer_layout
    eff_layout_prod_cols = hdr_detail_prod if hdr_prefix_prod else prod_layout_list
    eff_layout_test_cols = hdr_detail_test if hdr_prefix_test else test_layout_list
    prod_cols = cached_get_column_names(
        prod_paths, eff_prod_type, eff_delim_prod,
        eff_layout_prod_cols, prod_start_line, eff_rt_prod,
        header_prefix=hdr_prefix_prod, header_layout=hdr_header_prod,
        trailer_prefix=trailer_prefix_prod, trailer_layout=trailer_layout_prod,
        source=_ex_source,
    )
    test_cols = cached_get_column_names(
        test_paths, eff_test_type, eff_delim_test,
        eff_layout_test_cols, test_start_line, eff_rt_test,
        header_prefix=hdr_prefix_test, header_layout=hdr_header_test,
        trailer_prefix=trailer_prefix_test, trailer_layout=trailer_layout_test,
        source=_ex_source,
    )

    prod_store_col = ctx.prod.store_col
    prod_units_col = ctx.prod.units_col
    prod_price_col = ctx.prod.price_col
    prod_upc_col = ctx.prod.upc_col
    prod_desc_col = ctx.prod.desc_col
    test_store_col = ctx.test.store_col
    test_units_col = ctx.test.units_col
    test_price_col = ctx.test.price_col
    test_upc_col = ctx.test.upc_col
    test_desc_col = ctx.test.desc_col

    st.info(
        f"BAU columns mapped — Store: {prod_store_col}, UPC: {prod_upc_col}, "
        f"Units: {prod_units_col}, Price: {prod_price_col}"
    )
    st.info(
        f"Test columns mapped — Store: {test_store_col}, UPC: {test_upc_col}, "
        f"Units: {test_units_col}, Price: {test_price_col}"
    )

    with st.expander("Aggregated Data Preview", expanded=False):
        cc = st.columns(2)
        with cc[0]:
            st.subheader("BAU Store-Level")
            sa = ctx.prod.store_agg
            if sa is not None and not sa.is_empty():
                st.dataframe(sa.to_pandas().head(10))

            st.subheader("BAU UPC-Level")
            ia = ctx.prod.item_agg
            if ia is not None and not ia.is_empty():
                st.dataframe(ia.to_pandas().head(10))

        with cc[1]:
            st.subheader("Test Store-Level")
            sa = ctx.test.store_agg
            if sa is not None and not sa.is_empty():
                st.dataframe(sa.to_pandas().head(10))

            st.subheader("Test UPC-Level")
            ia = ctx.test.item_agg
            if ia is not None and not ia.is_empty():
                st.dataframe(ia.to_pandas().head(10))

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
        st.markdown(f"**BAU Columns ({len(prod_cols)})**: {', '.join(prod_cols)}")
        st.markdown(f"**Test Columns ({len(test_cols)})**: {', '.join(test_cols)}")
        st.markdown("**BAU Mapping:**")
        st.markdown(f"- Store: {prod_store_col}, UPC: {prod_upc_col}")
        st.markdown(f"- Description: {prod_desc_col}, Units: {prod_units_col}, Price: {prod_price_col}")
        st.markdown("**Test Mapping:**")
        st.markdown(f"- Store: {test_store_col}, UPC: {test_upc_col}")
        st.markdown(f"- Description: {test_desc_col}, Units: {test_units_col}, Price: {test_price_col}")

    vc = _get_ex_validation_config(ctx)
    st.subheader("Select Validations")
    colA, colB = st.columns(2)
    with colA:
        run_store = st.checkbox("Store Level Validation", value=vc.store_validation.enabled)
        run_item = st.checkbox("Item Level Validation", value=vc.item_validation.enabled)
    with colB:
        run_compare_existing = st.checkbox("Compare Store List", value=vc.compare_store_list.enabled)
        run_summary = st.checkbox("Summary (requires Item)", value=vc.item_validation.enabled)
        run_file_review_existing = st.checkbox("File Review Report", value=vc.file_review.enabled)

    if st.button("Validate", use_container_width=True, type="primary"):
        with st.spinner("Running validations..."):
            try:
                _execute_validation(
                    prod_paths, test_paths, prod_type, test_type,
                    prod_delim, test_delim,
                    getattr(ctx.prod, 'eff_layout', None) or prod_layout_list,
                    getattr(ctx.test, 'eff_layout', None) or test_layout_list,
                    prod_start_line, test_start_line, prod_record_type, test_record_type,
                    prod_store_col, prod_units_col, prod_price_col, prod_upc_col, prod_desc_col,
                    test_store_col, test_units_col, test_price_col, test_upc_col, test_desc_col,
                    ctx.prod.price_type, ctx.test.price_type,
                    ctx.prod.implied_dollars, ctx.prod.implied_units,
                    ctx.test.implied_dollars, ctx.test.implied_units,
                    run_store, run_item, run_compare_existing, run_summary, run_file_review_existing,
                    trailer_prefix_prod=trailer_prefix_prod, trailer_layout_prod=trailer_layout_prod,
                    trailer_prefix_test=trailer_prefix_test, trailer_layout_test=trailer_layout_test,
                )
            except Exception as e:
                st.error(f"Validation failed: {e}")
                logger.error("Existing validation error: %s", e, exc_info=True)

    if ctx.validation_done:
        cleanup_dataframes(ctx, keep_attrs=[
            "store_df", "comparison_df", "summary_df",
            "fr_prod", "fr_test",
        ])
        ctx.phase = PHASE_REPORTS
        st.rerun()


def _phase6_reports(ctx):
    st.markdown("### Step 9: Reports")
    try:
        _display_results()
    except Exception as e:
        st.error(f"Report generation failed: {e}")
        logger.error("Existing report error: %s", e, exc_info=True)
    display_processing_history()

    if st.button("Generate Migration Report \u2192", use_container_width=True, type="primary"):
        ctx.phase = PHASE_MIGRATION_REPORT
        st.rerun()

    if st.button("Start Over", use_container_width=True):
        _reset_phase()
        st.rerun()


def _clear_detection_cache(file_paths, side_label=""):
    cache_key = hashlib.md5(str(sorted(file_paths)).encode()).hexdigest() + f"_{side_label}"
    if "_detection_cache" in st.session_state:
        st.session_state._detection_cache.pop(cache_key, None)


def _detect_and_set(file_paths, side_ctx: ProcessingContext, side_label: str = "", key_prefix: str = "", source=None):
    """Detect file type via Discovery service and set results on side_ctx.

    Stores a DiscoveryResult on the side context so downstream phases
    never need to re-detect.
    """
    log_phase(f"Detection Started — {side_label}")

    try:
        cache_key = hashlib.md5(str(sorted(file_paths)).encode()).hexdigest() + f"_{side_label}"
        cached = st.session_state._detection_cache.get(cache_key)
        if cached is not None:
            logger.info("DETECTION CACHE HIT — %s (%s)", file_paths, side_label)
            discovery = cached
        else:
            logger.info("DETECTION EXECUTED — %s (%s)", file_paths, side_label)
            discovery = detect_file(file_paths, source=source)
            st.session_state._detection_cache[cache_key] = discovery
        if discovery.error:
            if discovery.file_type == "fixed":
                st.warning(f"Fixed-width file detected ({side_label}). Define column positions below.")
            else:
                st.error(f"Detection failed for {side_label}: {discovery.error}")
                return False

        # Show confidence breakdown
        display_confidence_breakdown(discovery)

        # Store discovery result on the side context
        side_ctx.discovery = discovery
        side_ctx.columns = discovery.columns or []
        side_ctx.schema = discovery.schema or discovery.columns or []

        if discovery.file_type == "multiline":
            st.warning(f"Multi-line structured file detected ({side_label})")
            side_ctx.file_type = "multiline"
            side_ctx.header_prefix = discovery.header_prefix
            log_phase(f"Detection Completed — {side_label}: multiline")
            return True
        elif discovery.file_type == "delimited":
            st.success(f"Delimited ({discovery.delimiter})")
            side_ctx.file_type = "delimited"
            side_ctx.delimiter = discovery.delimiter
            log_phase(f"Detection Completed — {side_label}: delimited")
            return True
        elif discovery.file_type == "fixed":
            st.warning("Fixed-width file")
            side_ctx.file_type = "fixed"
            fw_layout = render_layout_builder(
                file_paths,
                existing_layout=side_ctx.layout or getattr(discovery, 'layout', None),
                candidate_layout=getattr(discovery, 'candidate_layout', None),
                source=source,
                key_prefix=f"{key_prefix}_fw_layout",
            )
            if fw_layout is not None:
                side_ctx.layout = fw_layout
                discovery.layout = fw_layout
                # Set meaningful schema from layout field names
                layout_fields = [c["field"] for c in fw_layout]
                side_ctx.columns = layout_fields
                side_ctx.schema = layout_fields
                log_phase(f"Detection Completed — {side_label}: fixed-width with layout")
                return True
            logger.warning("Layout builder returned None for %s — user did not confirm layout", side_label)
        elif discovery.file_type == "excel":
            st.success(f"Excel file detected ({side_label})")
            side_ctx.file_type = "delimited"
            side_ctx.delimiter = ","
            log_phase(f"Detection Completed — {side_label}: excel")
            return True
        else:
            st.error(f"Unrecognized file type '{discovery.file_type}' for {side_label}")
    except Exception as e:
        st.error(f"Detection failed for {side_label}: {str(e)}")

    return False


def _multiline_section(prod_paths, test_paths, source=None):
    ctx = st.session_state.ex_ctx
    st.subheader("Multiline Record Settings")
    mc1, mc2 = st.columns(2)

    with mc1:
        if ctx.prod.file_type == "multiline":
            st.markdown("**BAU Multiline**")
            if getattr(ctx.prod, '_config_applied', False) and ctx.prod.ml_flattened:
                st.success("Config loaded (flattened)")
            else:
                raw_p = cached_preview_raw(prod_paths, "multiline", n_rows=5, source=source)
                if not raw_p.is_empty():
                    st.dataframe(raw_p.to_pandas(), height=150)
                _multiline_side_inputs(prod_paths, ctx.prod, "BAU", "prod", source=source)

    with mc2:
        if ctx.test.file_type == "multiline":
            st.markdown("**Test Multiline**")
            if getattr(ctx.test, '_config_applied', False) and ctx.test.ml_flattened:
                st.success("Config loaded (flattened)")
            else:
                raw_t = cached_preview_raw(test_paths, "multiline", n_rows=5, source=source)
                if not raw_t.is_empty():
                    st.dataframe(raw_t.to_pandas(), height=150)
                _multiline_side_inputs(test_paths, ctx.test, "Test", "test", source=source)

    ml_delim = st.selectbox("Multiline Delimiter", [",", "|", "\t", ";"], index=0, key="existing_ml_delim")

    prod_configured = getattr(ctx.prod, '_config_applied', False) and ctx.prod.ml_flattened
    test_configured = getattr(ctx.test, '_config_applied', False) and ctx.test.ml_flattened
    both_pre_flattened = prod_configured and test_configured
    if both_pre_flattened:
        st.info("Both sides configured — ready to proceed.")
    elif st.button("Flatten Records", key="existing_flatten"):
        ctx.ml_delimiter = ml_delim
        if ctx.prod.file_type == "multiline":
            _store_ml_config(ctx.prod, "prod")
        if ctx.test.file_type == "multiline":
            _store_ml_config(ctx.test, "test")
        st.rerun()

    if ctx.prod.ml_flattened or ctx.test.ml_flattened:
        _flattened_preview_and_schema(prod_paths, test_paths, ml_delim, source=source)

    return ml_delim


def _multiline_side_inputs(file_paths, side_ctx: ProcessingContext, side_label: str = "", key_prefix: str = "", source=None):
    if not file_paths:
        return
    if side_ctx.header_prefix:
        hp = side_ctx.header_prefix
        st.info(f"HDR prefix: **{hp}**")
        with st.expander(f"{side_label} Header Layout", expanded=not bool(side_ctx.header_layout)):
            hdr_header = render_layout_builder(
                file_paths,
                existing_layout=side_ctx.header_layout,
                source=source,
                key_prefix=f"ex_{key_prefix}_hdr_header",
            )
            if hdr_header is not None:
                side_ctx.header_layout = hdr_header
        with st.expander(f"{side_label} Detail Layout", expanded=not bool(side_ctx.detail_layout)):
            hdr_detail = render_layout_builder(
                file_paths,
                existing_layout=side_ctx.detail_layout,
                source=source,
                key_prefix=f"ex_{key_prefix}_hdr_detail",
            )
            if hdr_detail is not None:
                side_ctx.detail_layout = hdr_detail
        with st.expander(f"{side_label} Trailer Layout (optional)", expanded=False):
            tr_prefix = st.text_input(f"{side_label} Trailer Prefix", value=side_ctx.trailer_prefix or "TRL", key=f"ex_tr_prefix_{key_prefix}")
            hdr_trailer = render_layout_builder(
                file_paths,
                existing_layout=side_ctx.trailer_layout,
                source=source,
                key_prefix=f"ex_{key_prefix}_hdr_trailer",
            )
            if hdr_trailer is not None:
                side_ctx.trailer_layout = hdr_trailer
                side_ctx.trailer_prefix = tr_prefix.strip() or None
    else:
        detected = detect_record_types(file_paths[0], source=source)
        rt_default = ",".join(detected) if detected else "H,D"
        st.text_input(
            f"{side_label} Record Type Flags",
            value=rt_default, key=f"ml_rt_{key_prefix}"
        )


def _store_ml_config(side_ctx: ProcessingContext, key_prefix: str = ""):
    if not side_ctx.header_prefix:
        rt_val = st.session_state.get(f"ml_rt_{key_prefix}", "")
        side_ctx.ml_record_types = [r.strip() for r in rt_val.split(",") if r.strip()]
    side_ctx.ml_flattened = True


def _flattened_preview_and_schema(prod_paths, test_paths, ml_delim, source=None):
    ctx = st.session_state.ex_ctx
    mc1, mc2 = st.columns(2)
    with mc1:
        st.subheader("BAU Flattened Preview")
        if ctx.prod.file_type == "multiline":
            if ctx.prod.header_prefix:
                fp = preview_flattened_multiline_fixed(
                    prod_paths,
                    ctx.prod.header_prefix,
                    ctx.prod.header_layout or [],
                    ctx.prod.detail_layout or [],
                    n_rows=10,
                    trailer_prefix=ctx.prod.trailer_prefix,
                    trailer_layout=ctx.prod.trailer_layout,
                    source=source,
                )
            else:
                fp = preview_flattened_multiline(prod_paths, ctx.prod.ml_record_types or [], ml_delim, n_rows=10, source=source)
            if not fp.is_empty():
                st.dataframe(fp.to_pandas())
    with mc2:
        st.subheader("Test Flattened Preview")
        if ctx.test.file_type == "multiline":
            if ctx.test.header_prefix:
                fp = preview_flattened_multiline_fixed(
                    test_paths,
                    ctx.test.header_prefix,
                    ctx.test.header_layout or [],
                    ctx.test.detail_layout or [],
                    n_rows=10,
                    trailer_prefix=ctx.test.trailer_prefix,
                    trailer_layout=ctx.test.trailer_layout,
                    source=source,
                )
            else:
                fp = preview_flattened_multiline(test_paths, ctx.test.ml_record_types or [], ml_delim, n_rows=10, source=source)
            if not fp.is_empty():
                st.dataframe(fp.to_pandas())

    st.subheader("Define Column Schema")
    prod_schema = {}
    test_schema = {}
    sc1, sc2 = st.columns(2)
    with sc1:
        if ctx.prod.file_type == "multiline":
            if ctx.prod.header_prefix:
                fp = preview_flattened_multiline_fixed(
                    prod_paths,
                    ctx.prod.header_prefix,
                    ctx.prod.header_layout or [],
                    ctx.prod.detail_layout or [],
                    n_rows=5,
                    trailer_prefix=ctx.prod.trailer_prefix,
                    trailer_layout=ctx.prod.trailer_layout,
                    source=source,
                )
            else:
                fp = preview_flattened_multiline(prod_paths, ctx.prod.ml_record_types or [], ml_delim, n_rows=5, source=source)
            if not fp.is_empty():
                st.markdown("**BAU Column Names**")
                for i, col in enumerate(fp.columns):
                    prod_schema[col] = st.text_input(
                        f"BAU '{col}' \u2192", value=col, key=f"ex_schema_prod_{i}"
                    )
    with sc2:
        if ctx.test.file_type == "multiline":
            if ctx.test.header_prefix:
                fp = preview_flattened_multiline_fixed(
                    test_paths,
                    ctx.test.header_prefix,
                    ctx.test.header_layout or [],
                    ctx.test.detail_layout or [],
                    n_rows=5,
                    trailer_prefix=ctx.test.trailer_prefix,
                    trailer_layout=ctx.test.trailer_layout,
                    source=source,
                )
            else:
                fp = preview_flattened_multiline(test_paths, ctx.test.ml_record_types or [], ml_delim, n_rows=5, source=source)
            if not fp.is_empty():
                st.markdown("**Test Column Names**")
                for i, col in enumerate(fp.columns):
                    test_schema[col] = st.text_input(
                        f"Test '{col}' \u2192", value=col, key=f"ex_schema_test_{i}"
                    )

    if st.button("Apply Schema", key="ex_apply_schema"):
        if prod_schema:
            ctx.prod.schema = list(prod_schema.values())
        if test_schema:
            ctx.test.schema = list(test_schema.values())
        st.rerun()


def _show_regular_previews(prod_paths, test_paths, prod_type, test_type,
                           prod_delim, test_delim, prod_layout_list, test_layout_list,
                           prod_start_line, test_start_line,
                           prod_record_type, test_record_type,
                           source=None):
    if prod_paths and test_paths and prod_type and test_type:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("BAU Preview")
            pv = cached_preview_raw(prod_paths, prod_type, prod_delim or ",", prod_layout_list,
                              n_rows=10, start_line=prod_start_line, record_type=prod_record_type,
                              source=source)
            if not pv.is_empty():
                st.table(pv.to_pandas().iloc[:10, :10].astype(str))
        with c2:
            st.subheader("Test Preview")
            tv = cached_preview_raw(test_paths, test_type, test_delim or ",", test_layout_list,
                              n_rows=10, start_line=test_start_line, record_type=test_record_type,
                              source=source)
            if not tv.is_empty():
                st.table(tv.to_pandas().iloc[:10, :10].astype(str))


def _get_hdr_params(side_ctx: ProcessingContext):
    if side_ctx.header_prefix:
        return side_ctx.header_prefix, side_ctx.header_layout
    return None, None


def _execute_validation(
    prod_paths, test_paths, prod_type, test_type,
    prod_delim, test_delim, prod_layout_list, test_layout_list,
    prod_start_line, test_start_line, prod_record_type, test_record_type,
    prod_store_col, prod_units_col, prod_price_col, prod_upc_col, prod_desc_col,
    test_store_col, test_units_col, test_price_col, test_upc_col, test_desc_col,
    price_type_bau, price_type_test,
    isimplied_dollars_prod, isimplied_units_prod,
    isimplied_dollars_test, isimplied_units_test,
    run_store, run_item, run_compare_existing, run_summary, run_file_review_existing,
    trailer_prefix_prod=None, trailer_layout_prod=None,
    trailer_prefix_test=None, trailer_layout_test=None,
):
    ctx = st.session_state.ex_ctx
    log_phase("Validation Started")

    if not any([run_store, run_item, run_compare_existing, run_summary]):
        st.warning(
            "Please select at least one validation option.\n\n"
            "**Options:** Store Level Validation, Item Level Validation, "
            "Compare Store List, Summary, or File Review Report."
        )
        return

    run_existing_validation(
        ctx,
        prod_paths, test_paths,
        prod_type, test_type,
        prod_delim, test_delim,
        prod_layout_list, test_layout_list,
        prod_start_line, test_start_line,
        prod_record_type, test_record_type,
        prod_store_col, prod_units_col, prod_price_col, prod_upc_col, prod_desc_col,
        test_store_col, test_units_col, test_price_col, test_upc_col, test_desc_col,
        price_type_bau, price_type_test,
        isimplied_dollars_prod, isimplied_units_prod,
        isimplied_dollars_test, isimplied_units_test,
        run_store, run_item, run_compare_existing, run_summary, run_file_review_existing,
        trailer_prefix_prod=trailer_prefix_prod, trailer_layout_prod=trailer_layout_prod,
        trailer_prefix_test=trailer_prefix_test, trailer_layout_test=trailer_layout_test,
        source=get_active_source(),
    )

    print_memory_snapshot("AFTER VALIDATION (EXISTING)")
    log_dataframe_summary()
    record_execution(ctx.metrics)
    log_phase("Validation Completed")
    log_phase(f"Execution Summary — {ctx.metrics.rows_processed} rows, "
              f"{ctx.metrics.total_execution_time:.2f}s, "
              f"{ctx.metrics.peak_memory:.1f}MB peak, "
              f"{len(ctx.metrics.warnings)} warnings, {len(ctx.metrics.errors)} errors")
    ctx.validation_done = True
    st.rerun()


def _display_results():
    ctx = st.session_state.ex_ctx
    output = generate_existing_output(ctx)

    with st.expander("Validation Results", expanded=True):
        if output.compare_result is not None:
            st.subheader("Store Compare")
            res = output.compare_result
            st.write(f"Missing in Test: {res['missing_in_test']}")
            st.write(f"Missing in BAU: {res['missing_in_prod']}")

        if output.summary_df is not None:
            st.subheader("Summary")
            st.dataframe(output.summary_df.to_pandas())

        if output.store_df is not None:
            st.subheader("Store Validation")
            st.dataframe(output.store_df.to_pandas().head(100))
            if output.store_df_csv:
                st.download_button("Download Store Validation", output.store_df_csv, "store_validation.csv")

        if output.comparison_df is not None:
            st.subheader("Item Validation")
            st.dataframe(output.comparison_df.to_pandas().head(100))
            if output.comparison_df_csv:
                st.download_button("Download Item Validation", output.comparison_df_csv, "item_validation.csv")

        if output.fr_prod is not None or output.fr_test is not None:
            st.subheader("File Review Report")
            cc = st.columns(2)
            with cc[0]:
                if output.fr_prod is not None and not output.fr_prod.is_empty():
                    st.markdown("**BAU**")
                    st.dataframe(output.fr_prod.to_pandas())
                    if output.fr_prod_csv:
                        st.download_button("Download BAU File Review", output.fr_prod_csv, "bau_file_review.csv")
            with cc[1]:
                if output.fr_test is not None and not output.fr_test.is_empty():
                    st.markdown("**Test**")
                    st.dataframe(output.fr_test.to_pandas())
                    if output.fr_test_csv:
                        st.download_button("Download Test File Review", output.fr_test_csv, "test_file_review.csv")

    _display_summary_sheets(output, "BAU")

    display_execution_summary(output.metrics)


def _phase7_migration_report(ctx):
    st.markdown("### Step 10: Migration Report")
    try:
        output = generate_migration_report(ctx)
    except Exception as e:
        st.error(f"Migration report failed: {e}")
        logger.error("Migration report error: %s", e, exc_info=True)
        return
    sd = output.schema_diff
    oc = output.operation_compare

    st.subheader("Migration Summary")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("BAU Columns", output.migration_metrics.get("prod_columns", 0))
    with c2:
        st.metric("Test Columns", output.migration_metrics.get("test_columns", 0))
    with c3:
        st.metric("Common", output.migration_metrics.get("common_columns", 0))
    with c4:
        st.metric("New in Test", output.migration_metrics.get("new_in_test", 0))

    st.subheader("Aggregation Comparison")
    if oc and (oc.prod_store_count or oc.test_store_count):
        st.info(f"**Store Count:** BAU={oc.prod_store_count}, Test={oc.test_store_count}")
    else:
        st.info("Store aggregation not available for both sides.")

    if oc and (oc.prod_item_count or oc.test_item_count):
        st.info(f"**Item Count:** BAU={oc.prod_item_count}, Test={oc.test_item_count}")
    else:
        st.info("Item aggregation not available for both sides.")

    st.subheader("Validation Results")
    if output.compare_result is not None:
        missing_test = len(output.compare_result.get("missing_in_test", "").split(",")) if output.compare_result.get("missing_in_test") else 0
        missing_prod = len(output.compare_result.get("missing_in_prod", "").split(",")) if output.compare_result.get("missing_in_prod") else 0
        st.markdown(f"- **Store Comparison:** {missing_test} stores missing in Test, {missing_prod} stores missing in BAU")
    else:
        st.info("Store list comparison not performed.")

    st.subheader("Recommendations")
    for rec in output.migration_recommendations:
        st.markdown(f"- {rec}")

    with st.expander("Execution Metrics"):
        display_execution_summary(output.metrics)

    if output.migration_report_json:
        st.download_button(
            "Download Migration Report (JSON)",
            output.migration_report_json,
            file_name="migration_report.json",
            use_container_width=True,
        )

    if st.button("Start Over", use_container_width=True):
        _reset_phase()
        st.rerun()

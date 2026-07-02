import os
import streamlit as st
import polars as pl
from dav_tool._parsers import (
    preview_raw, preview_flattened_multiline, preview_flattened_multiline_fixed,
    load_layout,
)
from dav_tool._aggregators import (
    stream_store_aggregate, stream_item_aggregate,
)
from dav_tool._reports import generate_file_review
from dav_tool._observability import ProcessingTimer, log_phase, setup_logging
from dav_tool.validation.store import compare_files, storelevelvalidation
from dav_tool.validation.item import run_item_validation
from dav_tool.detection import (
    is_multiline_record, detect_file_type, detect_record_types,
    detect_hdr_prefix,
)
from dav_tool.ui.helpers import clean_path, get_file_list, get_column_names, display_execution_summary, display_dev_diagnostics
from dav_tool.processing_context import ProcessingContext, ExistingContext


def _reset_phase():
    st.session_state.ex_ctx = ExistingContext()


def run():
    setup_logging()
    log_phase("Page Loaded — Existing")

    st.title("Existing")

    if "ex_ctx" not in st.session_state:
        st.session_state.ex_ctx = ExistingContext()
    ctx = st.session_state.ex_ctx

    dev_mode = st.sidebar.checkbox("Developer Mode", key="ex_dev_mode")
    if dev_mode:
        display_dev_diagnostics(ctx)

    _phase0_detection_and_preview(ctx)
    if ctx.phase >= 1:
        _phase1_column_mapping(ctx)
    if ctx.phase >= 2:
        _phase2_validation(ctx)


def _phase0_detection_and_preview(ctx):
    st.markdown("### Phase 1: File Detection & Preview")

    col1, col2 = st.columns(2)

    with col1:
        st.header("BAU")
        prod_txt = clean_path(st.text_input("BAU Folder Path"))
        prod_file_paths = get_file_list(prod_txt)
        if prod_txt and prod_file_paths:
            _detect_and_set(prod_file_paths, ctx.prod, "BAU", "prod")

    with col2:
        st.header("Test")
        test_txt = clean_path(st.text_input("Test Folder Path"))
        test_file_paths = get_file_list(test_txt)
        if test_txt and test_file_paths:
            _detect_and_set(test_file_paths, ctx.test, "Test", "test")

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
        ml_delim = _multiline_section(prod_file_paths, test_file_paths)

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
        )

    both_detected = bool(ctx.prod.file_type and ctx.test.file_type)
    if ctx.prod.file_type == "multiline" and not ctx.prod.ml_flattened:
        both_detected = False
    if ctx.test.file_type == "multiline" and not ctx.test.ml_flattened:
        both_detected = False

    if both_detected and ctx.phase == 0:
        if st.button("Proceed to Column Mapping  ->", use_container_width=True):
            ctx.prod.file_paths = prod_file_paths
            ctx.test.file_paths = test_file_paths
            ctx.ml_delimiter = ml_delim
            ctx.phase = 1
            st.rerun()


def _phase1_column_mapping(ctx):
    st.divider()
    st.markdown("### Phase 2: Column Mapping")

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

    eff_layout_prod_cols = hdr_detail_prod if hdr_prefix_prod else prod_layout_list
    eff_layout_test_cols = hdr_detail_test if hdr_prefix_test else test_layout_list

    prod_cols = get_column_names(
        prod_paths, eff_prod_type, eff_delim_prod,
        eff_layout_prod_cols, prod_start_line, eff_rt_prod,
        header_prefix=hdr_prefix_prod, header_layout=hdr_header_prod,
    )
    test_cols = get_column_names(
        test_paths, eff_test_type, eff_delim_test,
        eff_layout_test_cols, test_start_line, eff_rt_test,
        header_prefix=hdr_prefix_test, header_layout=hdr_header_test,
    )

    st.subheader("Column Mapping")
    c1, c2 = st.columns(2)
    with c1:
        prod_store_col = st.selectbox("Store (BAU)", prod_cols, key="store_prod")
        prod_units_col = st.selectbox("Units (BAU)", prod_cols, key="units_prod")
        prod_price_col = st.selectbox("Price (BAU)", prod_cols, key="price_prod")
        prod_upc_col = st.selectbox("UPC (BAU)", prod_cols, key="upc_prod")
        prod_desc_col = st.selectbox("Description (BAU)", prod_cols, key="desc_prod")
        price_type_bau = st.radio("Price Type (BAU)", ["Total Price", "Unit Price"], key="price_bau")
        st.markdown("<small>Implied Decimal</small>", unsafe_allow_html=True)
        isimplied_dollars_prod = st.checkbox("Implied dollars (BAU)", key="imp_dol_prod")
        isimplied_units_prod = st.checkbox("Implied units (BAU)", key="imp_unt_prod")

    with c2:
        test_store_col = st.selectbox("Store (Test)", test_cols, key="store_test")
        test_units_col = st.selectbox("Units (Test)", test_cols, key="units_test")
        test_price_col = st.selectbox("Price (Test)", test_cols, key="price_test")
        test_upc_col = st.selectbox("UPC (Test)", test_cols, key="upc_test")
        test_desc_col = st.selectbox("Description (Test)", test_cols, key="desc_test")
        price_type_test = st.radio("Price Type (Test)", ["Total Price", "Unit Price"], key="price_test")
        st.markdown("<small>Implied Decimal</small>", unsafe_allow_html=True)
        isimplied_dollars_test = st.checkbox("Implied dollars (Test)", key="imp_dol_test")
        isimplied_units_test = st.checkbox("Implied units (Test)", key="imp_unt_test")

    if ctx.phase == 1:
        if st.button("Save Mapping & Proceed to Validation  ->", use_container_width=True):
            log_phase("Column Mapping Saved")
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
            ctx.prod.eff_layout = eff_layout_prod_cols
            ctx.test.eff_layout = eff_layout_test_cols

            with ProcessingTimer(ctx.metrics, "aggregation", "BAU stream_store_aggregate"):
                prod_store_agg = stream_store_aggregate(
                    prod_paths, prod_type,
                    prod_store_col, prod_units_col, prod_price_col,
                    delimiter=prod_delim, layout=prod_layout_list,
                    price_type=price_type_bau,
                    implied_dollars=isimplied_dollars_prod,
                    implied_units=isimplied_units_prod,
                    start_line=prod_start_line, record_type=prod_record_type,
                    multiline_record_types=ctx.prod.ml_record_types if prod_type == "multiline" and not hdr_prefix_prod else None,
                    multiline_delimiter=ml_delim_val, column_names=ctx.prod.schema,
                    header_prefix=hdr_prefix_prod, header_layout=hdr_header_prod,
                )
            with ProcessingTimer(ctx.metrics, "aggregation", "Test stream_store_aggregate"):
                test_store_agg = stream_store_aggregate(
                    test_paths, test_type,
                    test_store_col, test_units_col, test_price_col,
                    delimiter=test_delim, layout=test_layout_list,
                    price_type=price_type_test,
                    implied_dollars=isimplied_dollars_test,
                    implied_units=isimplied_units_test,
                    start_line=test_start_line, record_type=test_record_type,
                    multiline_record_types=ctx.test.ml_record_types if test_type == "multiline" and not hdr_prefix_test else None,
                    multiline_delimiter=ml_delim_val, column_names=ctx.test.schema,
                    header_prefix=hdr_prefix_test, header_layout=hdr_header_test,
                )
            with ProcessingTimer(ctx.metrics, "aggregation", "BAU stream_item_aggregate"):
                prod_item_agg = stream_item_aggregate(
                    prod_paths, prod_type,
                    prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
                    delimiter=prod_delim, layout=prod_layout_list,
                    implied_units=isimplied_units_prod,
                    implied_dollars=isimplied_dollars_prod,
                    start_line=prod_start_line, record_type=prod_record_type,
                    multiline_record_types=ctx.prod.ml_record_types if prod_type == "multiline" and not hdr_prefix_prod else None,
                    multiline_delimiter=ml_delim_val, column_names=ctx.prod.schema,
                    header_prefix=hdr_prefix_prod, header_layout=hdr_header_prod,
                )
            with ProcessingTimer(ctx.metrics, "aggregation", "Test stream_item_aggregate"):
                test_item_agg = stream_item_aggregate(
                    test_paths, test_type,
                    test_upc_col, test_desc_col, test_units_col, test_price_col,
                    delimiter=test_delim, layout=test_layout_list,
                    implied_units=isimplied_units_test,
                    implied_dollars=isimplied_dollars_test,
                    start_line=test_start_line, record_type=test_record_type,
                    multiline_record_types=ctx.test.ml_record_types if test_type == "multiline" and not hdr_prefix_test else None,
                    multiline_delimiter=ml_delim_val, column_names=ctx.test.schema,
                    header_prefix=hdr_prefix_test, header_layout=hdr_header_test,
                )

            ctx.prod.store_agg = prod_store_agg
            ctx.test.store_agg = test_store_agg
            ctx.prod.item_agg = prod_item_agg
            ctx.test.item_agg = test_item_agg
            ctx.phase = 2
            st.rerun()


def _phase2_validation(ctx):
    st.divider()
    st.markdown("### Phase 3: Validation")

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

    st.subheader("Select Validations")
    colA, colB = st.columns(2)
    with colA:
        run_store = st.checkbox("Store Level Validation", value=True)
        run_item = st.checkbox("Item Level Validation", value=True)
    with colB:
        run_compare_existing = st.checkbox("Compare Store List", value=True)
        run_summary = st.checkbox("Summary (requires Item)", value=True)
        run_file_review_existing = st.checkbox("File Review Report", value=False)

    if st.button("Validate", use_container_width=True, type="primary"):
        _execute_validation(
            prod_paths, test_paths, prod_type, test_type,
            prod_delim, test_delim,
            ctx.prod.eff_layout, ctx.test.eff_layout,
            prod_start_line, test_start_line, prod_record_type, test_record_type,
            prod_store_col, prod_units_col, prod_price_col, prod_upc_col, prod_desc_col,
            test_store_col, test_units_col, test_price_col, test_upc_col, test_desc_col,
            ctx.prod.price_type, ctx.test.price_type,
            ctx.prod.implied_dollars, ctx.prod.implied_units,
            ctx.test.implied_dollars, ctx.test.implied_units,
            run_store, run_item, run_compare_existing, run_summary, run_file_review_existing,
        )

    if ctx.validation_done:
        _display_results()

    if st.button("Start Over", use_container_width=True):
        _reset_phase()
        st.rerun()


def _detect_and_set(file_paths, side_ctx: ProcessingContext, side_label: str = "", key_prefix: str = ""):
    if is_multiline_record(file_paths[0]):
        st.warning(f"Multi-line structured file detected ({side_label})")
        side_ctx.file_type = "multiline"
        hdr_prefixes = detect_hdr_prefix(file_paths[0])
        if hdr_prefixes:
            side_ctx.header_prefix = hdr_prefixes[0]
        else:
            side_ctx.header_prefix = None
    else:
        ftype, delim = detect_file_type(file_paths[0])
        if ftype == "delimited":
            st.success(f"Delimited ({delim})")
            side_ctx.file_type = "delimited"
            side_ctx.delimiter = delim
        else:
            st.warning("Fixed-width file")
            side_ctx.file_type = "fixed"
            layout_file = st.text_input(f"{side_label} Layout CSV", key=f"{key_prefix}_layout")
            if layout_file:
                layout_file = clean_path(layout_file)
                if os.path.exists(layout_file):
                    side_ctx.layout = load_layout(layout_file)
                    st.success("Layout loaded")


def _multiline_section(prod_paths, test_paths):
    ctx = st.session_state.ex_ctx
    st.subheader("Multiline Record Settings")
    mc1, mc2 = st.columns(2)

    with mc1:
        if ctx.prod.file_type == "multiline":
            st.markdown("**BAU Multiline**")
            raw_p = preview_raw(prod_paths, "multiline", n_rows=5)
            if not raw_p.is_empty():
                st.dataframe(raw_p.to_pandas(), height=150)
            _multiline_side_inputs(prod_paths, ctx.prod, "BAU", "prod")

    with mc2:
        if ctx.test.file_type == "multiline":
            st.markdown("**Test Multiline**")
            raw_t = preview_raw(test_paths, "multiline", n_rows=5)
            if not raw_t.is_empty():
                st.dataframe(raw_t.to_pandas(), height=150)
            _multiline_side_inputs(test_paths, ctx.test, "Test", "test")

    ml_delim = st.selectbox("Multiline Delimiter", [",", "|", "\t", ";"], index=0, key="existing_ml_delim")

    if st.button("Flatten Records", key="existing_flatten"):
        ctx.ml_delimiter = ml_delim
        if ctx.prod.file_type == "multiline":
            _store_ml_config(ctx.prod, "prod")
        if ctx.test.file_type == "multiline":
            _store_ml_config(ctx.test, "test")
        st.rerun()

    if ctx.prod.ml_flattened or ctx.test.ml_flattened:
        _flattened_preview_and_schema(prod_paths, test_paths, ml_delim)

    return ml_delim


def _multiline_side_inputs(file_paths, side_ctx: ProcessingContext, side_label: str = "", key_prefix: str = ""):
    if side_ctx.header_prefix:
        hp = side_ctx.header_prefix
        st.info(f"HDR prefix: **{hp}**")
        hf = st.text_input(f"{side_label} Header Layout CSV", key=f"ex_hdr_header_file_{key_prefix}")
        df = st.text_input(f"{side_label} Detail Layout CSV", key=f"ex_hdr_detail_file_{key_prefix}")
        if hf and os.path.exists(clean_path(hf)):
            side_ctx.header_layout = load_layout(clean_path(hf))
            st.success("Header layout ready")
        if df and os.path.exists(clean_path(df)):
            side_ctx.detail_layout = load_layout(clean_path(df))
            st.success("Detail layout ready")
    else:
        detected = detect_record_types(file_paths[0])
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


def _flattened_preview_and_schema(prod_paths, test_paths, ml_delim):
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
                )
            else:
                fp = preview_flattened_multiline(prod_paths, ctx.prod.ml_record_types or [], ml_delim, n_rows=10)
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
                )
            else:
                fp = preview_flattened_multiline(test_paths, ctx.test.ml_record_types or [], ml_delim, n_rows=10)
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
                )
            else:
                fp = preview_flattened_multiline(prod_paths, ctx.prod.ml_record_types or [], ml_delim, n_rows=5)
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
                )
            else:
                fp = preview_flattened_multiline(test_paths, ctx.test.ml_record_types or [], ml_delim, n_rows=5)
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
                           prod_record_type, test_record_type):
    if prod_paths and test_paths and prod_type and test_type:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("BAU Preview")
            pv = preview_raw(prod_paths, prod_type, prod_delim or ",", prod_layout_list,
                              n_rows=10, start_line=prod_start_line, record_type=prod_record_type)
            if not pv.is_empty():
                st.table(pv.to_pandas().iloc[:10, :10].astype(str))
        with c2:
            st.subheader("Test Preview")
            tv = preview_raw(test_paths, test_type, test_delim or ",", test_layout_list,
                              n_rows=10, start_line=test_start_line, record_type=test_record_type)
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
):
    ctx = st.session_state.ex_ctx

    if not any([run_store, run_item, run_compare_existing, run_summary]):
        st.warning("Please select at least one validation option")
        st.stop()

    ctx.compare_result = None
    ctx.store_df = None
    ctx.comparison_df = None
    ctx.summary_df = None

    ml_delim_val = ctx.ml_delimiter

    hdr_prefix_prod, hdr_header_prod = _get_hdr_params(ctx.prod)
    hdr_prefix_test, hdr_header_test = _get_hdr_params(ctx.test)

    eff_layout_prod = ctx.prod.eff_layout or prod_layout_list
    eff_layout_test = ctx.test.eff_layout or test_layout_list

    prod_store_agg = ctx.prod.store_agg
    test_store_agg = ctx.test.store_agg
    prod_item_agg = ctx.prod.item_agg
    test_item_agg = ctx.test.item_agg

    if run_store:
        with ProcessingTimer(ctx.metrics, "validation", "storelevelvalidation"):
            store_df = storelevelvalidation(
                prod_paths, test_paths, prod_type, test_type,
                prod_delim, test_delim, eff_layout_prod, eff_layout_test,
                prod_store_col, prod_units_col, prod_price_col,
                test_store_col, test_units_col, test_price_col,
                price_type_bau, price_type_test,
                isimplied_dollars_prod, isimplied_units_prod,
                isimplied_dollars_test, isimplied_units_test,
                start_line=prod_start_line, record_type=prod_record_type,
                multiline_record_types=ctx.prod.ml_record_types if prod_type == "multiline" and not hdr_prefix_prod else None,
                multiline_delimiter=ml_delim_val, column_names=ctx.prod.schema,
                header_prefix=hdr_prefix_prod or hdr_prefix_test,
                header_layout=hdr_header_prod or hdr_header_test,
                prod_summary=prod_store_agg, test_summary=test_store_agg,
            )
        ctx.store_df = store_df

    if run_item:
        with ProcessingTimer(ctx.metrics, "validation", "run_item_validation"):
            comparison_df, summary_df = run_item_validation(
                prod_paths, test_paths, prod_type, test_type,
                prod_delim, test_delim, eff_layout_prod, eff_layout_test,
                prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
                implied_units_bau=isimplied_units_prod,
                implied_dollars_bau=isimplied_dollars_prod,
                implied_units_test=isimplied_units_test,
                implied_dollars_test=isimplied_dollars_test,
                start_line=prod_start_line, record_type=prod_record_type,
                multiline_record_types=ctx.prod.ml_record_types if prod_type == "multiline" and not hdr_prefix_prod else None,
                multiline_delimiter=ml_delim_val, column_names=ctx.prod.schema,
                header_prefix=hdr_prefix_prod or hdr_prefix_test,
                header_layout=hdr_header_prod or hdr_header_test,
                bau_summary=prod_item_agg, test_summary=test_item_agg,
            )
        ctx.comparison_df = comparison_df
        ctx.summary_df = summary_df

    if run_compare_existing:
        _compare_stores(
            prod_store_col=prod_store_col, prod_units_col=prod_units_col, prod_price_col=prod_price_col,
            test_store_col=test_store_col, test_units_col=test_units_col, test_price_col=test_price_col,
            prod_store_agg=prod_store_agg, test_store_agg=test_store_agg,
        )

    if run_file_review_existing:
        with ProcessingTimer(ctx.metrics, "report", "generate_file_reviews"):
            _generate_file_reviews(
                prod_paths, test_paths, prod_type, test_type,
                prod_delim, test_delim, eff_layout_prod, eff_layout_test,
                prod_start_line, test_start_line, prod_record_type, test_record_type,
                prod_store_col, prod_upc_col, prod_units_col, prod_price_col,
                test_store_col, test_upc_col, test_units_col, test_price_col,
                price_type_bau, price_type_test,
                isimplied_dollars_prod, isimplied_units_prod,
                isimplied_dollars_test, isimplied_units_test,
                hdr_prefix_prod, hdr_prefix_test,
                hdr_header_prod, hdr_header_test,
            )

    ctx.validation_done = True
    st.rerun()


def _compare_stores(
    prod_store_col, prod_units_col, prod_price_col,
    test_store_col, test_units_col, test_price_col,
    prod_store_agg=None, test_store_agg=None,
):
    ctx = st.session_state.ex_ctx

    if prod_store_agg is not None:
        prod_series = prod_store_agg.select(["STORE_NUMBER"])
    else:
        with ProcessingTimer(ctx.metrics, "aggregation", "BAU stream_store_aggregate (compare)"):
            prod_series = stream_store_aggregate(
                ctx.prod.file_paths, ctx.prod.file_type,
                prod_store_col, prod_units_col, prod_price_col,
                delimiter=ctx.prod.delimiter, layout=ctx.prod.layout,
                start_line=st.session_state.get("fw_start_prod", 0),
                record_type=st.session_state.get("fw_rec_prod", ""),
                multiline_record_types=ctx.prod.ml_record_types if ctx.prod.file_type == "multiline" and not ctx.prod.header_prefix else None,
                multiline_delimiter=ctx.ml_delimiter, column_names=ctx.prod.schema,
                header_prefix=ctx.prod.header_prefix,
                header_layout=ctx.prod.header_layout,
            ).select(["STORE_NUMBER"])

    if test_store_agg is not None:
        test_series = test_store_agg.select(["STORE_NUMBER"])
    else:
        with ProcessingTimer(ctx.metrics, "aggregation", "Test stream_store_aggregate (compare)"):
            test_series = stream_store_aggregate(
                ctx.test.file_paths, ctx.test.file_type,
                test_store_col, test_units_col, test_price_col,
                delimiter=ctx.test.delimiter, layout=ctx.test.layout,
                start_line=st.session_state.get("fw_start_test", 0),
                record_type=st.session_state.get("fw_rec_test", ""),
                multiline_record_types=ctx.test.ml_record_types if ctx.test.file_type == "multiline" and not ctx.test.header_prefix else None,
                multiline_delimiter=ctx.ml_delimiter, column_names=ctx.test.schema,
                header_prefix=ctx.test.header_prefix,
                header_layout=ctx.test.header_layout,
            ).select(["STORE_NUMBER"])

    if not prod_series.is_empty() and not test_series.is_empty():
        result = compare_files(
            prod_series.to_series().to_frame("store"),
            test_series.to_series().to_frame("store"), "store", "store",
        )
    else:
        result = {"missing_in_test": "", "missing_in_prod": ""}
    ctx.compare_result = result


def _generate_file_reviews(
    prod_paths, test_paths, prod_type, test_type,
    prod_delim, test_delim, prod_layout_list, test_layout_list,
    prod_start_line, test_start_line, prod_record_type, test_record_type,
    prod_store_col, prod_upc_col, prod_units_col, prod_price_col,
    test_store_col, test_upc_col, test_units_col, test_price_col,
    price_type_bau, price_type_test,
    isimplied_dollars_prod, isimplied_units_prod,
    isimplied_dollars_test, isimplied_units_test,
    hdr_prefix_prod=None, hdr_prefix_test=None,
    hdr_header_prod=None, hdr_header_test=None,
):
    ctx = st.session_state.ex_ctx

    with ProcessingTimer(ctx.metrics, "report", "BAU generate_file_review"):
        fr_prod = generate_file_review(
            prod_paths, prod_type, prod_store_col, prod_upc_col,
            prod_units_col, prod_price_col,
            delimiter=prod_delim, layout=prod_layout_list,
            price_type=price_type_bau,
            implied_dollars=isimplied_dollars_prod,
            implied_units=isimplied_units_prod,
            start_line=prod_start_line, record_type=prod_record_type,
            multiline_record_types=ctx.prod.ml_record_types if prod_type == "multiline" and not hdr_prefix_prod else None,
            multiline_delimiter=ctx.ml_delimiter, column_names=ctx.prod.schema,
            header_prefix=hdr_prefix_prod,
            header_layout=hdr_header_prod,
        )
    with ProcessingTimer(ctx.metrics, "report", "Test generate_file_review"):
        fr_test = generate_file_review(
            test_paths, test_type, test_store_col, test_upc_col,
            test_units_col, test_price_col,
            delimiter=test_delim, layout=test_layout_list,
            price_type=price_type_test,
            implied_dollars=isimplied_dollars_test,
            implied_units=isimplied_units_test,
            start_line=test_start_line, record_type=test_record_type,
            multiline_record_types=ctx.test.ml_record_types if test_type == "multiline" and not hdr_prefix_test else None,
            multiline_delimiter=ctx.ml_delimiter, column_names=ctx.test.schema,
            header_prefix=hdr_prefix_test,
            header_layout=hdr_header_test,
        )
    ctx.fr_prod = fr_prod
    ctx.fr_test = fr_test


def _display_results():
    ctx = st.session_state.ex_ctx
    with st.expander("Validation Results", expanded=True):
        if ctx.compare_result is not None:
            st.subheader("Store Compare")
            res = ctx.compare_result
            st.write(f"Missing in Test: {res['missing_in_test']}")
            st.write(f"Missing in BAU: {res['missing_in_prod']}")

        if ctx.summary_df is not None:
            st.subheader("Summary")
            st.dataframe(ctx.summary_df.to_pandas())

        if ctx.store_df is not None:
            st.subheader("Store Validation")
            df = ctx.store_df
            if df is not None and not df.is_empty():
                st.dataframe(df.to_pandas().head(100))
                st.download_button("Download Store Validation", df.write_csv(), "store_validation.csv")

        if ctx.comparison_df is not None:
            st.subheader("Item Validation")
            df = ctx.comparison_df
            if df is not None and not df.is_empty():
                st.dataframe(df.to_pandas().head(100))
                st.download_button("Download Item Validation", df.write_csv(), "item_validation.csv")

        if ctx.fr_prod is not None or ctx.fr_test is not None:
            st.subheader("File Review Report")
            cc = st.columns(2)
            with cc[0]:
                fr = ctx.fr_prod
                if fr is not None and not fr.is_empty():
                    st.markdown("**BAU**")
                    st.dataframe(fr.to_pandas())
                    st.download_button("Download BAU File Review", fr.write_csv(), "bau_file_review.csv")
            with cc[1]:
                fr = ctx.fr_test
                if fr is not None and not fr.is_empty():
                    st.markdown("**Test**")
                    st.dataframe(fr.to_pandas())
                    st.download_button("Download Test File Review", fr.write_csv(), "test_file_review.csv")

    display_execution_summary(ctx.metrics)

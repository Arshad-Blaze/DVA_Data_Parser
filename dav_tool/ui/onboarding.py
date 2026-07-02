import os
import streamlit as st
import polars as pl
from dav_tool._parsers import (
    preview_raw, preview_flattened_multiline, preview_flattened_multiline_fixed,
    load_layout,
)
from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate
from dav_tool._reports import generate_file_review
from dav_tool._observability import ProcessingTimer, log_phase, setup_logging
from dav_tool.validation.store import compare_files
from dav_tool.detection import is_multiline_record, detect_file_type, detect_record_types, detect_hdr_prefix
from dav_tool.ui.helpers import clean_path, get_file_list, load_storelist, get_column_names, display_execution_summary, display_dev_diagnostics
from dav_tool.processing_context import ProcessingContext


def _reset_phase():
    st.session_state.onb_ctx = ProcessingContext()


def run():
    setup_logging()
    log_phase("Page Loaded — Onboarding")

    st.title("Onboarding")

    if "onb_ctx" not in st.session_state:
        st.session_state.onb_ctx = ProcessingContext()
    ctx = st.session_state.onb_ctx

    dev_mode = st.sidebar.checkbox("Developer Mode", key="onb_dev_mode")
    if dev_mode:
        display_dev_diagnostics(ctx)

    _phase0_parsing_and_preview(ctx)
    if ctx.phase >= 1:
        _phase1_column_mapping(ctx)
    if ctx.phase >= 2:
        _phase2_validation(ctx)


def _phase0_parsing_and_preview(ctx):
    st.markdown("### Phase 1: File Parsing & Preview")

    prod_txt = clean_path(st.text_input("Folder Path"))
    file_paths = get_file_list(prod_txt)
    file_type = None
    prod_delim = None
    layout_list = None
    start_line = 0
    record_type = None
    cols = []

    if prod_txt and file_paths:
        log_phase(f"Folder Selected — {prod_txt} ({len(file_paths)} files)")
        log_phase("Detection Started")
        if is_multiline_record(file_paths[0]):
            st.warning("Multi-line structured file detected")
            file_type = "multiline"
            _multiline_flow(file_paths)
        else:
            file_type, prod_delim = detect_file_type(file_paths[0])
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

    if file_type == "fixed" and layout_list and file_paths and not is_multiline_record(file_paths[0]):
        st.subheader("Fixed Width Settings")
        colA, colB = st.columns(2)
        with colA:
            start_line = st.number_input("Start Line", min_value=0, value=0)
        with colB:
            record_type = st.text_input("Record Type (e.g., U)", value="")

    if file_type and file_type != "multiline" and file_paths:
        st.subheader("Data Preview")
        df_preview = preview_raw(file_paths, file_type, prod_delim or ",", layout_list,
                                  n_rows=10, start_line=start_line, record_type=record_type)
        if not df_preview.is_empty():
            st.dataframe(df_preview.to_pandas().head(10))

    if file_type:
        log_phase(f"Detection Completed — {file_type}")

    if file_type and file_type == "multiline":
        if ctx.ml_flattened and ctx.schema:
            cols = ctx.schema
        else:
            cols = []
    elif file_type and file_paths:
        cols = get_column_names(file_paths, file_type, prod_delim or ",", layout_list,
                                 start_line, record_type)

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
        st.success(f"Parsing complete — {len(cols)} column(s) detected")
        if st.button("Proceed to Column Mapping  ->", use_container_width=True):
            ctx.file_paths = file_paths
            ctx.file_type = file_type
            ctx.delimiter = prod_delim
            ctx.layout = layout_list
            ctx.start_line = start_line
            ctx.record_type = record_type
            ctx.columns = cols
            ctx.phase = 1
            st.rerun()


def _phase1_column_mapping(ctx):
    st.divider()
    st.markdown("### Phase 2: Column Mapping")

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
    prod_store_col = st.selectbox("Retailer Store Column", cols)
    prod_upc_col = st.selectbox("UPC Column", cols)
    prod_desc_col = st.selectbox("Description Column", cols)
    prod_units_col = st.selectbox("Units Column", cols)
    prod_price_col = st.selectbox("Price Column", cols)

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

    if ctx.phase == 1:
        if st.button("Save Mapping & Proceed to Validation  ->", use_container_width=True):
            log_phase("Column Mapping Saved")
            ctx.store_col = prod_store_col
            ctx.upc_col = prod_upc_col
            ctx.desc_col = prod_desc_col
            ctx.units_col = prod_units_col
            ctx.price_col = prod_price_col
            ctx.storelist_path = storelist_path
            ctx.storelist_delim = storelist_delim
            ctx.storelist_store_col = storelist_store_col

            with ProcessingTimer(ctx.metrics, "aggregation", "stream_store_aggregate"):
                store_agg = stream_store_aggregate(
                    fp, ft, prod_store_col, prod_units_col, prod_price_col,
                    delimiter=pd, layout=ll,
                    start_line=sl, record_type=rt,
                    multiline_record_types=ctx.ml_record_types, multiline_delimiter=ctx.ml_delimiter,
                    column_names=ctx.schema,
                    header_prefix=ctx.header_prefix, header_layout=ctx.header_layout,
                )
            with ProcessingTimer(ctx.metrics, "aggregation", "stream_item_aggregate"):
                item_agg = stream_item_aggregate(
                    fp, ft,
                    prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
                    delimiter=pd, layout=ll,
                    start_line=sl, record_type=rt,
                    multiline_record_types=ctx.ml_record_types, multiline_delimiter=ctx.ml_delimiter,
                    column_names=ctx.schema,
                    header_prefix=ctx.header_prefix, header_layout=ctx.header_layout,
                )

            ctx.store_agg = store_agg
            ctx.item_agg = item_agg
            ctx.phase = 2
            st.rerun()


def _phase2_validation(ctx):
    st.divider()
    st.markdown("### Phase 3: Validation")

    fp = ctx.file_paths
    ft = ctx.file_type
    pd = ctx.delimiter
    ll = ctx.layout
    sl = ctx.start_line
    rt = ctx.record_type
    cols = ctx.columns

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

    st.subheader("Select Validations")
    run_onb_compare = st.checkbox("Compare Store List", value=True)
    run_upc_summary = st.checkbox("Generate Unique UPC Summary", value=True)
    run_onb_file_review = st.checkbox("File Review Report", value=False)

    if st.button("Validate Onboarding", use_container_width=True, type="primary"):
        _run_validation(
            fp, ft, pd, ll, sl, rt, cols,
            storelist_path, storelist_delim, storelist_store_col,
            run_onb_compare, run_upc_summary, run_onb_file_review,
            prod_store_col, prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
            header_prefix=ctx.header_prefix,
            header_layout=ctx.header_layout,
        )

    if ctx.done:
        _display_results()

    if st.button("Start Over", use_container_width=True):
        _reset_phase()
        st.rerun()


def _multiline_flow(file_paths):
    hdr_prefixes = detect_hdr_prefix(file_paths[0])

    if hdr_prefixes:
        _hdr_fixed_flow(file_paths, hdr_prefixes)
    else:
        _delimited_ml_flow(file_paths)


def _delimited_ml_flow(file_paths):
    ctx = st.session_state.onb_ctx

    st.subheader("Raw Preview (with record-type prefixes)")
    raw_preview = preview_raw(file_paths, "multiline", n_rows=10)
    if not raw_preview.is_empty():
        st.dataframe(raw_preview.to_pandas())

    detected_types = detect_record_types(file_paths[0])
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
        _show_ml_preview_and_schema(file_paths)


def _hdr_fixed_flow(file_paths, hdr_prefixes):
    ctx = st.session_state.onb_ctx
    prefix = hdr_prefixes[0]
    st.warning(f"HDR fixed-width file detected (prefix: {prefix})")

    st.subheader("Raw Preview")
    raw_preview = preview_raw(file_paths, "multiline", n_rows=10)
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

    if st.button("Flatten Records", key="onb_hdr_flatten"):
        if hdr_header_layout and hdr_detail_layout:
            ctx.header_prefix = prefix
            ctx.header_layout = hdr_header_layout
            ctx.detail_layout = hdr_detail_layout
            ctx.ml_flattened = True
            st.rerun()

    if ctx.ml_flattened:
        _show_hdr_fixed_preview_and_schema(file_paths, prefix)


def _show_ml_preview_and_schema(file_paths):
    ctx = st.session_state.onb_ctx

    st.subheader("Flattened Preview")
    rt_list = ctx.ml_record_types
    flat_preview = preview_flattened_multiline(
        file_paths, rt_list, ctx.ml_delimiter, n_rows=10
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


def _show_hdr_fixed_preview_and_schema(file_paths, prefix):
    ctx = st.session_state.onb_ctx

    st.subheader("Flattened Preview")
    hdr_header_layout = ctx.header_layout
    hdr_detail_layout = ctx.detail_layout
    flat_preview = preview_flattened_multiline_fixed(
        file_paths, prefix, hdr_header_layout, hdr_detail_layout, n_rows=10
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
):
    ctx = st.session_state.onb_ctx
    log_phase("Validation Started")

    if not any([run_onb_compare, run_upc_summary]):
        st.warning("Select at least one validation")
        st.stop()

    if run_onb_compare:
        if not storelist_path:
            st.error("Store list file required")
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
            )
        ctx.file_review = fr
        log_phase("Reports Generated")

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

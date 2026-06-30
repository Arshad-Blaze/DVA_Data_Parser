import os
import streamlit as st
import polars as pl
from dav_tool._parsers import preview_raw, preview_flattened_multiline
from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate, generate_file_review
from dav_tool.validation.store import compare_files
from dav_tool.detection import is_multiline_record, detect_file_type, detect_record_types
from dav_tool.io import safe_read_csv
from dav_tool.ui.helpers import clean_path, get_file_list, load_storelist, get_column_names


def run():
    st.title("Onboarding")
    prod_txt = clean_path(st.text_input("Folder Path"))
    file_paths = get_file_list(prod_txt)
    file_type = None
    prod_delim = None
    prod_layout = None
    layout_list = None
    start_line = 0
    record_type = None

    if prod_txt and file_paths:
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
                    from dav_tool._parsers import load_layout
                    layout_file = clean_path(layout_file)
                    if os.path.exists(layout_file):
                        layout_list = load_layout(layout_file)
                        st.success("Layout loaded")

    if file_type == "fixed" and layout_list and not is_multiline_record(file_paths[0]):
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

    if file_type and file_type != "multiline":
        cols = get_column_names(file_paths, file_type, prod_delim or ",", layout_list,
                                 start_line, record_type)
    elif st.session_state.get("onb_ml_flattened"):
        cols = _get_onb_cols()
    else:
        st.stop()

    if file_type or st.session_state.get("onb_ml_flattened"):
        _validation_section(file_paths, file_type, prod_delim, layout_list,
                            start_line, record_type, cols)


def _multiline_flow(file_paths):
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
            st.session_state.onb_ml_rt = rt_list
            st.session_state.onb_ml_delim = ml_delim
            st.session_state.onb_ml_flattened = True
            st.rerun()

    if st.session_state.get("onb_ml_flattened"):
        st.subheader("Flattened Preview")
        rt_list = st.session_state.onb_ml_rt
        flat_preview = preview_flattened_multiline(
            file_paths, rt_list, st.session_state.onb_ml_delim, n_rows=10
        )
        if not flat_preview.is_empty():
            st.dataframe(flat_preview.to_pandas())
            st.session_state.onb_ml_delim = st.session_state.onb_ml_delim

        st.subheader("Define Column Schema")
        default_cols = flat_preview.columns
        schema_names = {}
        for i, col in enumerate(default_cols):
            schema_names[col] = st.text_input(
                f"Rename '{col}' to:", value=col, key=f"onb_schema_{i}"
            )
        if st.button("Apply Schema", key="onb_apply_schema"):
            st.session_state.onb_schema = list(schema_names.values())
            st.rerun()


def _get_onb_cols():
    if st.session_state.get("onb_schema"):
        return st.session_state.onb_schema
    return []


def _validation_section(file_paths, file_type, prod_delim, layout_list,
                        start_line, record_type, cols):
    st.subheader("Store List Input")
    storelist_path = st.text_input("Store List File Path")
    storelist_delim = st.selectbox("Store List Delimiter", [",", "|", "\t", ";"])

    st.subheader("Select Validations")
    run_onb_compare = st.checkbox("Compare Store List", value=True)
    run_upc_summary = st.checkbox("Generate Unique UPC Summary", value=True)
    run_onb_file_review = st.checkbox("File Review Report", value=False)

    if cols:
        prod_store_col = st.selectbox("Retailer Store Column", cols)
        prod_upc_col = st.selectbox("UPC Column", cols)
        prod_desc_col = st.selectbox("Description Column", cols)
        prod_units_col = st.selectbox("Units Column", cols)
        prod_price_col = st.selectbox("Price Column", cols)

    if run_onb_compare and storelist_path:
        storelist_df = load_storelist(storelist_path, storelist_delim)
        ext = os.path.splitext(storelist_path)[-1].lower()
        if ext not in [".xlsx", ".xls"]:
            storelist_delim = st.selectbox("Store List Delimiter", [",", "|", "\t", ";"],
                                            key="storelist_delim_sel")
            storelist_store_col = st.selectbox("Storelist Store Column", storelist_df.columns)
        else:
            st.dataframe(storelist_df.head(5))
            storelist_store_col = st.selectbox("Storelist Store Column", storelist_df.columns)

    if st.button("Validate Onboarding"):
        _run_validation(file_paths, file_type, prod_delim, layout_list,
                        start_line, record_type, cols,
                        storelist_path, storelist_delim, storelist_store_col,
                        run_onb_compare, run_upc_summary, run_onb_file_review)

    if st.session_state.get("onb_done"):
        _display_results()


def _run_validation(file_paths, file_type, prod_delim, layout_list,
                    start_line, record_type, cols,
                    storelist_path, storelist_delim, storelist_store_col,
                    run_onb_compare, run_upc_summary, run_onb_file_review):
    if not any([run_onb_compare, run_upc_summary]):
        st.warning("Select at least one validation")
        st.stop()

    ml_rt = st.session_state.get("onb_ml_rt")
    ml_delim = st.session_state.get("onb_ml_delim", "|")
    ml_schema = st.session_state.get("onb_schema")

    if run_onb_compare:
        if not storelist_path:
            st.error("Store list file required")
            st.stop()

        storelist_df = load_storelist(storelist_path, storelist_delim)

        prod_series = stream_store_aggregate(
            file_paths, file_type, prod_store_col, prod_units_col, prod_price_col,
            delimiter=prod_delim, layout=layout_list,
            start_line=start_line, record_type=record_type,
            multiline_record_types=ml_rt, multiline_delimiter=ml_delim,
            column_names=ml_schema,
        ).select(["STORE_NUMBER"])

        if not prod_series.is_empty():
            result = compare_files(
                prod_series.to_series().to_frame("store"),
                storelist_df.select([pl.col(storelist_store_col).alias("store")]),
                "store", "store"
            )
        else:
            result = {"missing_in_test": "", "missing_in_prod": ""}

        st.session_state.onb_compare = result

    if run_upc_summary:
        upc_summary = stream_item_aggregate(
            file_paths, file_type,
            prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
            delimiter=prod_delim, layout=layout_list,
            start_line=start_line, record_type=record_type,
            multiline_record_types=ml_rt, multiline_delimiter=ml_delim,
            column_names=ml_schema,
        )
        st.session_state.onb_upc = upc_summary

    if run_onb_file_review:
        fr = generate_file_review(
            file_paths, file_type, prod_store_col, prod_upc_col,
            prod_units_col, prod_price_col,
            delimiter=prod_delim, layout=layout_list,
            start_line=start_line, record_type=record_type,
            multiline_record_types=ml_rt, multiline_delimiter=ml_delim,
            column_names=ml_schema,
        )
        st.session_state.onb_file_review = fr

    st.session_state.onb_done = True
    st.rerun()


def _display_results():
    with st.expander("Onboarding Validation Results", expanded=True):
        if "onb_compare" in st.session_state:
            res = st.session_state.onb_compare
            st.write(f"Missing in Storelist: {res['missing_in_test']}")
            st.write(f"Missing in Retailer: {res['missing_in_prod']}")

        if "onb_upc" in st.session_state:
            df = st.session_state.onb_upc
            st.dataframe(df.head(100).to_pandas())
            st.download_button("Download UPC Summary", df.write_csv(), "upc_summary.csv")

        if "onb_file_review" in st.session_state:
            st.subheader("File Review Report")
            fr = st.session_state.onb_file_review
            if not fr.is_empty():
                st.dataframe(fr.to_pandas())
                st.download_button("Download File Review", fr.write_csv(), "file_review.csv")

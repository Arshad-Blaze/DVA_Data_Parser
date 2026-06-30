import os
import streamlit as st
import polars as pl
from dav_tool._parsers import (
    preview_raw, preview_flattened_multiline, load_layout,
)
from dav_tool._aggregators import (
    stream_store_aggregate, stream_item_aggregate, generate_file_review,
)
from dav_tool.validation.store import compare_files, storelevelvalidation
from dav_tool.validation.item import run_item_validation
from dav_tool.detection import (
    is_multiline_record, detect_file_type, detect_record_types, has_header,
)
from dav_tool.ui.helpers import clean_path, get_file_list, get_column_names


def run():
    st.title("Existing")
    col1, col2 = st.columns(2)

    prod_paths = []
    test_paths = []
    prod_type = test_type = None
    prod_delim = test_delim = None
    prod_layout_list = test_layout_list = None
    prod_start_line = test_start_line = 0
    prod_record_type = test_record_type = None

    with col1:
        st.header("BAU")
        prod_txt = clean_path(st.text_input("BAU Folder Path"))
        prod_file_paths = get_file_list(prod_txt)
        if prod_txt and prod_file_paths:
            _detect_and_set(prod_file_paths, "prod")

    with col2:
        st.header("Test")
        test_txt = clean_path(st.text_input("Test Folder Path"))
        test_file_paths = get_file_list(test_txt)
        if test_txt and test_file_paths:
            _detect_and_set(test_file_paths, "test")

    if st.session_state.get("prod_type") == "fixed" or st.session_state.get("test_type") == "fixed":
        st.subheader("Fixed Width Settings")
        colA, colB = st.columns(2)
        with colA:
            prod_start_line = st.number_input("BAU Start Line", min_value=0, value=0, key="fw_start_prod")
            prod_record_type = st.text_input("BAU Record Type", value="", key="fw_rec_prod")
        with colB:
            test_start_line = st.number_input("Test Start Line", min_value=0, value=0, key="fw_start_test")
            test_record_type = st.text_input("Test Record Type", value="", key="fw_rec_test")

    prod_type = st.session_state.get("prod_type")
    test_type = st.session_state.get("test_type")
    prod_delim = st.session_state.get("prod_delim")
    test_delim = st.session_state.get("test_delim")
    prod_layout_list = st.session_state.get("prod_layout_list")
    test_layout_list = st.session_state.get("test_layout_list")
    prod_paths = prod_file_paths
    test_paths = test_file_paths

    ml_delim = "|"

    if prod_type == "multiline" or test_type == "multiline":
        ml_delim = _multiline_section(prod_paths, test_paths, prod_type, test_type)

    if not (prod_type == "multiline" and test_type == "multiline"):
        _show_regular_previews(prod_paths, test_paths, prod_type, test_type,
                               prod_delim, test_delim, prod_layout_list, test_layout_list,
                               prod_start_line, test_start_line,
                               prod_record_type, test_record_type)

    _run_column_mapping_and_validation(
        prod_paths, test_paths, prod_type, test_type,
        prod_delim, test_delim, prod_layout_list, test_layout_list,
        prod_start_line, test_start_line, prod_record_type, test_record_type,
    )


def _detect_and_set(file_paths, prefix):
    if is_multiline_record(file_paths[0]):
        st.warning(f"Multi-line structured file detected ({prefix})")
        st.session_state[f"{prefix}_type"] = "multiline"
    else:
        ftype, delim = detect_file_type(file_paths[0])
        if ftype == "delimited":
            st.success(f"Delimited ({delim})")
            st.session_state[f"{prefix}_type"] = "delimited"
            st.session_state[f"{prefix}_delim"] = delim
        else:
            st.warning("Fixed-width file")
            st.session_state[f"{prefix}_type"] = "fixed"
            layout_file = st.text_input(f"{prefix.upper()} Layout CSV", key=f"{prefix}_layout")
            if layout_file:
                layout_file = clean_path(layout_file)
                if os.path.exists(layout_file):
                    st.session_state[f"{prefix}_layout_list"] = load_layout(layout_file)
                    st.success("Layout loaded")


def _multiline_section(prod_paths, test_paths, prod_type, test_type):
    st.subheader("Multiline Record Settings")
    mc1, mc2 = st.columns(2)

    with mc1:
        if prod_type == "multiline":
            st.markdown("**BAU Multiline**")
            raw_p = preview_raw(prod_paths, "multiline", n_rows=5)
            if not raw_p.is_empty():
                st.dataframe(raw_p.to_pandas(), height=150)
            detected_p = detect_record_types(prod_paths[0])
            rt_p_default = ",".join(detected_p) if detected_p else "H,D"
            ml_rt_prod = st.text_input("BAU Record Type Flags", value=rt_p_default, key="ml_rt_prod")

    with mc2:
        if test_type == "multiline":
            st.markdown("**Test Multiline**")
            raw_t = preview_raw(test_paths, "multiline", n_rows=5)
            if not raw_t.is_empty():
                st.dataframe(raw_t.to_pandas(), height=150)
            detected_t = detect_record_types(test_paths[0])
            rt_t_default = ",".join(detected_t) if detected_t else "H,D"
            ml_rt_test = st.text_input("Test Record Type Flags", value=rt_t_default, key="ml_rt_test")

    ml_delim = st.selectbox("Multiline Delimiter", [",", "|", "\t", ";"], index=0, key="existing_ml_delim")

    if st.button("Flatten Records", key="existing_flatten"):
        st.session_state.ex_ml_delim = ml_delim
        if prod_type == "multiline":
            st.session_state.ex_ml_rt_prod = [r.strip() for r in ml_rt_prod.split(",") if r.strip()]
        if test_type == "multiline":
            st.session_state.ex_ml_rt_test = [r.strip() for r in ml_rt_test.split(",") if r.strip()]
        st.session_state.ex_ml_flattened = True
        st.rerun()

    if st.session_state.get("ex_ml_flattened"):
        _flattened_preview_and_schema(prod_paths, test_paths, prod_type, test_type, ml_delim)

    return ml_delim


def _flattened_preview_and_schema(prod_paths, test_paths, prod_type, test_type, ml_delim):
    mc1, mc2 = st.columns(2)
    with mc1:
        st.subheader("BAU Flattened Preview")
        if prod_type == "multiline":
            rt_list = st.session_state.ex_ml_rt_prod
            fp = preview_flattened_multiline(prod_paths, rt_list, ml_delim, n_rows=10)
            if not fp.is_empty():
                st.dataframe(fp.to_pandas())
    with mc2:
        st.subheader("Test Flattened Preview")
        if test_type == "multiline":
            rt_list = st.session_state.ex_ml_rt_test
            fp = preview_flattened_multiline(test_paths, rt_list, ml_delim, n_rows=10)
            if not fp.is_empty():
                st.dataframe(fp.to_pandas())

    st.subheader("Define Column Schema")
    prod_schema = {}
    test_schema = {}
    sc1, sc2 = st.columns(2)
    with sc1:
        if prod_type == "multiline":
            rt_list = st.session_state.ex_ml_rt_prod
            fp = preview_flattened_multiline(prod_paths, rt_list, ml_delim, n_rows=5)
            if not fp.is_empty():
                st.markdown("**BAU Column Names**")
                for i, col in enumerate(fp.columns):
                    prod_schema[col] = st.text_input(
                        f"BAU '{col}' →", value=col, key=f"ex_schema_prod_{i}"
                    )
    with sc2:
        if test_type == "multiline":
            rt_list = st.session_state.ex_ml_rt_test
            fp = preview_flattened_multiline(test_paths, rt_list, ml_delim, n_rows=5)
            if not fp.is_empty():
                st.markdown("**Test Column Names**")
                for i, col in enumerate(fp.columns):
                    test_schema[col] = st.text_input(
                        f"Test '{col}' →", value=col, key=f"ex_schema_test_{i}"
                    )

    if st.button("Apply Schema", key="ex_apply_schema"):
        if prod_schema:
            st.session_state.ex_schema_prod = list(prod_schema.values())
        if test_schema:
            st.session_state.ex_schema_test = list(test_schema.values())
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


def _run_column_mapping_and_validation(
    prod_paths, test_paths, prod_type, test_type,
    prod_delim, test_delim, prod_layout_list, test_layout_list,
    prod_start_line, test_start_line, prod_record_type, test_record_type,
):
    eff_prod_type = (
        "multiline" if prod_type == "multiline" and st.session_state.get("ex_ml_flattened")
        else prod_type
    )
    eff_test_type = (
        "multiline" if test_type == "multiline" and st.session_state.get("ex_ml_flattened")
        else test_type
    )

    if not (prod_paths and test_paths and prod_type and test_type):
        return

    if prod_type == "multiline" and not st.session_state.get("ex_ml_flattened"):
        st.info("Click 'Flatten Records' above to proceed")
        st.stop()
    if test_type == "multiline" and not st.session_state.get("ex_ml_flattened"):
        st.info("Click 'Flatten Records' above to proceed")
        st.stop()

    ml_delim = st.session_state.get("ex_ml_delim", "|")
    eff_delim_prod = ml_delim if prod_type == "multiline" else (prod_delim or ",")
    eff_delim_test = ml_delim if test_type == "multiline" else (test_delim or ",")
    eff_rt_prod = (
        ",".join(st.session_state.get("ex_ml_rt_prod", []))
        if prod_type == "multiline" else prod_record_type
    )
    eff_rt_test = (
        ",".join(st.session_state.get("ex_ml_rt_test", []))
        if test_type == "multiline" else test_record_type
    )

    prod_cols = get_column_names(prod_paths, eff_prod_type, eff_delim_prod,
                                  prod_layout_list, prod_start_line, eff_rt_prod)
    test_cols = get_column_names(test_paths, eff_test_type, eff_delim_test,
                                  test_layout_list, test_start_line, eff_rt_test)

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

    st.subheader("Select Validations")
    colA, colB = st.columns(2)
    with colA:
        run_store = st.checkbox("Store Level Validation", value=True)
        run_item = st.checkbox("Item Level Validation", value=True)
    with colB:
        run_compare_existing = st.checkbox("Compare Store List", value=True)
        run_summary = st.checkbox("Summary (requires Item)", value=True)
        run_file_review_existing = st.checkbox("File Review Report", value=False)

    if st.button("Validate"):
        _execute_validation(
            prod_paths, test_paths, prod_type, test_type,
            prod_delim, test_delim, prod_layout_list, test_layout_list,
            prod_start_line, test_start_line, prod_record_type, test_record_type,
            prod_store_col, prod_units_col, prod_price_col, prod_upc_col, prod_desc_col,
            test_store_col, test_units_col, test_price_col, test_upc_col, test_desc_col,
            price_type_bau, price_type_test,
            isimplied_dollars_prod, isimplied_units_prod,
            isimplied_dollars_test, isimplied_units_test,
            run_store, run_item, run_compare_existing, run_summary, run_file_review_existing,
        )

    if st.session_state.get("validation_done", False):
        _display_results()


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
    if not any([run_store, run_item, run_compare_existing, run_summary]):
        st.warning("Please select at least one validation option")
        st.stop()

    for key in ["compare_result", "store_df", "comparison_df", "summary_df"]:
        if key in st.session_state:
            del st.session_state[key]

    ml_delim_val = st.session_state.get("ex_ml_delim", "|")
    ml_rt_prod = st.session_state.get("ex_ml_rt_prod")
    ml_rt_test = st.session_state.get("ex_ml_rt_test")
    ml_schema_prod = st.session_state.get("ex_schema_prod")
    ml_schema_test = st.session_state.get("ex_schema_test")

    if run_store:
        store_df = storelevelvalidation(
            prod_paths, test_paths, prod_type, test_type,
            prod_delim, test_delim, prod_layout_list, test_layout_list,
            prod_store_col, prod_units_col, prod_price_col,
            test_store_col, test_units_col, test_price_col,
            price_type_bau, price_type_test,
            isimplied_dollars_prod, isimplied_units_prod,
            isimplied_dollars_test, isimplied_units_test,
            start_line=prod_start_line, record_type=prod_record_type,
            multiline_record_types=ml_rt_prod if prod_type == "multiline" else None,
            multiline_delimiter=ml_delim_val, column_names=ml_schema_prod,
        )
        st.session_state.store_df = store_df

    if run_item:
        comparison_df, summary_df = run_item_validation(
            prod_paths, test_paths, prod_type, test_type,
            prod_delim, test_delim, prod_layout_list, test_layout_list,
            prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
            implied_units_bau=isimplied_units_prod,
            implied_dollars_bau=isimplied_dollars_prod,
            implied_units_test=isimplied_units_test,
            implied_dollars_test=isimplied_dollars_test,
            start_line=prod_start_line, record_type=prod_record_type,
            multiline_record_types=ml_rt_prod if prod_type == "multiline" else None,
            multiline_delimiter=ml_delim_val, column_names=ml_schema_prod,
        )
        st.session_state.comparison_df = comparison_df
        st.session_state.summary_df = summary_df

    if run_compare_existing:
        _compare_stores(
            prod_paths, test_paths, prod_type, test_type,
            prod_delim, test_delim, prod_layout_list, test_layout_list,
            prod_start_line, test_start_line, prod_record_type, test_record_type,
            prod_store_col, prod_units_col, prod_price_col,
            test_store_col, test_units_col, test_price_col,
            ml_delim_val, ml_rt_prod, ml_rt_test, ml_schema_prod, ml_schema_test,
        )

    if run_file_review_existing:
        _generate_file_reviews(
            prod_paths, test_paths, prod_type, test_type,
            prod_delim, test_delim, prod_layout_list, test_layout_list,
            prod_start_line, test_start_line, prod_record_type, test_record_type,
            prod_store_col, prod_upc_col, prod_units_col, prod_price_col,
            test_store_col, test_upc_col, test_units_col, test_price_col,
            price_type_bau, price_type_test,
            isimplied_dollars_prod, isimplied_units_prod,
            isimplied_dollars_test, isimplied_units_test,
            ml_delim_val, ml_rt_prod, ml_rt_test, ml_schema_prod, ml_schema_test,
        )

    st.session_state.validation_done = True
    st.rerun()


def _compare_stores(
    prod_paths, test_paths, prod_type, test_type,
    prod_delim, test_delim, prod_layout_list, test_layout_list,
    prod_start_line, test_start_line, prod_record_type, test_record_type,
    prod_store_col, prod_units_col, prod_price_col,
    test_store_col, test_units_col, test_price_col,
    ml_delim_val, ml_rt_prod, ml_rt_test, ml_schema_prod, ml_schema_test,
):
    prod_series = stream_store_aggregate(
        prod_paths, prod_type, prod_store_col, prod_units_col, prod_price_col,
        delimiter=prod_delim, layout=prod_layout_list,
        start_line=prod_start_line, record_type=prod_record_type,
        multiline_record_types=ml_rt_prod if prod_type == "multiline" else None,
        multiline_delimiter=ml_delim_val, column_names=ml_schema_prod,
    ).select(["STORE_NUMBER"])

    test_series = stream_store_aggregate(
        test_paths, test_type, test_store_col, test_units_col, test_price_col,
        delimiter=test_delim, layout=test_layout_list,
        start_line=test_start_line, record_type=test_record_type,
        multiline_record_types=ml_rt_test if test_type == "multiline" else None,
        multiline_delimiter=ml_delim_val, column_names=ml_schema_test,
    ).select(["STORE_NUMBER"])

    if not prod_series.is_empty() and not test_series.is_empty():
        result = compare_files(
            prod_series.to_series().to_frame("store"),
            test_series.to_series().to_frame("store"), "store", "store",
        )
    else:
        result = {"missing_in_test": "", "missing_in_prod": ""}
    st.session_state.compare_result = result


def _generate_file_reviews(
    prod_paths, test_paths, prod_type, test_type,
    prod_delim, test_delim, prod_layout_list, test_layout_list,
    prod_start_line, test_start_line, prod_record_type, test_record_type,
    prod_store_col, prod_upc_col, prod_units_col, prod_price_col,
    test_store_col, test_upc_col, test_units_col, test_price_col,
    price_type_bau, price_type_test,
    isimplied_dollars_prod, isimplied_units_prod,
    isimplied_dollars_test, isimplied_units_test,
    ml_delim_val, ml_rt_prod, ml_rt_test, ml_schema_prod, ml_schema_test,
):
    fr_prod = generate_file_review(
        prod_paths, prod_type, prod_store_col, prod_upc_col,
        prod_units_col, prod_price_col,
        delimiter=prod_delim, layout=prod_layout_list,
        price_type=price_type_bau,
        implied_dollars=isimplied_dollars_prod,
        implied_units=isimplied_units_prod,
        start_line=prod_start_line, record_type=prod_record_type,
        multiline_record_types=ml_rt_prod if prod_type == "multiline" else None,
        multiline_delimiter=ml_delim_val, column_names=ml_schema_prod,
    )
    fr_test = generate_file_review(
        test_paths, test_type, test_store_col, test_upc_col,
        test_units_col, test_price_col,
        delimiter=test_delim, layout=test_layout_list,
        price_type=price_type_test,
        implied_dollars=isimplied_dollars_test,
        implied_units=isimplied_units_test,
        start_line=test_start_line, record_type=test_record_type,
        multiline_record_types=ml_rt_test if test_type == "multiline" else None,
        multiline_delimiter=ml_delim_val, column_names=ml_schema_test,
    )
    st.session_state.fr_prod = fr_prod
    st.session_state.fr_test = fr_test


def _display_results():
    with st.expander("Validation Results", expanded=True):
        if "compare_result" in st.session_state:
            st.subheader("Store Compare")
            res = st.session_state.compare_result
            st.write(f"Missing in Test: {res['missing_in_test']}")
            st.write(f"Missing in BAU: {res['missing_in_prod']}")

        if "summary_df" in st.session_state:
            st.subheader("Summary")
            st.dataframe(st.session_state.summary_df.to_pandas())

        if "store_df" in st.session_state:
            st.subheader("Store Validation")
            df = st.session_state.store_df
            if df is not None and not df.is_empty():
                st.dataframe(df.to_pandas().head(100))
                st.download_button("Download Store Validation", df.write_csv(), "store_validation.csv")

        if "comparison_df" in st.session_state:
            st.subheader("Item Validation")
            df = st.session_state.comparison_df
            if df is not None and not df.is_empty():
                st.dataframe(df.to_pandas().head(100))
                st.download_button("Download Item Validation", df.write_csv(), "item_validation.csv")

        if "fr_prod" in st.session_state or "fr_test" in st.session_state:
            st.subheader("File Review Report")
            cc = st.columns(2)
            with cc[0]:
                fr = st.session_state.get("fr_prod")
                if fr is not None and not fr.is_empty():
                    st.markdown("**BAU**")
                    st.dataframe(fr.to_pandas())
                    st.download_button("Download BAU File Review", fr.write_csv(), "bau_file_review.csv")
            with cc[1]:
                fr = st.session_state.get("fr_test")
                if fr is not None and not fr.is_empty():
                    st.markdown("**Test**")
                    st.dataframe(fr.to_pandas())
                    st.download_button("Download Test File Review", fr.write_csv(), "test_file_review.csv")

import time
import polars as pl
from dav_tool._aggregators import stream_store_aggregate
from dav_tool.validation._utils import _pct_expr


def compare_files(prod_file, test_file, col1, col2):
    prod_store = prod_file[col1]
    test_store = test_file[col2]

    prod_unique = (
        prod_store.drop_nulls().cast(pl.Utf8).str.strip_chars()
        .str.to_lowercase().unique()
    )
    test_unique = (
        test_store.drop_nulls().cast(pl.Utf8).str.strip_chars()
        .str.to_lowercase().unique()
    )

    s1 = set(prod_unique.to_list())
    s2 = set(test_unique.to_list())

    return {
        "missing_in_test": ", ".join(sorted(s1 - s2)),
        "missing_in_prod": ", ".join(sorted(s2 - s1)),
    }


def _compare_store_summaries(prod_summary, test_summary):
    """Compare two store-level aggregated DataFrames and produce diff columns.

    prod_summary and test_summary must have canonical columns:
    STORE_NUMBER (str), Units (f64), Totalprice (f64).
    """
    if prod_summary.is_empty() and test_summary.is_empty():
        return pl.DataFrame()

    merged = prod_summary.join(
        test_summary, on="STORE_NUMBER", how="full", suffix="_Test"
    ).fill_null(0)

    rename_map = {}
    if "Units" in merged.columns:
        rename_map["Units"] = "Units_Prod"
    if "Totalprice" in merged.columns:
        rename_map["Totalprice"] = "Totalprice_Prod"
    if rename_map:
        merged = merged.rename(rename_map)

    for col_name in ["Units_Prod", "Totalprice_Prod", "Units_Test", "Totalprice_Test"]:
        if col_name not in merged.columns:
            merged = merged.with_columns(pl.lit(0.0).alias(col_name))

    merged = merged.with_columns([
        (pl.col("Units_Prod") - pl.col("Units_Test")).alias("Units_Diff"),
        (pl.col("Totalprice_Prod") - pl.col("Totalprice_Test")).alias("Sales_Diff"),
        _pct_expr("Units_Prod", "Units_Test").alias("Units_Diff_%"),
        _pct_expr("Totalprice_Prod", "Totalprice_Test").alias("Sales_Diff_%"),
    ])

    return merged.sort("STORE_NUMBER")


def storelevelvalidation(
    prod_paths, test_paths,
    prod_type, test_type,
    prod_delim, test_delim,
    prod_layout, test_layout,
    prod_store_col, prod_units_col, prod_price_col,
    test_store_col, test_units_col, test_price_col,
    price_type_bau, price_type_test,
    isimplied_dollars_prod, isimplied_units_prod,
    isimplied_dollars_test, isimplied_units_test,
    start_line=0, record_type=None,
    multiline_record_types=None, multiline_delimiter="|",
    column_names=None, header_prefix=None, header_layout=None,
    prod_summary=None, test_summary=None,
):
    start_time = time.time()

    if prod_summary is None:
        prod_summary = stream_store_aggregate(
            prod_paths, prod_type,
            prod_store_col, prod_units_col, prod_price_col,
            delimiter=prod_delim, layout=prod_layout,
            price_type=price_type_bau,
            implied_dollars=isimplied_dollars_prod,
            implied_units=isimplied_units_prod,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix,
            header_layout=header_layout,
        )

    if test_summary is None:
        test_summary = stream_store_aggregate(
            test_paths, test_type,
            test_store_col, test_units_col, test_price_col,
            delimiter=test_delim, layout=test_layout,
            price_type=price_type_test,
            implied_dollars=isimplied_dollars_test,
            implied_units=isimplied_units_test,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix,
            header_layout=header_layout,
        )

    result = _compare_store_summaries(prod_summary, test_summary)
    print(f"Time taken for store level validation {time.time() - start_time}")
    return result


def storelevelvalidation_from_df(prod_df, test_df):
    """Validate store-level data from canonical DataFrames.

    prod_df and test_df must already have canonical columns:
    STORE_NUMBER (str), Units (f64), Totalprice (f64).
    """
    prod_summary = prod_df.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])
    test_summary = test_df.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])
    return _compare_store_summaries(prod_summary, test_summary)
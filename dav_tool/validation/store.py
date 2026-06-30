import time
import polars as pl
from dav_tool._aggregators import stream_store_aggregate


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
    column_names=None,
):
    start_time = time.time()

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
    )

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
    )

    if prod_summary.is_empty() and test_summary.is_empty():
        print(f"Time taken for store level validation {time.time() - start_time}")
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

    print(f"Time taken for store level validation {time.time() - start_time}")
    return merged.sort("STORE_NUMBER")


def _pct_expr(base, comp):
    return (
        pl.when((pl.col(base) == 0) & (pl.col(comp) == 0)).then(0.0)
        .when(pl.col(base) == 0).then(-100.0)
        .when(pl.col(comp) == 0).then(100.0)
        .otherwise((pl.col(base) - pl.col(comp)) / pl.col(base) * 100)
    )


def storelevelvalidation_from_df(
    prod_df, test_df,
    prod_store_col, prod_units_col, prod_price_col,
    test_store_col, test_units_col, test_price_col,
    price_type_bau, price_type_test,
    isimplied_dollars_prod, isimplied_units_prod,
    isimplied_dollars_test, isimplied_units_test,
):
    start_time = time.time()

    prod = prod_df.rename({
        prod_store_col: "STORE_NUMBER",
        prod_units_col: "Units",
        prod_price_col: "Totalprice",
    })
    test = test_df.rename({
        test_store_col: "STORE_NUMBER",
        test_units_col: "Units",
        test_price_col: "Totalprice",
    })

    prod = prod.with_columns([
        pl.col("Units").cast(pl.Float64).fill_null(0),
        pl.col("Totalprice").cast(pl.Float64).fill_null(0),
    ])
    test = test.with_columns([
        pl.col("Units").cast(pl.Float64).fill_null(0),
        pl.col("Totalprice").cast(pl.Float64).fill_null(0),
    ])

    if isimplied_dollars_prod:
        prod = prod.with_columns(pl.col("Totalprice") / 100)
    if isimplied_units_prod:
        prod = prod.with_columns(pl.col("Units") / 100)
    if isimplied_dollars_test:
        test = test.with_columns(pl.col("Totalprice") / 100)
    if isimplied_units_test:
        test = test.with_columns(pl.col("Units") / 100)

    if price_type_bau == "Unit Price":
        prod = prod.with_columns((pl.col("Units") * pl.col("Totalprice")).alias("Totalprice"))
    if price_type_test == "Unit Price":
        test = test.with_columns((pl.col("Units") * pl.col("Totalprice")).alias("Totalprice"))

    prod_summary = prod.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])
    test_summary = test.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])

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

    print(f"Time taken for store level validation {time.time() - start_time}")
    return merged.sort("STORE_NUMBER")
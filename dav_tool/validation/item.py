import time
import polars as pl
from dav_tool._aggregators import stream_item_aggregate


def run_item_validation(
    bau_paths, test_paths,
    bau_type, test_type,
    bau_delim, test_delim,
    bau_layout, test_layout,
    upc_col, desc_col, units_col, dollars_col,
    implied_units_bau=False, implied_dollars_bau=False,
    implied_units_test=False, implied_dollars_test=False,
    start_line=0, record_type=None,
    multiline_record_types=None, multiline_delimiter="|",
    column_names=None, header_prefix=None, header_layout=None,
):
    start_time = time.time()

    bau_summary = stream_item_aggregate(
        bau_paths, bau_type,
        upc_col, desc_col, units_col, dollars_col,
        delimiter=bau_delim, layout=bau_layout,
        implied_units=implied_units_bau,
        implied_dollars=implied_dollars_bau,
        start_line=start_line, record_type=record_type,
        multiline_record_types=multiline_record_types,
        multiline_delimiter=multiline_delimiter,
        column_names=column_names,
        header_prefix=header_prefix,
        header_layout=header_layout,
    )

    test_summary = stream_item_aggregate(
        test_paths, test_type,
        upc_col, desc_col, units_col, dollars_col,
        delimiter=test_delim, layout=test_layout,
        implied_units=implied_units_test,
        implied_dollars=implied_dollars_test,
        start_line=start_line, record_type=record_type,
        multiline_record_types=multiline_record_types,
        multiline_delimiter=multiline_delimiter,
        column_names=column_names,
        header_prefix=header_prefix,
        header_layout=header_layout,
    )

    comparison = create_comparison(bau_summary, test_summary)
    summary = comparison.group_by("Present In").agg([
        pl.sum("Units Difference"),
        pl.sum("Dollar Difference"),
    ]).sort("Present In")

    print(f"Time taken for item validation {time.time() - start_time}")
    return comparison, summary


def _pct_expr(base, comp):
    return (
        pl.when((pl.col(base) == 0) & (pl.col(comp) == 0)).then(0.0)
        .when(pl.col(base) == 0).then(-100.0)
        .when(pl.col(comp) == 0).then(100.0)
        .otherwise((pl.col(base) - pl.col(comp)) / pl.col(base) * 100)
    )


def create_comparison(bau_df, test_df):
    bau = bau_df.rename({"UNITS_SOLD": "BAU Units", "TOTAL_DOLLARS": "BAU Dollars"})
    test = test_df.rename({"UNITS_SOLD": "TEST Units", "TOTAL_DOLLARS": "TEST Dollars"})

    df = bau.join(test, on=["UPC_CODE", "PRODUCT_DESCRIPTION"], how="full")

    df = df.with_columns([
        pl.when(pl.col("BAU Units").is_null() & pl.col("TEST Units").is_not_null())
        .then(pl.lit("Present only in TEST"))
        .when(pl.col("TEST Units").is_null() & pl.col("BAU Units").is_not_null())
        .then(pl.lit("Present only in BAU"))
        .otherwise(pl.lit("Present in Both"))
        .alias("Present In")
    ])

    for col in ["BAU Units", "TEST Units", "BAU Dollars", "TEST Dollars"]:
        df = df.with_columns(pl.col(col).cast(pl.Float64).fill_null(0.0))

    df = df.with_columns([
        (pl.col("BAU Units") - pl.col("TEST Units")).alias("Units Difference"),
        (pl.col("BAU Dollars") - pl.col("TEST Dollars")).alias("Dollar Difference"),
        _pct_expr("BAU Units", "TEST Units").alias("Unit % Difference"),
        _pct_expr("BAU Dollars", "TEST Dollars").alias("Dollar % Difference"),
    ])

    return df

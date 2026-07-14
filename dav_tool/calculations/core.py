"""Pure calculation primitives for the Calculation Engine.

Every function here is a pure function on Polars DataFrames/expressions.
No file I/O, no aggregation, no parsing.
"""

from typing import List, Optional
import polars as pl


def pct_diff(base_col: str, comp_col: str) -> pl.Expr:
    """Percentage difference: (base - comp) / base * 100.

    Handles zero-division:
    - Both zero → 0.0
    - Only base zero → -100.0
    - Only comp zero → 100.0
    """
    return (
        pl.when((pl.col(base_col) == 0) & (pl.col(comp_col) == 0)).then(0.0)
        .when(pl.col(base_col) == 0).then(-100.0)
        .when(pl.col(comp_col) == 0).then(100.0)
        .otherwise((pl.col(base_col) - pl.col(comp_col)) / pl.col(base_col) * 100)
    )


def abs_diff(a_col: str, b_col: str, result_col: str) -> pl.Expr:
    """Absolute difference: a - b."""
    return (pl.col(a_col) - pl.col(b_col)).alias(result_col)


def classify_presence(
    bau_col: str,
    test_col: str,
    result_col: str = "Present In",
    bau_label: str = "Present only in BAU",
    test_label: str = "Present only in TEST",
    both_label: str = "Present in Both",
) -> pl.Expr:
    """Classify rows by presence across BAU and TEST columns.

    A row is 'only in BAU' if BAU column has a value but TEST is null,
    'only in TEST' if TEST has a value but BAU is null,
    'in Both' if both have values.
    """
    return (
        pl.when(pl.col(bau_col).is_null() & pl.col(test_col).is_not_null())
        .then(pl.lit(test_label))
        .when(pl.col(test_col).is_null() & pl.col(bau_col).is_not_null())
        .then(pl.lit(bau_label))
        .otherwise(pl.lit(both_label))
        .alias(result_col)
    )


def full_join_with_coalesce(
    left_df: pl.DataFrame,
    right_df: pl.DataFrame,
    on: list,
    suffix: str = "_Test",
    fill_value: float = 0.0,
) -> pl.DataFrame:
    """Full outer join with null-fill and rename collision handling.

    Fill only applies to non-key columns to avoid corrupting key columns.
    """
    merged = left_df.join(right_df, on=on, how="full", suffix=suffix)
    value_cols = [c for c in merged.columns if c not in on]
    merged = merged.with_columns([pl.col(c).fill_null(fill_value) for c in value_cols])
    return merged


def store_diffs(
    prod_summary: pl.DataFrame,
    test_summary: pl.DataFrame,
) -> pl.DataFrame:
    """Compute store-level differences between prod and test summaries.

    Both inputs must have canonical columns:
    STORE_NUMBER (str), Units (f64), Totalprice (f64).

    Returns a DataFrame with columns:
    STORE_NUMBER, Units_Prod, Totalprice_Prod, Units_Test, Totalprice_Test,
    Units_Diff, Sales_Diff, Units_Diff_%, Sales_Diff_%
    """
    if prod_summary.is_empty() and test_summary.is_empty():
        return pl.DataFrame()

    merged = full_join_with_coalesce(prod_summary, test_summary, on=["STORE_NUMBER"])

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
        pct_diff("Units_Prod", "Units_Test").alias("Units_Diff_%"),
        pct_diff("Totalprice_Prod", "Totalprice_Test").alias("Sales_Diff_%"),
    ])

    return merged.sort("STORE_NUMBER")


def item_comparison(
    bau_df: pl.DataFrame,
    test_df: pl.DataFrame,
) -> pl.DataFrame:
    """Compute item-level comparison between BAU and test summaries.

    Both inputs must have canonical columns:
    UPC_CODE (str), PRODUCT_DESCRIPTION (str), UNITS_SOLD (f64), TOTAL_DOLLARS (f64).

    Returns a DataFrame with columns:
    UPC_CODE, PRODUCT_DESCRIPTION, BAU Units, TEST Units, BAU Dollars, TEST Dollars,
    Present In, Units Difference, Dollar Difference, Unit % Difference, Dollar % Difference.
    """
    bau = bau_df.rename({"UNITS_SOLD": "BAU Units", "TOTAL_DOLLARS": "BAU Dollars"})
    test = test_df.rename({"UNITS_SOLD": "TEST Units", "TOTAL_DOLLARS": "TEST Dollars"})

    df = bau.join(test, on=["UPC_CODE", "PRODUCT_DESCRIPTION"], how="full")

    df = df.with_columns(
        classify_presence("BAU Units", "TEST Units")
    )

    for col in ["BAU Units", "TEST Units", "BAU Dollars", "TEST Dollars"]:
        df = df.with_columns(pl.col(col).cast(pl.Float64).fill_null(0.0))

    df = df.with_columns([
        (pl.col("BAU Units") - pl.col("TEST Units")).alias("Units Difference"),
        (pl.col("BAU Dollars") - pl.col("TEST Dollars")).alias("Dollar Difference"),
        pct_diff("BAU Units", "TEST Units").alias("Unit % Difference"),
        pct_diff("BAU Dollars", "TEST Dollars").alias("Dollar % Difference"),
    ])

    return df


def item_summary(comparison_df: pl.DataFrame) -> pl.DataFrame:
    """Group an item comparison DataFrame by presence and sum the differences.

    Returns a DataFrame with columns: Present In, Units Difference, Dollar Difference.
    """
    return comparison_df.group_by("Present In").agg([
        pl.sum("Units Difference"),
        pl.sum("Dollar Difference"),
    ]).sort("Present In")


def sort_by_diff(
    df: pl.DataFrame,
    sort_col: str = "Units_Diff_%",
    ascending: bool = False,
) -> pl.DataFrame:
    """Sort a comparison DataFrame by a difference column.

    Defaults to descending by percentage difference.
    """
    return df.sort(sort_col, descending=not ascending)


def rank_by_diff(
    df: pl.DataFrame,
    rank_col: str = "Units_Diff_%",
    rank_name: str = "Rank",
    ascending: bool = False,
) -> pl.DataFrame:
    """Rank rows by a difference column (1 = largest difference).

    Defaults to ranking from largest percentage difference downward.
    """
    return df.with_columns(
        pl.col(rank_col).rank(descending=not ascending).cast(pl.Int32).alias(rank_name)
    )


def apply_tolerance(
    df: pl.DataFrame,
    diff_col: str = "Units_Diff_%",
    tolerance: float = 5.0,
    status_col: str = "Status",
    pass_label: str = "Pass",
    fail_label: str = "Fail",
) -> pl.DataFrame:
    """Classify rows as Pass or Fail based on a tolerance threshold.

    |diff_col| <= tolerance → Pass, otherwise Fail.
    """
    return df.with_columns(
        pl.when(pl.col(diff_col).abs() <= tolerance)
        .then(pl.lit(pass_label))
        .otherwise(pl.lit(fail_label))
        .alias(status_col)
    )

"""Operation Comparison Service — compares BAU vs Test aggregation results.

Pure logic, no Streamlit, no UI.
"""
from dataclasses import dataclass
from typing import Optional

import polars as pl


@dataclass
class OperationComparison:
    prod_store_count: int = 0
    test_store_count: int = 0
    prod_item_count: int = 0
    test_item_count: int = 0
    prod_total_units: float = 0.0
    test_total_units: float = 0.0
    prod_total_dollars: float = 0.0
    test_total_dollars: float = 0.0

    @property
    def store_count_diff(self) -> int:
        return self.prod_store_count - self.test_store_count

    @property
    def item_count_diff(self) -> int:
        return self.prod_item_count - self.test_item_count


def compare_operations(
    prod_store_agg: Optional[pl.DataFrame],
    test_store_agg: Optional[pl.DataFrame],
    prod_item_agg: Optional[pl.DataFrame],
    test_item_agg: Optional[pl.DataFrame],
) -> OperationComparison:
    """Compare aggregation results between BAU and Test.

    Args:
        prod_store_agg: BAU store-level aggregation result.
        test_store_agg: Test store-level aggregation result.
        prod_item_agg: BAU item-level aggregation result.
        test_item_agg: Test item-level aggregation result.

    Returns:
        OperationComparison with counts and totals.
    """
    return OperationComparison(
        prod_store_count=prod_store_agg.height if prod_store_agg is not None and not prod_store_agg.is_empty() else 0,
        test_store_count=test_store_agg.height if test_store_agg is not None and not test_store_agg.is_empty() else 0,
        prod_item_count=prod_item_agg.height if prod_item_agg is not None and not prod_item_agg.is_empty() else 0,
        test_item_count=test_item_agg.height if test_item_agg is not None and not test_item_agg.is_empty() else 0,
        prod_total_units=float(prod_item_agg["UNITS_SOLD"].sum()) if prod_item_agg is not None and "UNITS_SOLD" in prod_item_agg.columns else 0.0,
        test_total_units=float(test_item_agg["UNITS_SOLD"].sum()) if test_item_agg is not None and "UNITS_SOLD" in test_item_agg.columns else 0.0,
        prod_total_dollars=round(float(prod_item_agg["TOTAL_DOLLARS"].sum()), 2) if prod_item_agg is not None and "TOTAL_DOLLARS" in prod_item_agg.columns else 0.0,
        test_total_dollars=round(float(test_item_agg["TOTAL_DOLLARS"].sum()), 2) if test_item_agg is not None and "TOTAL_DOLLARS" in test_item_agg.columns else 0.0,
    )

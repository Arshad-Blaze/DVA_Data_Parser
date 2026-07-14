"""Operation Comparison Service — compares BAU vs Test aggregation results.

Pure logic, no Streamlit, no UI.
"""
from dataclasses import dataclass
from typing import Optional


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


def compare_operations(
    prod_store_agg,
    test_store_agg,
    prod_item_agg,
    test_item_agg,
) -> OperationComparison:
    """Compare aggregation results between BAU and Test."""
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

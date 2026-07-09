"""Calculation Engine — Pure calculation functions on canonical DataFrames.

Contains no file I/O, no parsing, no aggregation.
Every function accepts canonical-summary DataFrames and returns transformed DataFrames.
"""

from dav_tool.calculations.core import (
    pct_diff,
    abs_diff,
    classify_presence,
    full_join_with_coalesce,
    store_diffs,
    item_comparison,
    item_summary,
    sort_by_diff,
    rank_by_diff,
    apply_tolerance,
)

__all__ = [
    "pct_diff",
    "abs_diff",
    "classify_presence",
    "full_join_with_coalesce",
    "store_diffs",
    "item_comparison",
    "item_summary",
    "sort_by_diff",
    "rank_by_diff",
    "apply_tolerance",
]

"""Item-level validation — orchestrates aggregation and calculation.

Aggregation Engine (``_aggregators``) handles parsing → normalization → group-by → sum.
Calculation Engine (``calculations``) handles diff, pct-diff, and comparison.

This module only wires them together and accepts pre-computed summaries.
"""

import logging
import time
import polars as pl
from dav_tool.calculations import item_comparison, item_summary

logger = logging.getLogger(__name__)


def run_item_validation(
    bau_paths=None, test_paths=None,
    bau_type=None, test_type=None,
    bau_delim=None, test_delim=None,
    bau_layout=None, test_layout=None,
    upc_col=None, desc_col=None, units_col=None, dollars_col=None,
    implied_units_bau=False, implied_dollars_bau=False,
    implied_units_test=False, implied_dollars_test=False,
    start_line=0, record_type=None,
    multiline_record_types=None, multiline_delimiter="|",
    column_names=None, header_prefix=None, header_layout=None,
    trailer_prefix=None, trailer_layout=None,
    bau_summary=None, test_summary=None,
    aggregation_source=None,
):
    """Orchestrate item-level validation.

    Requires pre-computed summaries (``bau_summary``, ``test_summary``).
    The Operation Layer guarantees these are always provided — no fallback
    aggregation is performed here.

    The comparison is computed by the Calculation Engine (``item_comparison``).
    """
    start_time = time.time()

    if bau_summary is None:
        raise ValueError(
            "run_item_validation requires bau_summary — "
            "pre-computed by the Operation Layer. "
            "Validation must not perform aggregation."
        )
    if test_summary is None:
        raise ValueError(
            "run_item_validation requires test_summary — "
            "pre-computed by the Operation Layer. "
            "Validation must not perform aggregation."
        )

    comparison = create_comparison(bau_summary, test_summary)
    summary = item_summary(comparison)

    logger.info("Item validation completed in %.3fs", time.time() - start_time)
    return comparison, summary


def create_comparison(bau_df, test_df):
    """Compare BAU vs Test item summaries.

    Delegates to the Calculation Engine (``item_comparison``).
    """
    return item_comparison(bau_df, test_df)

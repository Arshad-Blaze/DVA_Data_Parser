"""Item-level validation — orchestrates aggregation and calculation.

Aggregation Engine (``_aggregators``) handles parsing → normalization → group-by → sum.
Calculation Engine (``calculations``) handles diff, pct-diff, and comparison.

This module only wires them together and accepts pre-computed summaries.
"""

import logging
import time
import polars as pl
from dav_tool._aggregators import stream_item_aggregate
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

    Accepts optional pre-computed summaries. When not provided,
    delegates to the Aggregation Engine (``stream_item_aggregate``).
    The comparison is computed by the Calculation Engine (``item_comparison``).
    """
    start_time = time.time()

    if bau_summary is None:
        from dav_tool._aggregators import stream_item_aggregate
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
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
            source=aggregation_source,
        )

    if test_summary is None:
        from dav_tool._aggregators import stream_item_aggregate
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
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
            source=aggregation_source,
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

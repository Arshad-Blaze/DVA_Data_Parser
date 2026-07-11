"""Store-level validation — orchestrates aggregation and calculation.

Aggregation Engine (``_aggregators``) handles parsing → normalization → group-by → sum.
Calculation Engine (``calculations``) handles diff, pct-diff, and comparison.

This module only wires them together and accepts pre-computed summaries.
"""

import logging
import time
import polars as pl
from dav_tool._aggregators import stream_store_aggregate
from dav_tool.calculations import store_diffs

logger = logging.getLogger(__name__)


def compare_files(prod_file, test_file, col1, col2):
    """Compare two DataFrames by a single column and return missing sets."""
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

    Delegates to ``dav_tool.calculations.store_diffs``.
    """
    return store_diffs(prod_summary, test_summary)


def storelevelvalidation(
    prod_paths=None, test_paths=None,
    prod_type=None, test_type=None,
    prod_delim=None, test_delim=None,
    prod_layout=None, test_layout=None,
    prod_store_col=None, prod_units_col=None, prod_price_col=None,
    test_store_col=None, test_units_col=None, test_price_col=None,
    price_type_bau="Total Price", price_type_test="Total Price",
    isimplied_dollars_prod=False, isimplied_units_prod=False,
    isimplied_dollars_test=False, isimplied_units_test=False,
    start_line=0, record_type=None,
    multiline_record_types=None, multiline_delimiter="|",
    column_names=None, header_prefix=None, header_layout=None,
    trailer_prefix=None, trailer_layout=None,
    prod_summary=None, test_summary=None,
    aggregation_source=None,
):
    """Orchestrate store-level validation.

    Accepts optional pre-computed summaries. When not provided,
    delegates to the Aggregation Engine (``stream_store_aggregate``).
    The comparison is computed by the Calculation Engine (``store_diffs``).
    """
    start_time = time.time()

    if prod_summary is None:
        from dav_tool._aggregators import stream_store_aggregate
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
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
            source=aggregation_source,
        )

    if test_summary is None:
        from dav_tool._aggregators import stream_store_aggregate
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
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
            source=aggregation_source,
        )

    result = _compare_store_summaries(prod_summary, test_summary)
    logger.info("Store level validation completed in %.3fs", time.time() - start_time)
    return result


def storelevelvalidation_from_df(
    prod_df, test_df,
    store_col: str = "STORE_NUMBER",
    units_col: str = "Units",
    price_col: str = "Totalprice",
):
    """Validate store-level data from canonical DataFrames.

    Aggregation is done here (simple group-by), comparison is delegated
    to the Calculation Engine.

    Column names default to the canonical names produced by the normalizer
    but can be overridden for non-standard DataFrames.
    """
    prod_summary = prod_df.group_by(store_col).agg([pl.sum(units_col), pl.sum(price_col)])
    test_summary = test_df.group_by(store_col).agg([pl.sum(units_col), pl.sum(price_col)])
    return _compare_store_summaries(prod_summary, test_summary)

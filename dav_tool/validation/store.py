"""Store-level validation — orchestrates aggregation and calculation.

Aggregation Engine (``_aggregators``) handles parsing → normalization → group-by → sum.
Calculation Engine (``calculations``) handles diff, pct-diff, and comparison.

This module only wires them together and accepts pre-computed summaries.
"""

import logging
import time
import polars as pl
from dav_tool.calculations import store_diffs
from dav_tool.operations.aggregate import AggregateOperation, AggregateOptions

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

    Requires pre-computed canonical summaries (``prod_summary``, ``test_summary``)
    with canonical column names (``STORE_NUMBER``, ``Units``, ``Totalprice``).
    The Operation Layer guarantees these are always provided — no fallback
    aggregation is performed here.

    Format-specific parameters (``prod_type``, ``prod_delim``, ``layout``, etc.)
    are UNUSED when pre-computed summaries are provided.  They exist only for
    backward compatibility with older callers and will be removed in a future
    RC.  All comparison logic uses canonical column names only.

    The comparison is computed by the Calculation Engine (``store_diffs``).
    """
    start_time = time.time()

    if prod_summary is None:
        raise ValueError(
            "storelevelvalidation requires prod_summary — "
            "pre-computed by the Operation Layer. "
            "Validation must not perform aggregation."
        )
    if test_summary is None:
        raise ValueError(
            "storelevelvalidation requires test_summary — "
            "pre-computed by the Operation Layer. "
            "Validation must not perform aggregation."
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

    Delegates aggregation to the Data Operations Framework,
    then passes summaries to the Calculation Engine for comparison.

    Column names default to the canonical names produced by the normalizer
    but can be overridden for non-standard DataFrames.
    """
    agg_op = AggregateOperation()
    agg_opts = AggregateOptions(
        group_by=[store_col],
        aggregations={units_col: "sum", price_col: "sum"},
    )

    prod_result = agg_op.execute(prod_df, agg_opts)
    if prod_result.errors:
        raise ValueError(f"Prod aggregation failed: {'; '.join(prod_result.errors)}")

    test_result = agg_op.execute(test_df, agg_opts)
    if test_result.errors:
        raise ValueError(f"Test aggregation failed: {'; '.join(test_result.errors)}")

    return _compare_store_summaries(prod_result.df, test_result.df)

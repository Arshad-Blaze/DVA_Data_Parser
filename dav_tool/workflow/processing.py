"""Processing Service — aggregation orchestration.

Moved from UI layer (onboarding.py:420-482, existing.py:598-706).
No Streamlit imports. No rendering. Pure processing logic.
"""
import logging
import time
from typing import Optional, Tuple

import polars as pl

from dav_tool.options import ParseOptions, ColumnMapping, AggregationOptions
from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate
from dav_tool._reports import generate_file_review
from dav_tool._observability import ProcessingMetrics, register_df, release_df
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)


def run_store_aggregation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run store-level aggregation. Returns (result_df, elapsed_seconds)."""
    t0 = time.perf_counter()
    try:
        result = stream_store_aggregate(
            file_paths,
            parse_opts.file_type,
            mapping.store,
            mapping.units,
            mapping.price,
            delimiter=parse_opts.delimiter,
            layout=parse_opts.layout,
            price_type=mapping.price_type,
            implied_dollars=mapping.implied_dollars,
            implied_units=mapping.implied_units,
            start_line=parse_opts.start_line,
            record_type=parse_opts.record_type,
            multiline_record_types=parse_opts.multiline_record_types,
            multiline_delimiter=parse_opts.multiline_delimiter,
            column_names=parse_opts.column_names,
            header_prefix=parse_opts.header_prefix,
            header_layout=parse_opts.header_layout,
            detail_layout=parse_opts.detail_layout,
            trailer_prefix=parse_opts.trailer_prefix,
            trailer_layout=parse_opts.trailer_layout,
            source=source,
        )
        register_df(result, "store_agg", owner="processing", phase="aggregation")
    except Exception:
        logger.exception("Store aggregation failed")
        raise
    elapsed = time.perf_counter() - t0
    return result, elapsed


def run_item_aggregation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run item-level aggregation. Returns (result_df, elapsed_seconds)."""
    t0 = time.perf_counter()
    try:
        result = stream_item_aggregate(
            file_paths,
            parse_opts.file_type,
            mapping.upc,
            mapping.description,
            mapping.units,
            mapping.price,
            delimiter=parse_opts.delimiter,
            layout=parse_opts.layout,
            implied_units=mapping.implied_units,
            implied_dollars=mapping.implied_dollars,
            start_line=parse_opts.start_line,
            record_type=parse_opts.record_type,
            multiline_record_types=parse_opts.multiline_record_types,
            multiline_delimiter=parse_opts.multiline_delimiter,
            column_names=parse_opts.column_names,
            header_prefix=parse_opts.header_prefix,
            header_layout=parse_opts.header_layout,
            detail_layout=parse_opts.detail_layout,
            trailer_prefix=parse_opts.trailer_prefix,
            trailer_layout=parse_opts.trailer_layout,
            source=source,
        )
        register_df(result, "item_agg", owner="processing", phase="aggregation")
    except Exception:
        logger.exception("Item aggregation failed")
        raise
    elapsed = time.perf_counter() - t0
    return result, elapsed


def run_file_review(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    precomputed_store_agg=None,
    precomputed_upc_summary=None,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run file review report generation. Returns (result_df, elapsed_seconds)."""
    t0 = time.perf_counter()
    try:
        result = generate_file_review(
            file_paths,
            parse_opts.file_type,
            mapping.store,
            mapping.upc,
            mapping.units,
            mapping.price,
            delimiter=parse_opts.delimiter,
            layout=parse_opts.layout,
            price_type=mapping.price_type,
            implied_dollars=mapping.implied_dollars,
            implied_units=mapping.implied_units,
            start_line=parse_opts.start_line,
            record_type=parse_opts.record_type,
            multiline_record_types=parse_opts.multiline_record_types,
            multiline_delimiter=parse_opts.multiline_delimiter,
            column_names=parse_opts.column_names,
            header_prefix=parse_opts.header_prefix,
            header_layout=parse_opts.header_layout,
            trailer_prefix=parse_opts.trailer_prefix,
            trailer_layout=parse_opts.trailer_layout,
            precomputed_store_agg=precomputed_store_agg,
            precomputed_upc_summary=precomputed_upc_summary,
            source=source,
        )
        register_df(result, "file_review", owner="processing", phase="report")
    except Exception:
        logger.exception("File review failed")
        raise
    elapsed = time.perf_counter() - t0
    return result, elapsed


def apply_implied_decimals(schema: dict, mapping: ColumnMapping) -> dict:
    """Apply implied decimal transformations to schema.

    This is the business logic that was previously in UI layer.

    Args:
        schema: Dict of column_name -> pl.Expr (will be modified)
        mapping: Column mapping with implied_dollars/implied_units flags

    Returns:
        Modified schema dict.
    """
    if mapping.implied_units and mapping.units in schema:
        schema[mapping.units] = pl.col(mapping.units) / 100
    if mapping.implied_dollars and mapping.price in schema:
        schema[mapping.price] = pl.col(mapping.price) / 100
    return schema

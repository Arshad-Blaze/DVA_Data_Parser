"""Processing Service — aggregation orchestration.

Consumes only CanonicalContext — never references physical schema or detection directly.
All file-format details are hidden behind ``canonical_chunk_stream()``.

Operation modes (OutputMode):
- RAW_REVIEW          — preview raw canonical data (no aggregation)
- AGGREGATE_ONLY      — store + item aggregation only
- AGGREGATE_CALCULATE — aggregation + statistics + calculations
- VALIDATE            — full pipeline with validation + reports
"""
import logging
import os
import time
from typing import Optional, Tuple, List

import polars as pl

from dav_tool.options import (
    ParseOptions, ColumnMapping, CanonicalContext,
)
from dav_tool._aggregators import (
    stream_store_aggregate, stream_item_aggregate,
)
from dav_tool._reports import generate_file_review
from dav_tool._observability import ProcessingMetrics, register_df, release_df
from dav_tool._parsers import canonical_chunk_stream
from dav_tool.datasource.base import IDataSource
from dav_tool.workflow.data_access import wrap_source, register_accessor, DataAccessor

logger = logging.getLogger(__name__)


def run_raw_review(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    n_rows: int = 100,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Preview raw canonical data without aggregation.

    Returns (preview_df, elapsed_seconds). The preview shows up to *n_rows*
    of canonical-named records from the first file.
    """
    accessor, file_paths = wrap_source(source, file_paths)
    source = accessor
    t0 = time.perf_counter()
    try:
        stream = canonical_chunk_stream(
            file_paths, parse_opts.file_type, parse_opts.layout,
            parse_opts.start_line, parse_opts.record_type,
            parse_opts.multiline_record_types, parse_opts.multiline_delimiter,
            parse_opts.header_prefix, parse_opts.header_layout,
            parse_opts.detail_layout,
            parse_opts.trailer_prefix, parse_opts.trailer_layout,
            source, parse_opts.delimiter,
            column_names=parse_opts.column_names,
            level="store",
            store_col=mapping.store, upc_col=mapping.upc,
            desc_col=mapping.description,
            units_col=mapping.units, price_col=mapping.price,
            price_type=mapping.price_type,
            implied_units=mapping.implied_units,
            implied_dollars=mapping.implied_dollars,
            quantity_type=mapping.quantity_type,
            weight_col=mapping.weight_col,
            weight_uom=mapping.weight_uom,
            weight_uom_col=mapping.weight_uom_col,
        )
        for chunk in stream:
            preview = chunk.head(n_rows)
            elapsed = time.perf_counter() - t0
            register_df(preview, "raw_review", owner="processing", phase="review")
            return preview, elapsed
        elapsed = time.perf_counter() - t0
        return pl.DataFrame(), elapsed
    except Exception:
        logger.exception("Raw review failed")
        raise


def run_store_aggregation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run store-level aggregation. Returns (result_df, elapsed_seconds).

    Accepts CanonicalContext for the canonical-aware path.
    """
    accessor, file_paths = wrap_source(source, file_paths)
    source = accessor
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
            quantity_type=mapping.quantity_type,
            weight_col=mapping.weight_col,
            weight_uom=mapping.weight_uom,
            weight_uom_col=mapping.weight_uom_col,
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
    """Run item-level aggregation. Returns (result_df, elapsed_seconds).

    Accepts CanonicalContext for the canonical-aware path.
    """
    accessor, file_paths = wrap_source(source, file_paths)
    source = accessor
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
            quantity_type=mapping.quantity_type,
            weight_col=mapping.weight_col,
            weight_uom=mapping.weight_uom,
            weight_uom_col=mapping.weight_uom_col,
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
    accessor, file_paths = wrap_source(source, file_paths)
    source = accessor
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
            quantity_type=mapping.quantity_type,
            weight_col=mapping.weight_col,
            weight_uom=mapping.weight_uom,
            weight_uom_col=mapping.weight_uom_col,
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

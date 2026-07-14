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
import time
from typing import Optional, Tuple

import polars as pl

from dav_tool.options import (
    ParseOptions, ColumnMapping,
)
from dav_tool._aggregators import (
    stream_store_aggregate, stream_item_aggregate,
)
from dav_tool._observability import register_df
from dav_tool.datasource.base import IDataSource
from dav_tool.workflow.data_access import wrap_source

logger = logging.getLogger(__name__)


def run_store_aggregation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run store-level aggregation. Returns (result_df, elapsed_seconds)."""
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
    """Run item-level aggregation. Returns (result_df, elapsed_seconds)."""
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

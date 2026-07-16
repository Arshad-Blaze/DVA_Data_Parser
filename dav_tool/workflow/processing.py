"""Processing Service — aggregation orchestration.

Consumes only CanonicalDataset — never references physical schema, file types,
delimiters, encodings, or any format-specific detail directly.

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
    aggregate_dataset,
)
from dav_tool._observability import register_df
from dav_tool.datasource.base import IDataSource
from dav_tool.workflow.canonical import CanonicalDataset
from dav_tool.workflow.data_access import wrap_source

logger = logging.getLogger(__name__)


def _aggregate_via_dataset(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    level: str,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Aggregate using CanonicalDataset — the canonical path.

    Processing never touches file-format details (CSV, delimiter, encoding,
    fixed-width, multiline, HDR).  The ``CanonicalDataset`` hides everything.
    """
    accessor, file_paths = wrap_source(source, file_paths)
    dataset_source = accessor
    t0 = time.perf_counter()
    try:
        dataset = CanonicalDataset.from_parse_options(
            file_paths, parse_opts, mapping, level, source=dataset_source,
        )
        result = aggregate_dataset(dataset, source=dataset_source)
        register_df(result, f"{level}_agg", owner="processing", phase="aggregation")
    except Exception:
        logger.exception(f"{level} aggregation failed")
        raise
    elapsed = time.perf_counter() - t0
    return result, elapsed


def run_store_aggregation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run store-level aggregation. Returns (result_df, elapsed_seconds)."""
    return _aggregate_via_dataset(
        file_paths, parse_opts, mapping, "store", source=source,
    )


def run_item_aggregation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    source: Optional[IDataSource] = None,
) -> Tuple[pl.DataFrame, float]:
    """Run item-level aggregation. Returns (result_df, elapsed_seconds)."""
    return _aggregate_via_dataset(
        file_paths, parse_opts, mapping, "item", source=source,
    )

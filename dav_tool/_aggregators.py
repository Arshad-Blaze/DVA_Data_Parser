"""Aggregation Engine — config-driven streaming aggregation.

Responsible for:
- Parsing files into chunks
- Normalizing to canonical columns
- Group-by and sum aggregation
- Merge-accumulate for chunked data

This engine accepts a data source, file paths, file type, and aggregation
configuration. It returns aggregated DataFrames.

No validation logic here. No UI rendering.
"""
import gc
import logging
from typing import List, Dict, Optional, Union

import polars as pl

from dav_tool._normalizer import (
    apply_column_names,
    store_normalize_exprs,
    normalize_store_chunk,
    item_normalize_exprs,
    normalize_item_chunk,
    upc_normalize_exprs,
    normalize_upc_chunk,
)
from dav_tool._parsers import (
    scan_delimited, parse_delimited_chunks,
    parse_fixed_width_chunks,
    flatten_multiline_chunks, flatten_multiline_fixed_width,
)
from dav_tool.datasource.base import IDataSource
from dav_tool.config import DEFAULT_CHUNK_SIZE

logger = logging.getLogger(__name__)


def aggregate(
    file_paths: Union[str, List[str]],
    file_type: str,
    level: str,
    store_col: Optional[str] = None,
    upc_col: Optional[str] = None,
    desc_col: Optional[str] = None,
    units_col: Optional[str] = None,
    price_col: Optional[str] = None,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    price_type: str = "Total Price",
    implied_dollars: bool = False,
    implied_units: bool = False,
    start_line: int = 0,
    record_type: Optional[str] = None,
    multiline_record_types: Optional[List[str]] = None,
    multiline_delimiter: str = "|",
    column_names: Optional[List[str]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    """Config-driven aggregation at one of three levels.

    *level* must be one of ``"store"``, ``"item"``, or ``"upc"``.

    This is the single entry point for the Aggregation Engine.
    It dispatches to the appropriate dedicated aggregator based on *level*.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if level == "store":
        return stream_store_aggregate(
            file_paths, file_type, store_col, units_col, price_col,
            delimiter=delimiter, layout=layout,
            price_type=price_type, implied_dollars=implied_dollars,
            implied_units=implied_units, start_line=start_line,
            record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix, header_layout=header_layout,
            detail_layout=detail_layout,
            trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
            source=source,
        )
    if level == "item":
        return stream_item_aggregate(
            file_paths, file_type, upc_col, desc_col, units_col, price_col,
            delimiter=delimiter, layout=layout,
            implied_units=implied_units, implied_dollars=implied_dollars,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix, header_layout=header_layout,
            detail_layout=detail_layout,
            trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
            source=source,
        )
    if level == "upc":
        return stream_upc_summary(
            file_paths, file_type, upc_col, units_col, price_col,
            delimiter=delimiter, layout=layout,
            implied_units=implied_units, implied_dollars=implied_dollars,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix, header_layout=header_layout,
            detail_layout=detail_layout,
            trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
            source=source,
        )

    raise ValueError(f"Unknown aggregation level: {level}")


def aggregate_with_config(
    file_paths: Union[str, List[str]],
    file_type: str,
    config,
    level: str,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    """Aggregate using a FormatConfig-like object with aggregation settings.

    Reads column mapping and price settings from *config*, which must have
    ``store_col``, ``upc_col``, ``desc_col``, ``units_col``, ``price_col``,
    ``price_type``, ``implied_dollars``, ``implied_units``, and any file
    format attributes (``delimiter``, ``layout``, ``start_line``, etc.).
    """
    return aggregate(
        file_paths, file_type, level,
        store_col=getattr(config, "store_col", None),
        upc_col=getattr(config, "upc_col", None),
        desc_col=getattr(config, "desc_col", None),
        units_col=getattr(config, "units_col", None),
        price_col=getattr(config, "price_col", None),
        delimiter=getattr(config, "delimiter", None),
        layout=getattr(config, "layout", None),
        price_type=getattr(config, "price_type", "Total Price"),
        implied_dollars=getattr(config, "implied_dollars", False),
        implied_units=getattr(config, "implied_units", False),
        start_line=getattr(config, "start_line", 0),
        record_type=getattr(config, "record_type", None),
        multiline_record_types=getattr(config, "ml_record_types", None),
        multiline_delimiter=getattr(config, "ml_delimiter", "|"),
        column_names=getattr(config, "schema", None),
        header_prefix=getattr(config, "header_prefix", None),
        header_layout=getattr(config, "header_layout", None),
        detail_layout=getattr(config, "detail_layout", None),
        trailer_prefix=getattr(config, "trailer_prefix", None),
        trailer_layout=getattr(config, "trailer_layout", None),
        source=source,
    )


def _merge_accumulate(
    aggs: List[pl.DataFrame],
    group_cols: List[str],
) -> pl.DataFrame:
    if not aggs:
        return pl.DataFrame()
    # Concat all per-chunk aggs and merge in one shot
    merged = pl.concat(aggs)
    aggs.clear()
    result = (
        merged
        .group_by(group_cols)
        .agg([pl.sum("Units"), pl.sum("Totalprice")])
    )
    del merged
    gc.collect()
    return result


def _merge_accumulate_item(
    aggs: List[pl.DataFrame],
) -> pl.DataFrame:
    if not aggs:
        return pl.DataFrame()
    merged = pl.concat(aggs)
    aggs.clear()
    result = (
        merged
        .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
        .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
    )
    del merged
    gc.collect()
    return result


def _merge_accumulate_upc(
    aggs: List[pl.DataFrame],
) -> pl.DataFrame:
    if not aggs:
        return pl.DataFrame()
    merged = pl.concat(aggs)
    aggs.clear()
    result = (
        merged
        .group_by("UPC")
        .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
    )
    del merged
    gc.collect()
    return result


def stream_store_aggregate(
    file_paths: Union[str, List[str]],
    file_type: str,
    store_col: str,
    units_col: str,
    price_col: str,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    price_type: str = "Total Price",
    implied_dollars: bool = False,
    implied_units: bool = False,
    start_line: int = 0,
    record_type: Optional[str] = None,
    multiline_record_types: Optional[List[str]] = None,
    multiline_delimiter: str = "|",
    column_names: Optional[List[str]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    can_use_fast_path = source is None or source.supports_direct_path

    if file_type == "delimited" and can_use_fast_path:
        lazy = scan_delimited(file_paths, delimiter, columns=[store_col, units_col, price_col])
        result = (
            lazy.with_columns(
                store_normalize_exprs(store_col, units_col, price_col,
                                       implied_units, implied_dollars, price_type)
            )
            .group_by("STORE_NUMBER")
            .agg([pl.sum("Units"), pl.sum("Totalprice")])
            .sort("STORE_NUMBER")
            .collect(engine="streaming")
        )
        del lazy
        gc.collect()
        return result

    aggs = []
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter,
                          header_prefix, header_layout,
                          detail_layout, trailer_prefix, trailer_layout,
                          source=source, delimiter=delimiter)

    for chunk in chunks:
        chunk = apply_column_names(chunk, column_names)
        if store_col not in chunk.columns:
            logger.warning("Skipping chunk: column '%s' not found (available: %s)", store_col, chunk.columns)
            del chunk
            continue

        c = normalize_store_chunk(chunk, store_col, units_col, price_col,
                                   implied_units, implied_dollars, price_type)
        del chunk
        agg = c.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])
        del c
        aggs.append(agg)

    result = _merge_accumulate(aggs, ["STORE_NUMBER"])
    del aggs[:]
    gc.collect()
    if not result.is_empty():
        return result.sort("STORE_NUMBER")
    return result


def stream_item_aggregate(
    file_paths: Union[str, List[str]],
    file_type: str,
    upc_col: str,
    desc_col: str,
    units_col: str,
    dollars_col: str,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    implied_units: bool = False,
    implied_dollars: bool = False,
    start_line: int = 0,
    record_type: Optional[str] = None,
    multiline_record_types: Optional[List[str]] = None,
    multiline_delimiter: str = "|",
    column_names: Optional[List[str]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    can_use_fast_path = source is None or source.supports_direct_path

    if file_type == "delimited" and can_use_fast_path:
        lazy = scan_delimited(file_paths, delimiter, columns=[upc_col, desc_col, units_col, dollars_col])
        result = (
            lazy.with_columns(
                item_normalize_exprs(upc_col, desc_col, units_col, dollars_col,
                                      implied_units, implied_dollars)
            )
            .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
            .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
            .sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
            .collect(engine="streaming")
        )
        del lazy
        gc.collect()
        return result

    aggs = []
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter,
                          header_prefix, header_layout,
                          detail_layout, trailer_prefix, trailer_layout,
                          source=source, delimiter=delimiter)

    for chunk in chunks:
        chunk = apply_column_names(chunk, column_names)
        if upc_col not in chunk.columns:
            logger.warning("Skipping chunk: column '%s' not found (available: %s)", upc_col, chunk.columns)
            del chunk
            continue

        c = normalize_item_chunk(chunk, upc_col, desc_col, units_col, dollars_col,
                                  implied_units, implied_dollars)
        del chunk
        agg = c.group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"]).agg(
            [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
        )
        del c
        aggs.append(agg)

    result = _merge_accumulate_item(aggs)
    del aggs[:]
    gc.collect()
    if not result.is_empty():
        return result.sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
    return result


def stream_upc_summary(
    file_paths: Union[str, List[str]],
    file_type: str,
    upc_col: str,
    units_col: str,
    dollars_col: str,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    implied_units: bool = False,
    implied_dollars: bool = False,
    start_line: int = 0,
    record_type: Optional[str] = None,
    multiline_record_types: Optional[List[str]] = None,
    multiline_delimiter: str = "|",
    column_names: Optional[List[str]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    can_use_fast_path = source is None or source.supports_direct_path

    if file_type == "delimited" and can_use_fast_path:
        lazy = scan_delimited(file_paths, delimiter, columns=[upc_col, units_col, dollars_col])
        result = (
            lazy.with_columns(
                upc_normalize_exprs(upc_col, units_col, dollars_col,
                                     implied_units, implied_dollars)
            )
            .group_by("UPC")
            .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
            .collect(engine="streaming")
        )
        del lazy
        gc.collect()
        return result

    aggs = []
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter,
                          header_prefix, header_layout,
                          detail_layout, trailer_prefix, trailer_layout,
                          source=source, delimiter=delimiter)

    for chunk in chunks:
        chunk = apply_column_names(chunk, column_names)
        if upc_col not in chunk.columns:
            logger.warning("Skipping chunk: column '%s' not found (available: %s)", upc_col, chunk.columns)
            del chunk
            continue

        c = normalize_upc_chunk(chunk, upc_col, units_col, dollars_col,
                                 implied_units, implied_dollars)
        del chunk
        agg = c.group_by("UPC").agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
        del c
        aggs.append(agg)

    result = _merge_accumulate_upc(aggs)
    del aggs[:]
    gc.collect()
    return result


def _iter_chunks(file_paths, file_type, layout, start_line,
                 record_type, multiline_record_types, multiline_delimiter,
                 header_prefix=None, header_layout=None,
                 detail_layout=None, trailer_prefix=None, trailer_layout=None,
                 source=None, delimiter=None):
    if file_type == "delimited":
        if source is not None:
            return parse_delimited_chunks(file_paths, delimiter, source=source)
        return parse_delimited_chunks(file_paths, delimiter)
    elif file_type == "fixed":
        return parse_fixed_width_chunks(file_paths, layout, start_line,
                                        record_type, source=source)
    elif file_type == "multiline":
        if header_prefix and header_layout:
            return flatten_multiline_fixed_width(
                file_paths, header_prefix, header_layout,
                detail_layout or layout or [],
                trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
                source=source,
            )
        rtypes = multiline_record_types or ["H", "D"]
        return flatten_multiline_chunks(file_paths, rtypes, multiline_delimiter,
                                        source=source)
    raise ValueError(f"Unsupported file type: {file_type}")

"""Aggregation Engine — canonical-stream aggregation.

Consumes ONLY ``canonical_chunk_stream`` (yields pre-normalized DataFrames)
and produces aggregated results via group-by + sum.

No file-format knowledge (delimiter, encoding, fixed-width, multiline, etc.)
escapes the ``canonical_chunk_stream`` boundary.

No validation logic here. No UI rendering.
"""
import gc
import logging
import time
from typing import Any, Dict, List, Optional, Union

import polars as pl

from dav_tool._observability import log_phase, print_memory_snapshot
from dav_tool._parsers import canonical_chunk_stream
from dav_tool.datasource.base import IDataSource

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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Any = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> pl.DataFrame:
    """Config-driven aggregation at one of three levels.

    *level* must be one of ``"store"``, ``"item"``, or ``"upc"``.

    This is the single entry point for the Aggregation Engine.
    Internally builds a canonical chunk stream and aggregates it.
    """
    log_phase(f"Aggregation — STARTED ({level})")
    t0 = time.time()
    print_memory_snapshot("BEFORE AGGREGATION")
    stream = canonical_chunk_stream(
        file_paths, file_type, layout, start_line, record_type,
        multiline_record_types, multiline_delimiter,
        header_prefix, header_layout, detail_layout,
        trailer_prefix, trailer_layout, source, delimiter,
        column_names=column_names,
        level=level,
        store_col=store_col, upc_col=upc_col, desc_col=desc_col,
        units_col=units_col, price_col=price_col,
        price_type=price_type,
        implied_units=implied_units, implied_dollars=implied_dollars,
        quantity_type=quantity_type, weight_col=weight_col,
        weight_uom=weight_uom, weight_uom_col=weight_uom_col,
        numeric_config=numeric_config,
        date_col=date_col, weight_qty_col=weight_qty_col,
        quantity_strategy=quantity_strategy, units_uom=units_uom,
        schema_template=schema_template,
    )

    if level == "store":
        result = _aggregate_store_stream(stream)
    elif level == "item":
        result = _aggregate_item_stream(stream)
    elif level == "upc":
        result = _aggregate_upc_stream(stream)
    else:
        raise ValueError(f"Unknown aggregation level: {level}")
    elapsed = time.time() - t0
    print_memory_snapshot("AFTER AGGREGATION")
    log_phase(f"Aggregation — COMPLETED ({level}, {elapsed:.2f}s, rows={len(result) if result is not None else 0})")
    return result


def aggregate_with_options(
    file_paths: Union[str, List[str]],
    parse_opts,
    mapping,
    level: str,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    """Aggregate using option objects — the new entry point.

    Unwraps ParseOptions + ColumnMapping and delegates to ``aggregate()``.
    """
    return aggregate(
        file_paths, parse_opts.file_type, level,
        store_col=mapping.store,
        upc_col=mapping.upc,
        desc_col=mapping.description,
        units_col=mapping.units,
        price_col=mapping.price,
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
        numeric_config=getattr(parse_opts, 'numeric_config', None),
        date_col=mapping.date_col,
        weight_qty_col=mapping.weight_qty_col,
        quantity_strategy=mapping.quantity_strategy,
        units_uom=mapping.units_uom,
        schema_template=mapping.schema_template,
    )


def aggregate_dataset(dataset, source: Optional[IDataSource] = None) -> pl.DataFrame:
    """Aggregate using a ``CanonicalDataset`` — format-agnostic path.

    Processing never touches file-format details.  The dataset provides
    pre-normalized canonical chunks; this function only groups and sums.
    """
    from dav_tool.workflow.canonical import CanonicalDataset
    if not isinstance(dataset, CanonicalDataset):
        raise TypeError("Expected a CanonicalDataset instance")
    stream = dataset.iter_chunks()
    level = dataset.level
    if level == "store":
        return _aggregate_store_stream(stream)
    if level == "item":
        return _aggregate_item_stream(stream)
    if level == "upc":
        return _aggregate_upc_stream(stream)
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
        quantity_type=getattr(config, "quantity_type", "units"),
        weight_col=getattr(config, "weight_col", None),
        weight_uom=getattr(config, "weight_uom", "lb"),
        weight_uom_col=getattr(config, "weight_uom_col", None),
        date_col=getattr(config, "date_col", None),
        weight_qty_col=getattr(config, "weight_qty_col", None),
        quantity_strategy=getattr(config, "quantity_strategy", "auto"),
        units_uom=getattr(config, "units_uom", None),
        schema_template=getattr(config, "schema_template", "minimal"),
    )


def _extra_agg_exprs(chunk: pl.DataFrame) -> List[pl.Expr]:
    """Build pass-through aggregation expressions for extra canonical columns."""
    extra = []
    for col_name in ("QuantityType", "UOM", "Date", "Brand", "Category"):
        if col_name in chunk.columns:
            extra.append(pl.first(col_name).alias(col_name))
    return extra


def _aggregate_store_stream(stream) -> pl.DataFrame:
    """Aggregate a canonical store-level chunk stream."""
    aggs = []
    for chunk in stream:
        if "STORE_NUMBER" not in chunk.columns:
            continue
        base_aggs = [pl.sum("Units"), pl.sum("Totalprice")]
        base_aggs.extend(_extra_agg_exprs(chunk))
        agg = chunk.group_by("STORE_NUMBER").agg(base_aggs)
        aggs.append(agg)
        del chunk

    if not aggs:
        return pl.DataFrame()

    merged = pl.concat(aggs)
    aggs.clear()
    base_aggs = [pl.sum("Units"), pl.sum("Totalprice")]
    extra_cols = [c for c in merged.columns if c in ("QuantityType", "UOM", "Date", "Brand", "Category")]
    for col_name in extra_cols:
        base_aggs.append(pl.first(col_name).alias(col_name))
    result = (
        merged
        .group_by("STORE_NUMBER")
        .agg(base_aggs)
        .sort("STORE_NUMBER")
    )
    del merged
    gc.collect()
    return result


def _aggregate_item_stream(stream) -> pl.DataFrame:
    """Aggregate a canonical item-level chunk stream."""
    aggs = []
    for chunk in stream:
        if "UPC_CODE" not in chunk.columns:
            continue
        base_aggs = [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
        base_aggs.extend(_extra_agg_exprs(chunk))
        agg = chunk.group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"]).agg(base_aggs)
        aggs.append(agg)
        del chunk

    if not aggs:
        return pl.DataFrame()

    merged = pl.concat(aggs)
    aggs.clear()
    base_aggs = [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
    extra_cols = [c for c in merged.columns if c in ("QuantityType", "UOM", "Date", "Brand", "Category")]
    for col_name in extra_cols:
        base_aggs.append(pl.first(col_name).alias(col_name))
    result = (
        merged
        .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
        .agg(base_aggs)
        .sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
    )
    del merged
    gc.collect()
    return result


def _aggregate_upc_stream(stream) -> pl.DataFrame:
    """Aggregate a canonical UPC-level chunk stream."""
    aggs = []
    for chunk in stream:
        if "UPC" not in chunk.columns:
            continue
        base_aggs = [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
        base_aggs.extend(_extra_agg_exprs(chunk))
        agg = chunk.group_by("UPC").agg(base_aggs)
        aggs.append(agg)
        del chunk

    if not aggs:
        return pl.DataFrame()

    merged = pl.concat(aggs)
    aggs.clear()
    base_aggs = [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
    extra_cols = [c for c in merged.columns if c in ("QuantityType", "UOM", "Date", "Brand", "Category")]
    for col_name in extra_cols:
        base_aggs.append(pl.first(col_name).alias(col_name))
    result = (
        merged
        .group_by("UPC")
        .agg(base_aggs)
        .sort("UPC")
    )
    del merged
    gc.collect()
    return result


def stream_store_aggregate(
    file_paths, file_type, store_col, units_col, price_col, **kwargs
) -> pl.DataFrame:
    """Backward-compatible store aggregation — delegates to canonical stream."""
    kwargs.update(store_col=store_col, units_col=units_col, price_col=price_col)
    return aggregate(file_paths, file_type, "store", **kwargs)


def stream_item_aggregate(
    file_paths, file_type, upc_col, desc_col, units_col, dollars_col, **kwargs
) -> pl.DataFrame:
    """Backward-compatible item aggregation — delegates to canonical stream."""
    kwargs.update(upc_col=upc_col, desc_col=desc_col,
                  units_col=units_col, price_col=dollars_col)
    return aggregate(file_paths, file_type, "item", **kwargs)


def stream_upc_summary(
    file_paths, file_type, upc_col, units_col, dollars_col, **kwargs
) -> pl.DataFrame:
    """Backward-compatible UPC summary — delegates to canonical stream."""
    kwargs.update(upc_col=upc_col, units_col=units_col, price_col=dollars_col)
    return aggregate(file_paths, file_type, "upc", **kwargs)

import logging

import polars as pl
from typing import List, Dict, Optional, Union

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
    scan_delimited, parse_fixed_width_chunks,
    flatten_multiline_chunks, flatten_multiline_fixed_width,
)

logger = logging.getLogger(__name__)



def _merge_accumulate(
    aggs: List[pl.DataFrame],
    group_cols: List[str],
) -> pl.DataFrame:
    if not aggs:
        return pl.DataFrame()
    return (
        pl.concat(aggs)
        .group_by(group_cols)
        .agg([pl.sum("Units"), pl.sum("Totalprice")])
    )


def _merge_accumulate_item(
    aggs: List[pl.DataFrame],
) -> pl.DataFrame:
    if not aggs:
        return pl.DataFrame()
    return (
        pl.concat(aggs)
        .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
        .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
    )


def _merge_accumulate_upc(
    aggs: List[pl.DataFrame],
) -> pl.DataFrame:
    if not aggs:
        return pl.DataFrame()
    return (
        pl.concat(aggs)
        .group_by("UPC")
        .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
    )


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
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if file_type == "delimited":
        lazy = scan_delimited(file_paths, delimiter, columns=[store_col, units_col, price_col])
        return (
            lazy.with_columns(
                store_normalize_exprs(store_col, units_col, price_col,
                                       implied_units, implied_dollars, price_type)
            )
            .group_by("STORE_NUMBER")
            .agg([pl.sum("Units"), pl.sum("Totalprice")])
            .sort("STORE_NUMBER")
            .collect(engine="streaming")
        )

    aggs = []
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter,
                          header_prefix, header_layout,
                          trailer_prefix, trailer_layout)

    for chunk in chunks:
        chunk = apply_column_names(chunk, column_names)
        if store_col not in chunk.columns:
            logger.warning("Skipping chunk: column '%s' not found (available: %s)", store_col, chunk.columns)
            continue

        c = normalize_store_chunk(chunk, store_col, units_col, price_col,
                                   implied_units, implied_dollars, price_type)
        agg = c.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])
        aggs.append(agg)

    result = _merge_accumulate(aggs, ["STORE_NUMBER"])
    if not result.is_empty():
        return result.sort("STORE_NUMBER")
    return pl.DataFrame()


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
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if file_type == "delimited":
        lazy = scan_delimited(file_paths, delimiter, columns=[upc_col, desc_col, units_col, dollars_col])
        return (
            lazy.with_columns(
                item_normalize_exprs(upc_col, desc_col, units_col, dollars_col,
                                      implied_units, implied_dollars)
            )
            .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
            .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
            .sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
            .collect(engine="streaming")
        )

    aggs = []
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter,
                          header_prefix, header_layout,
                          trailer_prefix, trailer_layout)

    for chunk in chunks:
        chunk = apply_column_names(chunk, column_names)
        if upc_col not in chunk.columns:
            logger.warning("Skipping chunk: column '%s' not found (available: %s)", upc_col, chunk.columns)
            continue

        c = normalize_item_chunk(chunk, upc_col, desc_col, units_col, dollars_col,
                                  implied_units, implied_dollars)
        agg = c.group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"]).agg(
            [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
        )
        aggs.append(agg)

    result = _merge_accumulate_item(aggs)
    if not result.is_empty():
        return result.sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
    return pl.DataFrame()


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
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if file_type == "delimited":
        lazy = scan_delimited(file_paths, delimiter, columns=[upc_col, units_col, dollars_col])
        return (
            lazy.with_columns(
                upc_normalize_exprs(upc_col, units_col, dollars_col,
                                     implied_units, implied_dollars)
            )
            .group_by("UPC")
            .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
            .collect(engine="streaming")
        )

    aggs = []
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter,
                          header_prefix, header_layout,
                          trailer_prefix, trailer_layout)

    for chunk in chunks:
        chunk = apply_column_names(chunk, column_names)
        if upc_col not in chunk.columns:
            logger.warning("Skipping chunk: column '%s' not found (available: %s)", upc_col, chunk.columns)
            continue

        c = normalize_upc_chunk(chunk, upc_col, units_col, dollars_col,
                                 implied_units, implied_dollars)
        agg = c.group_by("UPC").agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
        aggs.append(agg)

    result = _merge_accumulate_upc(aggs)
    if not result.is_empty():
        return result
    return pl.DataFrame()


def _iter_chunks(file_paths, file_type, layout, start_line,
                 record_type, multiline_record_types, multiline_delimiter,
                 header_prefix=None, header_layout=None,
                 trailer_prefix=None, trailer_layout=None):
    if file_type == "fixed":
        return parse_fixed_width_chunks(file_paths, layout, start_line, record_type)
    elif file_type == "multiline":
        if header_prefix and header_layout:
            return flatten_multiline_fixed_width(
                file_paths, header_prefix, header_layout, layout or [],
                trailer_prefix=trailer_prefix, trailer_layout=trailer_layout
            )
        rtypes = multiline_record_types or ["H", "D"]
        return flatten_multiline_chunks(file_paths, rtypes, multiline_delimiter)
    raise ValueError(f"Unsupported file type: {file_type}")

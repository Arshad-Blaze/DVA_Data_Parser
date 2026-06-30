import os
import polars as pl
from typing import List, Dict, Any, Optional, Union

from dav_tool._parsers import (
    safe_numeric, scan_delimited, parse_fixed_width_chunks,
    flatten_multiline_chunks,
)
from dav_tool.config import DEFAULT_CHUNK_SIZE


def _apply_numeric_units_dollars(
    df: pl.DataFrame,
    units_col: str,
    dollars_col: str,
    implied_units: bool = False,
    implied_dollars: bool = False,
    price_type: str = "Total Price",
) -> pl.DataFrame:
    u = safe_numeric(units_col).alias("Units")
    d = safe_numeric(dollars_col).alias("Totalprice")
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    if price_type == "Unit Price":
        d = pl.col("Units") * pl.col("Totalprice")
    return df.with_columns([u, d])


def _merge_accumulate(
    result: Optional[pl.DataFrame],
    agg: pl.DataFrame,
    group_cols: List[str],
) -> pl.DataFrame:
    if result is None:
        return agg
    return (
        pl.concat([result, agg])
        .group_by(group_cols)
        .agg([pl.sum("Units"), pl.sum("Totalprice")])
    )


def _merge_accumulate_item(
    result: Optional[pl.DataFrame],
    agg: pl.DataFrame,
) -> pl.DataFrame:
    if result is None:
        return agg
    return (
        pl.concat([result, agg])
        .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
        .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
    )


def _merge_accumulate_upc(
    result: Optional[pl.DataFrame],
    agg: pl.DataFrame,
) -> pl.DataFrame:
    if result is None:
        return agg
    return (
        pl.concat([result, agg])
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
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if file_type == "delimited":
        lazy = scan_delimited(file_paths, delimiter, columns=[store_col, units_col, price_col])
        units_expr = safe_numeric(units_col)
        price_expr = safe_numeric(price_col)

        if implied_units:
            units_expr = units_expr / 100
        if implied_dollars:
            price_expr = price_expr / 100
        if price_type == "Unit Price":
            price_expr = units_expr * price_expr

        return (
            lazy.with_columns([
                units_expr.alias("Units"),
                price_expr.alias("Totalprice"),
                pl.col(store_col).cast(pl.Utf8).alias("STORE_NUMBER"),
            ])
            .group_by("STORE_NUMBER")
            .agg([pl.sum("Units"), pl.sum("Totalprice")])
            .sort("STORE_NUMBER")
            .collect(streaming=True)
        )

    result = None
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter)

    for chunk in chunks:
        if column_names and len(column_names) == len(chunk.columns):
            chunk = chunk.rename(dict(zip(chunk.columns, column_names)))
        if store_col not in chunk.columns:
            continue

        c = chunk.rename({store_col: "STORE_NUMBER"}).select(["STORE_NUMBER", units_col, price_col])
        c = _apply_numeric_units_dollars(c, units_col, price_col,
                                          implied_units, implied_dollars, price_type)
        agg = c.group_by("STORE_NUMBER").agg([pl.sum("Units"), pl.sum("Totalprice")])
        result = _merge_accumulate(result, agg, ["STORE_NUMBER"])

    if result is not None:
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
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if file_type == "delimited":
        lazy = scan_delimited(file_paths, delimiter, columns=[upc_col, desc_col, units_col, dollars_col])
        units_expr = safe_numeric(units_col)
        dollars_expr = safe_numeric(dollars_col)

        if implied_units:
            units_expr = units_expr / 100
        if implied_dollars:
            dollars_expr = dollars_expr / 100

        return (
            lazy.with_columns([
                pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC_CODE"),
                pl.col(desc_col).cast(pl.Utf8).str.strip_chars().alias("PRODUCT_DESCRIPTION"),
                units_expr.alias("UNITS_SOLD"),
                dollars_expr.alias("TOTAL_DOLLARS"),
            ])
            .group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"])
            .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
            .sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
            .collect(streaming=True)
        )

    result = None
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter)

    for chunk in chunks:
        if column_names and len(column_names) == len(chunk.columns):
            chunk = chunk.rename(dict(zip(chunk.columns, column_names)))
        if upc_col not in chunk.columns:
            continue

        c = chunk.rename({upc_col: "UPC_CODE", desc_col: "PRODUCT_DESCRIPTION"}).select(
            ["UPC_CODE", "PRODUCT_DESCRIPTION", units_col, dollars_col]
        )
        c = c.with_columns([
            pl.col("UPC_CODE").cast(pl.Utf8).str.strip_chars(),
            pl.col("PRODUCT_DESCRIPTION").cast(pl.Utf8).str.strip_chars().fill_null(""),
            safe_numeric(units_col).alias("UNITS_SOLD"),
            safe_numeric(dollars_col).alias("TOTAL_DOLLARS"),
        ])
        if implied_units:
            c = c.with_columns(pl.col("UNITS_SOLD") / 100)
        if implied_dollars:
            c = c.with_columns(pl.col("TOTAL_DOLLARS") / 100)

        agg = c.group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"]).agg(
            [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]
        )
        result = _merge_accumulate_item(result, agg)

    if result is not None:
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
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if file_type == "delimited":
        lazy = scan_delimited(file_paths, delimiter, columns=[upc_col, units_col, dollars_col])
        u_expr = safe_numeric(units_col)
        d_expr = safe_numeric(dollars_col)
        if implied_units:
            u_expr = u_expr / 100
        if implied_dollars:
            d_expr = d_expr / 100
        return (
            lazy.with_columns([
                pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC"),
                u_expr.alias("UNITS_SOLD"),
                d_expr.alias("TOTAL_DOLLARS"),
            ])
            .group_by("UPC")
            .agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
            .collect(streaming=True)
        )

    result = None
    chunks = _iter_chunks(file_paths, file_type, layout, start_line,
                          record_type, multiline_record_types, multiline_delimiter)

    for chunk in chunks:
        if column_names and len(column_names) == len(chunk.columns):
            chunk = chunk.rename(dict(zip(chunk.columns, column_names)))
        if upc_col not in chunk.columns:
            continue

        c = chunk.rename({upc_col: "UPC"}).select(["UPC", units_col, dollars_col])
        c = c.with_columns([
            pl.col("UPC").cast(pl.Utf8).str.strip_chars(),
            safe_numeric(units_col).alias("UNITS_SOLD"),
            safe_numeric(dollars_col).alias("TOTAL_DOLLARS"),
        ])
        if implied_units:
            c = c.with_columns(pl.col("UNITS_SOLD") / 100)
        if implied_dollars:
            c = c.with_columns(pl.col("TOTAL_DOLLARS") / 100)

        agg = c.group_by("UPC").agg([pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")])
        result = _merge_accumulate_upc(result, agg)

    return result if result is not None else pl.DataFrame()


def _iter_chunks(file_paths, file_type, layout, start_line,
                 record_type, multiline_record_types, multiline_delimiter):
    if file_type == "fixed":
        return parse_fixed_width_chunks(file_paths, layout, start_line, record_type)
    elif file_type == "multiline":
        rtypes = multiline_record_types or ["H", "D"]
        return flatten_multiline_chunks(file_paths, rtypes, multiline_delimiter)
    return iter([])


def generate_file_review(
    file_paths: Union[str, List[str]],
    file_type: str,
    store_col: str,
    upc_col: str,
    units_col: str,
    dollars_col: str,
    date_col: Optional[str] = None,
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
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    rows = []
    for f in file_paths:
        fname = os.path.basename(f)

        sa = stream_store_aggregate(
            [f], file_type, store_col, units_col, dollars_col,
            delimiter=delimiter, layout=layout,
            price_type=price_type,
            implied_dollars=implied_dollars, implied_units=implied_units,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
        )

        ua = stream_upc_summary(
            [f], file_type, upc_col, units_col, dollars_col,
            delimiter=delimiter, layout=layout,
            implied_units=implied_units, implied_dollars=implied_dollars,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
        )

        store_count = sa.height if sa is not None and not sa.is_empty() else 0
        upc_count = ua.height if ua is not None and not ua.is_empty() else 0
        total_units = ua["UNITS_SOLD"].sum() if ua is not None and "UNITS_SOLD" in ua.columns else 0.0
        total_dollars = ua["TOTAL_DOLLARS"].sum() if ua is not None and "TOTAL_DOLLARS" in ua.columns else 0.0

        rows.append({
            "filename": fname,
            "store_count": store_count,
            "upc_count": upc_count,
            "total_units": float(total_units),
            "total_dollars": round(float(total_dollars), 2),
        })

    return pl.DataFrame(rows)

import polars as pl
from typing import List, Optional

from dav_tool._parsers import safe_numeric


def apply_column_names(df: pl.DataFrame, column_names: Optional[List[str]] = None) -> pl.DataFrame:
    if column_names and len(column_names) == len(df.columns):
        return df.rename(dict(zip(df.columns, column_names)))
    return df


def store_normalize_exprs(
    store_col: str, units_col: str, price_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    price_type: str = "Total Price",
) -> List[pl.Expr]:
    u = safe_numeric(units_col)
    d = safe_numeric(price_col)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    if price_type == "Unit Price":
        d = u * d
    return [
        u.alias("Units"),
        d.alias("Totalprice"),
        pl.col(store_col).cast(pl.Utf8).alias("STORE_NUMBER"),
    ]


def normalize_store_chunk(
    chunk: pl.DataFrame, store_col: str, units_col: str, price_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    price_type: str = "Total Price",
) -> pl.DataFrame:
    c = chunk.rename({store_col: "STORE_NUMBER"}).select(
        ["STORE_NUMBER", units_col, price_col]
    )
    u = safe_numeric(units_col)
    d = safe_numeric(price_col)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    if price_type == "Unit Price":
        d = u * d
    return c.with_columns([u.alias("Units"), d.alias("Totalprice")])


def item_normalize_exprs(
    upc_col: str, desc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
) -> List[pl.Expr]:
    u = safe_numeric(units_col)
    d = safe_numeric(dollars_col)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    return [
        pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC_CODE"),
        pl.col(desc_col).cast(pl.Utf8).str.strip_chars().alias("PRODUCT_DESCRIPTION"),
        u.alias("UNITS_SOLD"),
        d.alias("TOTAL_DOLLARS"),
    ]


def normalize_item_chunk(
    chunk: pl.DataFrame, upc_col: str, desc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
) -> pl.DataFrame:
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
    return c


def upc_normalize_exprs(
    upc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
) -> List[pl.Expr]:
    u = safe_numeric(units_col)
    d = safe_numeric(dollars_col)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    return [
        pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC"),
        u.alias("UNITS_SOLD"),
        d.alias("TOTAL_DOLLARS"),
    ]


def normalize_upc_chunk(
    chunk: pl.DataFrame, upc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
) -> pl.DataFrame:
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
    return c

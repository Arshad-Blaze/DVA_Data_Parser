import polars as pl
from typing import List, Optional

from dav_tool._numeric import (
    NumericParsingConfig,
    numeric_parse_expr,
)
from dav_tool.quantity import (
    QuantityStrategy,
    map_quantity_type_to_strategy,
    resolve_quantity,
)


def apply_column_names(df: pl.DataFrame, column_names: Optional[List[str]] = None) -> pl.DataFrame:
    if column_names and len(column_names) == len(df.columns):
        return df.rename(dict(zip(df.columns, column_names)))
    return df


def _effective_qty_expr(
    units_col: str,
    weight_col: Optional[str] = None,
    quantity_type: str = "units",
    weight_uom_col: Optional[str] = None,
    weight_uom: str = "lb",
    numeric_config: Optional[NumericParsingConfig] = None,
    quantity_strategy: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    units_uom: Optional[str] = None,
) -> pl.Expr:
    """Resolve quantity using the configurable Quantity Resolver.

    Backward-compatible: maps legacy ``quantity_type`` to ``QuantityStrategy``
    when ``quantity_strategy`` is not set.
    """
    strategy = (
        QuantityStrategy(quantity_strategy)
        if quantity_strategy
        else map_quantity_type_to_strategy(quantity_type)
    )
    return resolve_quantity(
        units_col=units_col,
        weight_qty_col=weight_qty_col or weight_col,
        weight_uom_col=weight_uom_col,
        weight_uom=weight_uom,
        strategy=strategy,
        units_uom=units_uom,
        numeric_config=numeric_config,
    )


def store_normalize_exprs(
    store_col: str, units_col: str, price_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    price_type: str = "Total Price",
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config)
    d = numeric_parse_expr(price_col, numeric_config)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> pl.DataFrame:
    qty_col = weight_col if quantity_type == "weight" and weight_col else units_col
    c = chunk.select([
        pl.col(store_col).alias("STORE_NUMBER"),
        pl.col(qty_col),
        pl.col(price_col),
    ])
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config)
    d = numeric_parse_expr(price_col, numeric_config)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config)
    d = numeric_parse_expr(dollars_col, numeric_config)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> pl.DataFrame:
    qty_col = weight_col if quantity_type == "weight" and weight_col else units_col
    c = chunk.select([
        pl.col(upc_col).alias("UPC_CODE"),
        pl.col(desc_col).alias("PRODUCT_DESCRIPTION"),
        pl.col(qty_col),
        pl.col(dollars_col),
    ])
    c = c.with_columns([
        pl.col("UPC_CODE").cast(pl.Utf8).str.strip_chars(),
        pl.col("PRODUCT_DESCRIPTION").cast(pl.Utf8).str.strip_chars().fill_null(""),
        _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config).alias("UNITS_SOLD"),
        numeric_parse_expr(dollars_col, numeric_config).alias("TOTAL_DOLLARS"),
    ])
    if implied_units:
        c = c.with_columns(pl.col("UNITS_SOLD") / 100)
    if implied_dollars:
        c = c.with_columns(pl.col("TOTAL_DOLLARS") / 100)
    return c


def upc_normalize_exprs(
    upc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config)
    d = numeric_parse_expr(dollars_col, numeric_config)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> pl.DataFrame:
    qty_col = weight_col if quantity_type == "weight" and weight_col else units_col
    c = chunk.select([
        pl.col(upc_col).alias("UPC"),
        pl.col(qty_col),
        pl.col(dollars_col),
    ])
    c = c.with_columns([
        pl.col("UPC").cast(pl.Utf8).str.strip_chars(),
        _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config).alias("UNITS_SOLD"),
        numeric_parse_expr(dollars_col, numeric_config).alias("TOTAL_DOLLARS"),
    ])
    if implied_units:
        c = c.with_columns(pl.col("UNITS_SOLD") / 100)
    if implied_dollars:
        c = c.with_columns(pl.col("TOTAL_DOLLARS") / 100)
    return c

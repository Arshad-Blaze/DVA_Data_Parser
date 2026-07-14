import polars as pl
from typing import List, Optional

from dav_tool._parsers import safe_numeric


def apply_column_names(df: pl.DataFrame, column_names: Optional[List[str]] = None) -> pl.DataFrame:
    if column_names and len(column_names) == len(df.columns):
        return df.rename(dict(zip(df.columns, column_names)))
    return df


UOM_TO_LB = {
    "lb": 1.0,
    "oz": 1.0 / 16.0,
    "kg": 2.20462,
    "g": 0.00220462,
}


def _apply_uom_conversion(expr: pl.Expr, uom_col: Optional[str], default_uom: str) -> pl.Expr:
    """Apply per-row or default UOM conversion to ``expr``, normalising to lb."""
    if uom_col:
        factor = (
            pl.when(pl.col(uom_col).str.to_lowercase().str.strip_chars() == "lb").then(1.0)
            .when(pl.col(uom_col).str.to_lowercase().str.strip_chars() == "oz").then(1.0 / 16.0)
            .when(pl.col(uom_col).str.to_lowercase().str.strip_chars() == "kg").then(2.20462)
            .when(pl.col(uom_col).str.to_lowercase().str.strip_chars() == "g").then(0.00220462)
            .otherwise(UOM_TO_LB.get(default_uom, 1.0))
        )
        return expr * factor
    factor = UOM_TO_LB.get(default_uom, 1.0)
    if factor != 1.0:
        return expr * factor
    return expr


def _effective_qty_expr(
    units_col: str,
    weight_col: Optional[str] = None,
    quantity_type: str = "units",
    weight_uom_col: Optional[str] = None,
    weight_uom: str = "lb",
) -> pl.Expr:
    """Return the effective quantity expression based on quantity type."""
    if quantity_type == "weight" and weight_col:
        qty = safe_numeric(weight_col)
        return _apply_uom_conversion(qty, weight_uom_col, weight_uom)
    if quantity_type == "mixed":
        units_expr = safe_numeric(units_col)
        if weight_col:
            weight_expr = safe_numeric(weight_col)
            weight_expr = _apply_uom_conversion(weight_expr, weight_uom_col, weight_uom)
            return pl.when(weight_expr.is_not_null() & (weight_expr != 0)).then(weight_expr).otherwise(units_expr)
        return units_expr
    return safe_numeric(units_col)


def store_normalize_exprs(
    store_col: str, units_col: str, price_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    price_type: str = "Total Price",
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
) -> pl.DataFrame:
    qty_col = weight_col if quantity_type == "weight" and weight_col else units_col
    c = chunk.select([
        pl.col(store_col).alias("STORE_NUMBER"),
        pl.col(qty_col),
        pl.col(price_col),
    ])
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
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
        _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom).alias("UNITS_SOLD"),
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom)
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
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
) -> pl.DataFrame:
    qty_col = weight_col if quantity_type == "weight" and weight_col else units_col
    c = chunk.select([
        pl.col(upc_col).alias("UPC"),
        pl.col(qty_col),
        pl.col(dollars_col),
    ])
    c = c.with_columns([
        pl.col("UPC").cast(pl.Utf8).str.strip_chars(),
        _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom).alias("UNITS_SOLD"),
        safe_numeric(dollars_col).alias("TOTAL_DOLLARS"),
    ])
    if implied_units:
        c = c.with_columns(pl.col("UNITS_SOLD") / 100)
    if implied_dollars:
        c = c.with_columns(pl.col("TOTAL_DOLLARS") / 100)
    return c

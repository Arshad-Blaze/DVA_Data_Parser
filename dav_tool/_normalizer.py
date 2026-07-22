import logging

import polars as pl
from typing import List, Optional

logger = logging.getLogger(__name__)

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


def _date_expr(date_col: Optional[str]) -> Optional[pl.Expr]:
    """Return a date expression from a date column, or None."""
    if not date_col:
        return None
    try:
        return pl.col(date_col).cast(pl.Utf8).alias("Date")
    except Exception as e:
        logger.warning("Date expression failed for column %s: %s", date_col, e)
        return pl.lit(None, pl.Utf8).alias("Date")


def _quantity_type_expr(
    units_col: str,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    quantity_type: str = "units",
    numeric_config: Optional[NumericParsingConfig] = None,
) -> pl.Expr:
    """Return an expression that resolves QuantityType per row.

    Mirrors the logic in ``resolve_quantity`` to determine whether
    each row resolved to WEIGHT, UNIT, or NONE.
    """
    strategy = (
        QuantityStrategy(quantity_strategy)
        if quantity_strategy
        else map_quantity_type_to_strategy(quantity_type)
    )

    if strategy == QuantityStrategy.UNITS_ONLY:
        qty = numeric_parse_expr(units_col, numeric_config)
        return (
            pl.when(qty.is_not_null() & (qty > 0))
            .then(pl.lit("UNIT", pl.Utf8))
            .otherwise(pl.lit("NONE", pl.Utf8))
        ).alias("QuantityType")

    if strategy == QuantityStrategy.WEIGHT_ONLY:
        if weight_qty_col:
            w = numeric_parse_expr(weight_qty_col, numeric_config)
            return (
                pl.when(w.is_not_null() & (w > 0))
                .then(pl.lit("WEIGHT", pl.Utf8))
                .otherwise(pl.lit("NONE", pl.Utf8))
            ).alias("QuantityType")
        return pl.lit("NONE", pl.Utf8).alias("QuantityType")

    # AUTO / PREFER_WEIGHT / PREFER_UNITS: per-row resolution
    units = numeric_parse_expr(units_col, numeric_config)

    if strategy in (QuantityStrategy.AUTO, QuantityStrategy.PREFER_WEIGHT):
        if weight_qty_col:
            w = numeric_parse_expr(weight_qty_col, numeric_config)
            return (
                pl.when(w.is_not_null() & (w > 0))
                .then(pl.lit("WEIGHT", pl.Utf8))
                .when(units.is_not_null() & (units > 0))
                .then(pl.lit("UNIT", pl.Utf8))
                .otherwise(pl.lit("NONE", pl.Utf8))
            ).alias("QuantityType")
        return (
            pl.when(units.is_not_null() & (units > 0))
            .then(pl.lit("UNIT", pl.Utf8))
            .otherwise(pl.lit("NONE", pl.Utf8))
        ).alias("QuantityType")

    if strategy == QuantityStrategy.PREFER_UNITS:
        if weight_qty_col:
            w = numeric_parse_expr(weight_qty_col, numeric_config)
            return (
                pl.when(units.is_not_null() & (units > 0))
                .then(pl.lit("UNIT", pl.Utf8))
                .when(w.is_not_null() & (w > 0))
                .then(pl.lit("WEIGHT", pl.Utf8))
                .otherwise(pl.lit("NONE", pl.Utf8))
            ).alias("QuantityType")
        return (
            pl.when(units.is_not_null() & (units > 0))
            .then(pl.lit("UNIT", pl.Utf8))
            .otherwise(pl.lit("NONE", pl.Utf8))
        ).alias("QuantityType")


def _uom_expr(
    units_col: str,
    weight_qty_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    units_uom: Optional[str] = None,
    quantity_strategy: str = "auto",
    quantity_type: str = "units",
    numeric_config: Optional[NumericParsingConfig] = None,
) -> pl.Expr:
    """Return an expression for the UOM column — per-row or default.

    When a per-row weight UOM column is provided, uses it for weight-based
    rows. Falls back to *weight_uom* or *units_uom* as appropriate.
    """
    qtype_expr = _quantity_type_expr(units_col, weight_qty_col, quantity_strategy, quantity_type, numeric_config)

    # Per-row UOM from column
    if weight_uom_col:
        row_uom = pl.col(weight_uom_col).cast(pl.Utf8)
        units_default = units_uom or "unit"
        return (
            pl.when(qtype_expr == pl.lit("WEIGHT"))
            .then(row_uom)
            .when(qtype_expr == pl.lit("UNIT"))
            .then(pl.lit(units_default, pl.Utf8))
            .otherwise(pl.lit("", pl.Utf8))
        ).alias("UOM")

    # Static UOM based on strategy
    default_uom = weight_uom
    if quantity_strategy in ("prefer_units", "units_only") or quantity_type in ("units",):
        default_uom = units_uom or "unit"

    return (
        pl.when(qtype_expr == pl.lit("WEIGHT"))
        .then(pl.lit(default_uom, pl.Utf8))
        .when(qtype_expr == pl.lit("UNIT"))
        .then(pl.lit(units_uom or "unit", pl.Utf8))
        .otherwise(pl.lit("", pl.Utf8))
    ).alias("UOM")


def _extra_cols(
    units_col: str,
    date_col: Optional[str] = None,
    quantity_type: str = "units",
    quantity_strategy: str = "auto",
    weight_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    units_uom: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    schema_template: str = "minimal",
) -> List[pl.Expr]:
    """Build extra canonical column expressions (Date, QuantityType, UOM).

    Only adds columns when *schema_template* is ``"standard"`` or ``"enriched"``.
    For ``"minimal"`` (the default) returns an empty list.
    """
    if schema_template == "minimal":
        return []
    exprs: List[pl.Expr] = []
    d = _date_expr(date_col)
    if d is not None:
        exprs.append(d)
    exprs.append(_quantity_type_expr(
        units_col, weight_qty_col, quantity_strategy, quantity_type, numeric_config,
    ))
    exprs.append(_uom_expr(
        units_col, weight_qty_col, weight_uom, weight_uom_col,
        units_uom, quantity_strategy, quantity_type, numeric_config,
    ))
    return exprs


def store_normalize_exprs(
    store_col: str, units_col: str, price_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    price_type: str = "Total Price",
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config, weight_qty_col=weight_qty_col, quantity_strategy=quantity_strategy, units_uom=units_uom)
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
    ] + _extra_cols(units_col, date_col, quantity_type, quantity_strategy, weight_col, weight_qty_col, weight_uom, weight_uom_col, units_uom, numeric_config, schema_template=schema_template)


def normalize_store_chunk(
    chunk: pl.DataFrame, store_col: str, units_col: str, price_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    price_type: str = "Total Price",
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> pl.DataFrame:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config, weight_qty_col=weight_qty_col, quantity_strategy=quantity_strategy, units_uom=units_uom)
    d = numeric_parse_expr(price_col, numeric_config)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    if price_type == "Unit Price":
        d = u * d
    exprs = [
        pl.col(store_col).cast(pl.Utf8).alias("STORE_NUMBER"),
        u.alias("Units"),
        d.alias("Totalprice"),
    ]
    extra = _extra_cols(units_col, date_col, quantity_type, quantity_strategy, weight_col, weight_qty_col, weight_uom, weight_uom_col, units_uom, numeric_config, schema_template=schema_template)
    if extra:
        exprs.extend(extra)
    return chunk.select(exprs)


def item_normalize_exprs(
    upc_col: str, desc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config, weight_qty_col=weight_qty_col, quantity_strategy=quantity_strategy, units_uom=units_uom)
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
    ] + _extra_cols(units_col, date_col, quantity_type, quantity_strategy, weight_col, weight_qty_col, weight_uom, weight_uom_col, units_uom, numeric_config, schema_template=schema_template)


def normalize_item_chunk(
    chunk: pl.DataFrame, upc_col: str, desc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> pl.DataFrame:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config, weight_qty_col=weight_qty_col, quantity_strategy=quantity_strategy, units_uom=units_uom)
    d = numeric_parse_expr(dollars_col, numeric_config)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    exprs = [
        pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC_CODE"),
        pl.col(desc_col).cast(pl.Utf8).str.strip_chars().fill_null("").alias("PRODUCT_DESCRIPTION"),
        u.alias("UNITS_SOLD"),
        d.alias("TOTAL_DOLLARS"),
    ]
    extra = _extra_cols(units_col, date_col, quantity_type, quantity_strategy, weight_col, weight_qty_col, weight_uom, weight_uom_col, units_uom, numeric_config, schema_template=schema_template)
    if extra:
        exprs.extend(extra)
    return chunk.select(exprs)


def upc_normalize_exprs(
    upc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> List[pl.Expr]:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config, weight_qty_col=weight_qty_col, quantity_strategy=quantity_strategy, units_uom=units_uom)
    d = numeric_parse_expr(dollars_col, numeric_config)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    return [
        pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC"),
        u.alias("UNITS_SOLD"),
        d.alias("TOTAL_DOLLARS"),
    ] + _extra_cols(units_col, date_col, quantity_type, quantity_strategy, weight_col, weight_qty_col, weight_uom, weight_uom_col, units_uom, numeric_config, schema_template=schema_template)


def normalize_upc_chunk(
    chunk: pl.DataFrame, upc_col: str, units_col: str, dollars_col: str,
    implied_units: bool = False, implied_dollars: bool = False,
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
    date_col: Optional[str] = None,
    weight_qty_col: Optional[str] = None,
    quantity_strategy: str = "auto",
    units_uom: Optional[str] = None,
    schema_template: str = "minimal",
) -> pl.DataFrame:
    u = _effective_qty_expr(units_col, weight_col, quantity_type, weight_uom_col, weight_uom, numeric_config, weight_qty_col=weight_qty_col, quantity_strategy=quantity_strategy, units_uom=units_uom)
    d = numeric_parse_expr(dollars_col, numeric_config)
    if implied_units:
        u = u / 100
    if implied_dollars:
        d = d / 100
    exprs = [
        pl.col(upc_col).cast(pl.Utf8).str.strip_chars().alias("UPC"),
        u.alias("UNITS_SOLD"),
        d.alias("TOTAL_DOLLARS"),
    ]
    extra = _extra_cols(units_col, date_col, quantity_type, quantity_strategy, weight_col, weight_qty_col, weight_uom, weight_uom_col, units_uom, numeric_config, schema_template=schema_template)
    if extra:
        exprs.extend(extra)
    return chunk.select(exprs)





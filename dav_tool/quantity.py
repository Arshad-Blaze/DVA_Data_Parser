"""Quantity Resolution — configurable resolver for mixed units/weight datasets.

Business Rule (default, strategy="auto"):

    IF weight_qty IS NOT NULL AND weight_qty > 0
        THEN resolved_qty = weight_qty (converted to lb)
    ELSE IF units > 0
        THEN resolved_qty = units
    ELSE
        resolved_qty = 0

Strategies:
    auto           — weight takes precedence, units fallback
    prefer_weight  — same as auto (explicit alias)
    prefer_units   — units take precedence, weight fallback
    weight_only    — only weight, ignore units
    units_only     — only units, ignore weight

UOM conversion normalises to pounds (lb) for weight columns.
Uses ``numeric_parse_expr`` for robust numeric parsing (currency symbols,
thousands separators, parenthetical negatives, etc.).
"""
from enum import Enum
from typing import Optional

import polars as pl

from dav_tool._numeric import NumericParsingConfig, numeric_parse_expr


class QuantityStrategy(str, Enum):
    """Resolution strategy for mixed units/weight datasets."""
    AUTO = "auto"
    PREFER_WEIGHT = "prefer_weight"
    PREFER_UNITS = "prefer_units"
    WEIGHT_ONLY = "weight_only"
    UNITS_ONLY = "units_only"


UOM_TO_LB = {
    "lb": 1.0,
    "lbs": 1.0,
    "pound": 1.0,
    "pounds": 1.0,
    "oz": 1.0 / 16.0,
    "ounce": 1.0 / 16.0,
    "ounces": 1.0 / 16.0,
    "kg": 2.20462,
    "kilogram": 2.20462,
    "kilograms": 2.20462,
    "g": 0.00220462,
    "gram": 0.00220462,
    "grams": 0.00220462,
}


def _uom_factor_expr(uom_col: Optional[str], default_uom: str = "lb") -> pl.Expr:
    """Return a Polars expression for the UOM-to-lb conversion factor."""
    if uom_col:
        lower = pl.col(uom_col).str.to_lowercase().str.strip_chars()
        return (
            pl.when(lower.is_in(list(UOM_TO_LB)))
            .then(lower.replace_strict(UOM_TO_LB, default=1.0))
            .otherwise(1.0)
        )
    factor = UOM_TO_LB.get(default_uom.lower(), 1.0)
    return pl.lit(factor, dtype=pl.Float64)


def convert_to_lb(expr: pl.Expr, uom_col: Optional[str] = None, default_uom: str = "lb") -> pl.Expr:
    """Convert *expr* from *default_uom* (or per-row *uom_col*) to pounds."""
    factor = _uom_factor_expr(uom_col, default_uom)
    return expr * factor


def resolve_quantity(
    units_col: str,
    weight_qty_col: Optional[str] = None,
    weight_uom_col: Optional[str] = None,
    weight_uom: str = "lb",
    strategy: QuantityStrategy = QuantityStrategy.AUTO,
    units_uom: Optional[str] = None,
    numeric_config: Optional[NumericParsingConfig] = None,
) -> pl.Expr:
    """Return a Polars expression that resolves quantity per row.

    Applies the full ``numeric_parse_expr`` pipeline to both units and
    weight columns before resolution.

    Parameters
    ----------
    units_col : str
        Column name for units (count) values.
    weight_qty_col : str, optional
        Column name for weighted quantity values.
    weight_uom_col : str, optional
        Column name for per-row weight UOM.
    weight_uom : str
        Default weight UOM when *weight_uom_col* is None.
    strategy : QuantityStrategy
        Resolution strategy.
    units_uom : str, optional
        UOM for units column (for display/consistency — units are count,
        so no conversion applied).
    numeric_config : NumericParsingConfig, optional
        Numeric parsing configuration (currency, locale, etc.).

    Returns
    -------
    pl.Expr
        Float64 expression with resolved quantity.
    """
    units = numeric_parse_expr(units_col, numeric_config)

    if strategy == QuantityStrategy.UNITS_ONLY:
        return units.fill_null(0.0)

    weight_qty = numeric_parse_expr(weight_qty_col, numeric_config) if weight_qty_col else None

    if strategy == QuantityStrategy.WEIGHT_ONLY:
        if weight_qty is None:
            return pl.lit(0.0, dtype=pl.Float64)
        return convert_to_lb(weight_qty, weight_uom_col, weight_uom).fill_null(0.0)

    if weight_qty is None:
        return units.fill_null(0.0)

    weight_qty_lb = convert_to_lb(weight_qty, weight_uom_col, weight_uom)

    if strategy in (QuantityStrategy.AUTO, QuantityStrategy.PREFER_WEIGHT):
        return (
            pl.when(weight_qty_lb.is_not_null() & (weight_qty_lb > 0))
            .then(weight_qty_lb)
            .when(units.is_not_null() & (units > 0))
            .then(units)
            .otherwise(0.0)
        )

    if strategy == QuantityStrategy.PREFER_UNITS:
        return (
            pl.when(units.is_not_null() & (units > 0))
            .then(units)
            .when(weight_qty_lb.is_not_null() & (weight_qty_lb > 0))
            .then(weight_qty_lb)
            .otherwise(0.0)
        )

    return units.fill_null(0.0)


def map_quantity_type_to_strategy(quantity_type: str) -> QuantityStrategy:
    """Map legacy ``quantity_type`` values to ``QuantityStrategy``."""
    mapping = {
        "units": QuantityStrategy.UNITS_ONLY,
        "weight": QuantityStrategy.WEIGHT_ONLY,
        "mixed": QuantityStrategy.AUTO,
    }
    return mapping.get(quantity_type, QuantityStrategy.AUTO)

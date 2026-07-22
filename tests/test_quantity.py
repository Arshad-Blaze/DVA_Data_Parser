"""Tests for quantity resolution (mixed weight/units)."""

import polars as pl
from dav_tool.quantity import (
    QuantityStrategy,
    UOM_TO_LB,
    convert_to_lb,
    resolve_quantity,
    map_quantity_type_to_strategy,
)


def test_strategy_enum_values():
    assert QuantityStrategy.AUTO.value == "auto"
    assert QuantityStrategy.PREFER_WEIGHT.value == "prefer_weight"
    assert QuantityStrategy.PREFER_UNITS.value == "prefer_units"
    assert QuantityStrategy.WEIGHT_ONLY.value == "weight_only"
    assert QuantityStrategy.UNITS_ONLY.value == "units_only"


def test_map_units_strategy():
    assert map_quantity_type_to_strategy("units") == QuantityStrategy.UNITS_ONLY


def test_map_weight_strategy():
    assert map_quantity_type_to_strategy("weight") == QuantityStrategy.WEIGHT_ONLY


def test_map_mixed_strategy():
    assert map_quantity_type_to_strategy("mixed") == QuantityStrategy.AUTO


def test_map_unknown_strategy_defaults_to_auto():
    assert map_quantity_type_to_strategy("unknown") == QuantityStrategy.AUTO


def test_uom_to_lb_conversion_factors():
    assert UOM_TO_LB["lb"] == 1.0
    assert UOM_TO_LB["oz"] == 1.0 / 16.0
    assert abs(UOM_TO_LB["kg"] - 2.20462) < 1e-5
    assert abs(UOM_TO_LB["g"] - 0.00220462) < 1e-5


def test_convert_to_lb_literal_default():
    df = pl.DataFrame({"weight": [10.0, 20.0, 0.0]})
    expr = convert_to_lb(pl.col("weight"), default_uom="lb")
    result = df.with_columns(converted=expr)
    assert result["converted"].to_list() == [10.0, 20.0, 0.0]


def test_convert_to_lb_oz_to_lb():
    df = pl.DataFrame({"weight": [16.0, 32.0]})
    expr = convert_to_lb(pl.col("weight"), default_uom="oz")
    result = df.with_columns(converted=expr)
    assert result["converted"].to_list() == [1.0, 2.0]


def test_convert_to_lb_kg_to_lb():
    df = pl.DataFrame({"weight": [1.0, 2.0]})
    expr = convert_to_lb(pl.col("weight"), default_uom="kg")
    result = df.with_columns(converted=expr)
    assert abs(result["converted"][0] - 2.20462) < 1e-4
    assert abs(result["converted"][1] - 4.40924) < 1e-4


def test_convert_to_lb_per_row_uom():
    df = pl.DataFrame({"weight": [1.0, 16.0, 1.0], "uom": ["lb", "oz", "kg"]})
    expr = convert_to_lb(pl.col("weight"), uom_col="uom")
    result = df.with_columns(converted=expr)
    assert result["converted"][0] == 1.0
    assert result["converted"][1] == 1.0
    assert abs(result["converted"][2] - 2.20462) < 1e-4


def test_convert_to_lb_unknown_uom_falls_back():
    df = pl.DataFrame({"weight": [10.0], "uom": ["stone"]})
    expr = convert_to_lb(pl.col("weight"), uom_col="uom", default_uom="lb")
    result = df.with_columns(converted=expr)
    assert result["converted"][0] == 10.0


def test_resolve_quantity_units_only():
    df = pl.DataFrame({"units": [5, 0, None], "weight": [10, 20, 30]})
    expr = resolve_quantity("units", strategy=QuantityStrategy.UNITS_ONLY)
    result = df.with_columns(qty=expr)
    assert result["qty"].to_list() == [5.0, 0.0, 0.0]


def test_resolve_quantity_weight_only():
    df = pl.DataFrame({"units": [5, 0, None], "weight_qty": [10, 20, None]})
    expr = resolve_quantity("units", weight_qty_col="weight_qty", strategy=QuantityStrategy.WEIGHT_ONLY)
    result = df.with_columns(qty=expr)
    assert result["qty"].to_list() == [10.0, 20.0, 0.0]


def test_resolve_quantity_weight_only_missing_col_returns_zero():
    df = pl.DataFrame({"units": [5]})
    expr = resolve_quantity("units", weight_qty_col=None, strategy=QuantityStrategy.WEIGHT_ONLY)
    result = df.with_columns(qty=expr)
    assert result["qty"][0] == 0.0


def test_resolve_quantity_auto_weight_preferred():
    df = pl.DataFrame({"units": [5, 0, None], "weight_qty": [0, 20, 30]})
    expr = resolve_quantity("units", weight_qty_col="weight_qty", strategy=QuantityStrategy.AUTO)
    result = df.with_columns(qty=expr)
    # row 0: weight=0 → fallback to units=5
    # row 1: weight=20 > 0 → use weight
    # row 2: weight=30 > 0 → use weight
    assert result["qty"][0] == 5.0
    assert result["qty"][1] == 20.0
    assert result["qty"][2] == 30.0


def test_resolve_quantity_prefer_units():
    df = pl.DataFrame({"units": [5, 0, None], "weight_qty": [10, 20, 30]})
    expr = resolve_quantity("units", weight_qty_col="weight_qty", strategy=QuantityStrategy.PREFER_UNITS)
    result = df.with_columns(qty=expr)
    # row 0: units=5 > 0 → use units
    # row 1: units=0 → fallback to weight=20
    # row 2: units=None → fallback to weight=30
    assert result["qty"][0] == 5.0
    assert result["qty"][1] == 20.0
    assert result["qty"][2] == 30.0


def test_resolve_quantity_auto_all_null():
    df = pl.DataFrame({"units": [None, None], "weight_qty": [None, None]})
    expr = resolve_quantity("units", weight_qty_col="weight_qty", strategy=QuantityStrategy.AUTO)
    result = df.with_columns(qty=expr)
    assert result["qty"].to_list() == [0.0, 0.0]


def test_resolve_quantity_no_weight_col():
    df = pl.DataFrame({"units": [5, 0, None]})
    expr = resolve_quantity("units", weight_qty_col=None, strategy=QuantityStrategy.AUTO)
    result = df.with_columns(qty=expr)
    assert result["qty"].to_list() == [5.0, 0.0, 0.0]


def test_resolve_quantity_weight_converted_to_lb():
    df = pl.DataFrame({"units": [1], "weight_qty": [1.0], "uom": ["oz"]})
    expr = resolve_quantity("units", weight_qty_col="weight_qty", weight_uom_col="uom",
                            strategy=QuantityStrategy.WEIGHT_ONLY)
    result = df.with_columns(qty=expr)
    assert abs(result["qty"][0] - 1.0 / 16.0) < 1e-6


def test_resolve_quantity_weight_default_uom():
    df = pl.DataFrame({"units": [1], "weight_qty": [2.0]})
    expr = resolve_quantity("units", weight_qty_col="weight_qty", weight_uom="kg",
                            strategy=QuantityStrategy.WEIGHT_ONLY)
    result = df.with_columns(qty=expr)
    assert abs(result["qty"][0] - 2.0 * 2.20462) < 1e-4

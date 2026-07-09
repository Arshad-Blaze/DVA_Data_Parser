"""Golden dataset regression tests.

Compares current pipeline output against saved golden CSV files.
Regenerate golden data with:  python -m tests.golden.generate_golden
"""
import csv
import os
from pathlib import Path

import polars as pl
import pytest

from dav_tool._aggregators import (
    stream_store_aggregate,
    stream_item_aggregate,
    stream_upc_summary,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
ROUNDING = 4

ROWS = [
    ("S001", "100001", "Widget A", "10", "99.90"),
    ("S001", "100002", "Gadget B", "5", "49.95"),
    ("S002", "100001", "Widget A", "8", "79.92"),
    ("S003", "100003", "Doohickey", "20", "199.80"),
]
COL_NAMES = ["Store", "UPC", "Description", "Units", "Price"]

# ── Format configuration ───────────────────────────────────────────────

FW_LAYOUT = [
    {"start": 0, "end": 6, "field": "Store", "type": "text"},
    {"start": 6, "end": 16, "field": "UPC", "type": "numeric"},
    {"start": 16, "end": 36, "field": "Description", "type": "text"},
    {"start": 36, "end": 41, "field": "Units", "type": "numeric"},
    {"start": 41, "end": 49, "field": "Price", "type": "numeric"},
]

HDR_LAYOUT = [
    {"start": 5, "end": 9, "field": "Store", "type": "text"},
    {"start": 12, "end": 22, "field": "Date", "type": "text"},
]

DTL_LAYOUT = [
    {"start": 0, "end": 12, "field": "UPC", "type": "text"},
    {"start": 12, "end": 33, "field": "Description", "type": "text"},
    {"start": 33, "end": 35, "field": "Units", "type": "numeric"},
    {"start": 35, "end": 43, "field": "Price", "type": "numeric"},
]

TRL_LAYOUT = [
    {"start": 3, "end": 9, "field": "TotalUnits", "type": "numeric"},
    {"start": 9, "end": 18, "field": "TotalPrice", "type": "numeric"},
]

# ── Input writers ──────────────────────────────────────────────────────


def _write_delimited(path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COL_NAMES)
        for row in ROWS:
            w.writerow(row)


def _write_fixed(path):
    with open(path, "w") as f:
        for store, upc, desc, units, price in ROWS:
            f.write(f"{store:<6}{upc:>10}{desc:<20}{units:>5}{price:>8}\n")


def _write_multiline(path):
    with open(path, "w") as f:
        for store, upc, desc, units, price in ROWS:
            f.write(f"H|{store}|2024-01-15\n")
            f.write(f"D|{store}|{upc}|{desc}|{units}|{price}\n")


def _write_hdr_fixed(path):
    def hdr_line(store, seq, date):
        return f"HDR{seq:02d}{store:<4}   {date}\n"
    def dtl_line(upc, desc, units, price):
        return f"{upc:<12}{desc:<21}{units:>2}{price:>8}     \n"
    def trl_line(total_units, total_price):
        return f"TRL{total_units:>6}{total_price:>9}\n"
    with open(path, "w") as f:
        f.write(hdr_line("S001", 1, "2024-01-15"))
        f.write(dtl_line("100001", "Widget A", "10", "99.90"))
        f.write(dtl_line("100002", "Gadget B", "5", "49.95"))
        f.write(trl_line("15", "149.85"))
        f.write(hdr_line("S002", 1, "2024-01-15"))
        f.write(dtl_line("100001", "Widget A", "8", "79.92"))
        f.write(trl_line("8", "79.92"))
        f.write(hdr_line("S003", 1, "2024-01-15"))
        f.write(dtl_line("100003", "Doohickey", "20", "199.80"))
        f.write(trl_line("20", "199.80"))


# ── Format register ────────────────────────────────────────────────────
# Each entry: (fmt_id, file_type, writer_fn, extra_kwargs)

FORMATS = [
    pytest.param(
        "delimited", "delimited", _write_delimited, {"delimiter": ","},
        id="delimited",
    ),
    pytest.param(
        "fixed", "fixed", _write_fixed, {"layout": FW_LAYOUT},
        id="fixed",
    ),
    pytest.param(
        "multiline", "multiline", _write_multiline, {
            "multiline_record_types": ["D"],
            "multiline_delimiter": "|",
            "column_names": COL_NAMES,
        },
        id="multiline",
    ),
    pytest.param(
        "hdr_fixed", "multiline", _write_hdr_fixed, {
            "header_prefix": "HDR",
            "header_layout": HDR_LAYOUT,
            "layout": DTL_LAYOUT,
            "trailer_prefix": "TRL",
            "trailer_layout": TRL_LAYOUT,
            "column_names": ["Store", "date", "UPC", "Description", "Units", "Price",
                             "total_units", "total_price"],
        },
        id="hdr_fixed",
    ),
]

AGG_LEVELS = [
    pytest.param("store", stream_store_aggregate, "store", id="store"),
    pytest.param("item", stream_item_aggregate, "item", id="item"),
    pytest.param("upc", stream_upc_summary, "upc", id="upc"),
]


# ── Helpers ────────────────────────────────────────────────────────────

def _run_pipeline(writer, file_type, agg_func, agg_name, kw, tmp_dir):
    path = os.path.join(tmp_dir, "data.txt")
    writer(path)
    if agg_name == "store":
        return agg_func(
            [path], file_type, "Store", "Units", "Price", **kw,
        ).sort("STORE_NUMBER")
    elif agg_name == "item":
        return agg_func(
            [path], file_type, "UPC", "Description", "Units", "Price", **kw,
        ).sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])
    else:
        return agg_func(
            [path], file_type, "UPC", "Units", "Price", **kw,
        ).sort("UPC")


def _read_golden(agg_name: str, fmt_id: str) -> pl.DataFrame:
    csv_path = GOLDEN_DIR / f"{agg_name}_{fmt_id}.csv"
    return pl.read_csv(csv_path)


def _compare_dfs(actual: pl.DataFrame, expected: pl.DataFrame) -> bool:
    if actual.shape != expected.shape:
        return False
    if list(actual.columns) != list(expected.columns):
        return False
    # Cast both to string for ID columns, round floats
    actual_str = actual.with_columns(
        pl.col(c).cast(pl.Utf8) for c in actual.columns if actual.schema[c] != pl.Float64
    )
    expected_str = expected.with_columns(
        pl.col(c).cast(pl.Utf8) for c in expected.columns if expected.schema[c] != pl.Float64
    )
    actual_rounded = actual_str.with_columns(
        pl.col(c).round(ROUNDING) for c in actual_str.columns if actual_str.schema[c] == pl.Float64
    )
    expected_rounded = expected_str.with_columns(
        pl.col(c).round(ROUNDING) for c in expected_str.columns if expected_str.schema[c] == pl.Float64
    )
    return actual_rounded.to_dicts() == expected_rounded.to_dicts()


# ── Tests ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("agg_name,agg_func,agg_key", AGG_LEVELS)
@pytest.mark.parametrize("fmt_id,file_type,writer,kwargs", FORMATS)
def test_golden_regression(tmp_path, fmt_id, file_type, writer, kwargs,
                           agg_name, agg_func, agg_key):
    actual = _run_pipeline(writer, file_type, agg_func, agg_key, kwargs, tmp_path)
    expected = _read_golden(agg_key, fmt_id)
    assert actual.shape == expected.shape, (
        f"Shape mismatch for {agg_key}_{fmt_id}: "
        f"actual={actual.shape}, expected={expected.shape}"
    )
    assert _compare_dfs(actual, expected), (
        f"Data mismatch for {agg_key}_{fmt_id}\n"
        f"Actual:\n{actual}\nExpected:\n{expected}"
    )

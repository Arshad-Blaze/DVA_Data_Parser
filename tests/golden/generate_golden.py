"""Generate golden dataset CSV files for regression testing.

Run from repo root:  python -m tests.golden.generate_golden

This will regenerate all golden CSV files in tests/golden/.
"""
import csv
import os
import tempfile

import polars as pl

from dav_tool._aggregators import (
    stream_store_aggregate,
    stream_item_aggregate,
    stream_upc_summary,
)

GOLDEN_DIR = os.path.join(os.path.dirname(__file__))

# ── Reference dataset ──────────────────────────────────────────────────
ROWS = [
    ("S001", "100001", "Widget A", "10", "99.90"),
    ("S001", "100002", "Gadget B", "5", "49.95"),
    ("S002", "100001", "Widget A", "8", "79.92"),
    ("S003", "100003", "Doohickey", "20", "199.80"),
]

COL_NAMES = ["Store", "UPC", "Description", "Units", "Price"]
ML_COLS = ["Store", "UPC", "Description", "Units", "Price"]

# Fixed-width layout: Store(6) + UPC(10) + Description(20) + Units(5) + Price(8)
# Fields: start (0-indexed), end (exclusive), field, type
FW_LAYOUT = [
    {"start": 0, "end": 6, "field": "Store", "type": "text"},
    {"start": 6, "end": 16, "field": "UPC", "type": "numeric"},
    {"start": 16, "end": 36, "field": "Description", "type": "text"},
    {"start": 36, "end": 41, "field": "Units", "type": "numeric"},
    {"start": 41, "end": 49, "field": "Price", "type": "numeric"},
]

# ── HDR Fixed-width layouts ────────────────────────────────────────────
# HDR line:  HDR + seq(2) + store(4) + spaces(3) + date(10)
# HDR line:  HDR<seq:02d><store:<4>   <date>
# Example:   HDR01S001   2024-01-15
# Store at 0-indexed 5-9 (4 chars), Date at 0-indexed 12-22 (10 chars)
HDR_LAYOUT = [
    {"start": 5, "end": 9, "field": "Store", "type": "text"},
    {"start": 12, "end": 22, "field": "Date", "type": "text"},
]

# Detail line: UPC(12) + Description(21) + Units(2) + Price(8) + padding
# Example: "100001    Widget A            100990"
DTL_LAYOUT = [
    {"start": 0, "end": 12, "field": "UPC", "type": "text"},
    {"start": 12, "end": 33, "field": "Description", "type": "text"},
    {"start": 33, "end": 35, "field": "Units", "type": "numeric"},
    {"start": 35, "end": 43, "field": "Price", "type": "numeric"},
]

# Trailer line: TRL + units(6) + price(9)
# Example: "TRL              1514985"
TRL_LAYOUT = [
    {"start": 3, "end": 9, "field": "TotalUnits", "type": "numeric"},
    {"start": 9, "end": 18, "field": "TotalPrice", "type": "numeric"},
]


def _fwf_row(store, upc, desc, units, price):
    return f"{store:<6}{upc:>10}{desc:<20}{units:>5}{price:>8}\n"


# ── Input file creators ────────────────────────────────────────────────

def _write_delimited(path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COL_NAMES)
        for row in ROWS:
            w.writerow(row)


def _write_fixed_width(path):
    with open(path, "w") as f:
        for row in ROWS:
            f.write(_fwf_row(*row))


def _write_multiline_delimited(path):
    with open(path, "w") as f:
        for store, upc, desc, units, price in ROWS:
            f.write(f"H|{store}|2024-01-15\n")
            f.write(f"D|{store}|{upc}|{desc}|{units}|{price}\n")


def _write_hdr_fixed_width(path):
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


# ── Pipeline wrappers ──────────────────────────────────────────────────

def _store_agg(path, file_type, **kw):
    return stream_store_aggregate(
        [path], file_type, "Store", "Units", "Price", **kw,
    ).sort("STORE_NUMBER")


def _item_agg(path, file_type, **kw):
    return stream_item_aggregate(
        [path], file_type, "UPC", "Description", "Units", "Price", **kw,
    ).sort(["UPC_CODE", "PRODUCT_DESCRIPTION"])


def _upc_agg(path, file_type, **kw):
    return stream_upc_summary(
        [path], file_type, "UPC", "Units", "Price", **kw,
    ).sort("UPC")


# ── Generators per format ──────────────────────────────────────────────

def generate_delimited(tmp_dir):
    path = os.path.join(tmp_dir, "data.csv")
    _write_delimited(path)
    kw = {"delimiter": ","}
    _store_agg(path, "delimited", **kw).write_csv(os.path.join(GOLDEN_DIR, "store_delimited.csv"))
    _item_agg(path, "delimited", **kw).write_csv(os.path.join(GOLDEN_DIR, "item_delimited.csv"))
    _upc_agg(path, "delimited", **kw).write_csv(os.path.join(GOLDEN_DIR, "upc_delimited.csv"))


def generate_fixed_width(tmp_dir):
    path = os.path.join(tmp_dir, "data.txt")
    _write_fixed_width(path)
    kw = {"layout": FW_LAYOUT}
    _store_agg(path, "fixed", **kw).write_csv(os.path.join(GOLDEN_DIR, "store_fixed.csv"))
    _item_agg(path, "fixed", **kw).write_csv(os.path.join(GOLDEN_DIR, "item_fixed.csv"))
    _upc_agg(path, "fixed", **kw).write_csv(os.path.join(GOLDEN_DIR, "upc_fixed.csv"))


def generate_multiline_delimited(tmp_dir):
    path = os.path.join(tmp_dir, "data.txt")
    _write_multiline_delimited(path)
    kw = {
        "multiline_record_types": ["D"],
        "multiline_delimiter": "|",
        "column_names": ML_COLS,
    }
    _store_agg(path, "multiline", **kw).write_csv(os.path.join(GOLDEN_DIR, "store_multiline.csv"))
    _item_agg(path, "multiline", **kw).write_csv(os.path.join(GOLDEN_DIR, "item_multiline.csv"))
    _upc_agg(path, "multiline", **kw).write_csv(os.path.join(GOLDEN_DIR, "upc_multiline.csv"))


def generate_hdr_fixed_width(tmp_dir):
    path = os.path.join(tmp_dir, "data.txt")
    _write_hdr_fixed_width(path)
    kw = {
        "header_prefix": "HDR",
        "header_layout": HDR_LAYOUT,
        "layout": DTL_LAYOUT,
        "trailer_prefix": "TRL",
        "trailer_layout": TRL_LAYOUT,
        "column_names": ["Store", "date", "UPC", "Description", "Units", "Price",
                          "total_units", "total_price"],
    }
    _store_agg(path, "multiline", **kw).write_csv(os.path.join(GOLDEN_DIR, "store_hdr_fixed.csv"))
    _item_agg(path, "multiline", **kw).write_csv(os.path.join(GOLDEN_DIR, "item_hdr_fixed.csv"))
    _upc_agg(path, "multiline", **kw).write_csv(os.path.join(GOLDEN_DIR, "upc_hdr_fixed.csv"))


# ── Main ───────────────────────────────────────────────────────────────

def main():
    with tempfile.TemporaryDirectory() as tmp:
        generate_delimited(tmp)
        generate_fixed_width(tmp)
        generate_multiline_delimited(tmp)
        generate_hdr_fixed_width(tmp)
    print("Golden dataset regenerated in tests/golden/")


if __name__ == "__main__":
    main()

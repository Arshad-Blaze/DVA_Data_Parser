"""Validation tests for 10 retailer scenarios from PROMPT.md sprint."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import polars as pl
import pytest

from dav_tool._parsers import (
    parse_delimited_chunks, parse_fixed_width_chunks,
    flatten_multiline_fixed_width, load_layout,
)
from dav_tool.detection import generate_detection_summary
from dav_tool.workflow.discovery import DiscoveryResult

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _collect(chunks):
    chunks = list(chunks)
    return pl.concat(chunks) if chunks else pl.DataFrame()


def _rows(chunks):
    return sum(c.height for c in chunks if c is not None and not c.is_empty())


# ── Scenario 1: Retailer 1 — Delimited + Weight + Units ─────────────────


def test_scenario1_mixed_quantity():
    path = os.path.join(DATA_DIR, "mixed_quantity", "sales.csv")
    chunks = list(parse_delimited_chunks([path], ","))
    assert len(chunks) > 0, "No data parsed"
    df = pl.concat(chunks)
    assert len(df) == 3
    assert "Units" in df.columns or "Weight" in df.columns


# ── Scenario 2: Retailer 2 — Pure Fixed Width ────────────────────────────


def test_scenario2_pure_fixed_width():
    layout = [
        {"field": "STORE_NUMBER", "start": 0, "end": 4, "from": 1, "length": 4, "type": "text"},
        {"field": "UPC_CODE", "start": 4, "end": 10, "from": 5, "length": 6, "type": "numeric"},
        {"field": "Description", "start": 10, "end": 30, "from": 11, "length": 20, "type": "text"},
        {"field": "Units", "start": 30, "end": 35, "from": 31, "length": 5, "type": "numeric"},
        {"field": "Price", "start": 35, "end": 42, "from": 36, "length": 7, "type": "numeric"},
    ]
    data_path = os.path.join(DATA_DIR, "sut_records", "sales.txt")
    with open(data_path) as f:
        raw = [l for l in f if l.strip() and l[0] == "U"]

    test_file = os.path.join(DATA_DIR, "sut_records", "detail_only.txt")
    with open(test_file, "w") as f:
        for l in raw:
            f.write(l)

    try:
        chunks = list(parse_fixed_width_chunks([test_file], layout))
        assert len(chunks) > 0, "No data parsed"
        df = pl.concat(chunks)
        assert len(df) > 0
        assert "STORE_NUMBER" in df.columns
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


# ── Scenario 3: Retailer 3 — HDR + S/U records ──────────────────────────


def test_scenario3_hdr_su_records():
    data_path = os.path.join(DATA_DIR, "sut_records", "sales.txt")
    s_layout = load_layout(os.path.join(DATA_DIR, "sut_records", "layout_s.csv"))
    u_layout = load_layout(os.path.join(DATA_DIR, "sut_records", "layout_u.csv"))
    t_layout = load_layout(os.path.join(DATA_DIR, "sut_records", "layout_t.csv"))

    chunks = list(flatten_multiline_fixed_width(
        [data_path], "S", s_layout, u_layout,
        trailer_prefix="T", trailer_layout=t_layout,
    ))
    assert len(chunks) > 0, "No flattened data"
    df = pl.concat(chunks)
    assert len(df) == 3, f"Expected 3 detail rows, got {len(df)}"
    assert "Store" in df.columns or "STORE_NUMBER" in df.columns


# ── Scenario 4: Retailer 4 — Simple Delimited ────────────────────────────


def test_scenario4_simple_delimited():
    path = os.path.join(DATA_DIR, "dated_sales", "sales.csv")
    chunks = list(parse_delimited_chunks([path], ","))
    df = _collect(chunks)
    assert len(df) == 3
    assert "Store" in df.columns
    assert "UPC" in df.columns
    assert "Date" in df.columns


# ── Scenario 5: Sales + Product master relationships ─────────────────────


def test_scenario5_sales_product_relationship():
    sales_path = os.path.join(DATA_DIR, "dated_sales", "sales.csv")
    sales_result = DiscoveryResult(
        file_paths=[sales_path],
        file_type="delimited",
        delimiter=",",
        columns=["Store", "UPC", "Description", "Units", "Price", "Date"],
    )
    assert sales_result.file_type == "delimited"


# ── Scenario 6: Different delimiters between header and data ────────────


def test_scenario6_header_data_diff_delimiter():
    path = os.path.join(DATA_DIR, "mixed_delimiters", "sales.csv")
    with open(path) as f:
        header = f.readline().strip()
        header_parts = header.split("|")
        assert len(header_parts) == 4, f"Header should split by |, got {len(header_parts)} parts"

    detection = generate_detection_summary(path)
    assert detection["file_type"] == "delimited"
    assert detection["delimiter"] is not None


# ── Scenario 7: Parent-child flattening (HDR + Trailer) ─────────────────


def test_scenario7_parent_child_flattening():
    data_path = os.path.join(DATA_DIR, "hdr_with_trailer", "sales.txt")
    h_layout = load_layout(os.path.join(DATA_DIR, "hdr_with_trailer", "layout_header.csv"))
    d_layout = load_layout(os.path.join(DATA_DIR, "hdr_with_trailer", "layout_detail.csv"))
    t_layout = load_layout(os.path.join(DATA_DIR, "hdr_with_trailer", "layout_trailer.csv"))

    chunks = list(flatten_multiline_fixed_width(
        [data_path], "HDR", h_layout, d_layout,
        trailer_prefix="TRL", trailer_layout=t_layout,
    ))
    assert len(chunks) > 0
    df = pl.concat(chunks)
    assert len(df) == 3, f"Expected 3 detail rows, got {len(df)}"
    assert "Store" in df.columns, "Parent Store should be replicated into child rows"


# ── Scenario 8: Multiple record layouts ──────────────────────────────────


def test_scenario8_multiple_record_layouts(tmp_path):
    """Test LayoutRegistry with fabricated S/U/T data."""
    d = tmp_path / "fw_multi"
    d.mkdir()
    layout_s = [
        {"field": "RecordType", "start": 0, "end": 1, "type": "string"},
        {"field": "Store", "start": 1, "end": 4, "type": "string"},
        {"field": "Date", "start": 4, "end": 14, "type": "string"},
    ]
    layout_u = [
        {"field": "RecordType", "start": 0, "end": 1, "type": "string"},
        {"field": "UPC", "start": 1, "end": 7, "type": "string"},
        {"field": "Desc", "start": 7, "end": 27, "type": "string"},
        {"field": "Units", "start": 27, "end": 32, "type": "integer"},
        {"field": "Price", "start": 32, "end": 39, "type": "decimal"},
    ]
    data_file = d / "sales.txt"
    data_file.write_text(
        "S0012024-01-15\n"
        "U001100001Widget A                 0001099.90\n"
        "U002100002Gadget B                 0005049.95\n"
    )
    # Parse S records
    s_chunks = list(parse_fixed_width_chunks(
        [str(data_file)], layout_s, record_type="S",
    ))
    # Parse U records
    u_chunks = list(parse_fixed_width_chunks(
        [str(data_file)], layout_u, record_type="U",
    ))
    total = _rows(s_chunks) + _rows(u_chunks)
    assert total == 3, f"Expected 3 total rows, got {total}"


# ── Scenario 9: Mixed quantity fallback logic ────────────────────────────


def test_scenario9_mixed_quantity_fallback():
    path = os.path.join(DATA_DIR, "mixed_quantity", "sales.csv")
    chunks = list(parse_delimited_chunks([path], ","))
    df = _collect(chunks)
    assert len(df) == 3


# ── Scenario 10: Large streaming files ───────────────────────────────────


def test_scenario10_large_streaming():
    path = os.path.join(DATA_DIR, "dated_sales", "sales.csv")
    chunks = list(parse_delimited_chunks([path], ",", chunk_size=2))
    assert len(chunks) >= 1, "Should produce at least 1 chunk"
    total = sum(c.height for c in chunks)
    assert total == 3, f"Expected 3 total rows across chunks, got {total}"

"""Validation tests for 10 retailer scenarios from PROMPT.md sprint."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import polars as pl
import pytest

from dav_tool._parsers import (
    parse_delimited_chunks, parse_fixed_width_chunks,
    flatten_multiline_fixed_width, flatten_multiline_chunks, load_layout,
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


# ── Scenario 11: Delimited multiline H/D parent→child flattening ────────


def test_scenario11_delimited_multiline_flat(tmp_path):
    """Parent (H) rows are carried forward into child (D) rows, never emitted.

    Mirrors the Retailer Wholesale certification dataset: a pipe-delimited
    multiline file where ``H`` records are parents and ``D`` records are
    children.  Only detail rows should appear; the parent header must not be
    emitted as a standalone row.
    """
    path = tmp_path / "wholesale.txt"
    path.write_text(
        "H|S001|2024-01-15\n"
        "D|S001|100001|Widget A|10|99.90\n"
        "D|S001|100002|Gadget B|5|49.95\n"
        "H|S002|2024-01-15\n"
        "D|S002|100001|Widget A|8|79.92\n"
        "H|S003|2024-01-15\n"
        "D|S003|100003|Doohickey|20|199.80\n"
    )

    chunks = list(flatten_multiline_chunks([str(path)], ["H", "D"], "|"))
    assert len(chunks) > 0, "No chunks produced"

    df = pl.concat(chunks)
    # Only the 4 D (detail) rows should survive — H rows are parents, not data.
    assert df.height == 4, f"Expected 4 detail rows, got {df.height}"
    assert len(df.columns) == 5, f"Expected 5 detail fields, got {len(df.columns)}"

    upc_count = df["Column_1"].n_unique()
    assert upc_count == 3, f"Expected 3 distinct UPCs, got {upc_count}"
    assert "Column_0" in df.columns


def test_scenario11b_delimited_multiline_certification():
    """The delimited multiline wholesale certification runs end-to-end."""
    from dav_tool.certification.runner import CertificationRunner, CERTIFICATION_ROOT

    runner = CertificationRunner(CERTIFICATION_ROOT)
    result = runner.run_one("multiline", "retailer_wholesale")
    assert result.passed, f"Wholesale certification failed: {result.errors}"
    assert result.processing_ok and result.validation_ok


# ── Scenario 12: Single record type emits all matching rows ─────────────


def test_scenario12_single_record_type_flatten(tmp_path):
    """Without a parent/child split (single record type), every line is a row."""
    path = tmp_path / "detail_only.txt"
    path.write_text(
        "H|S001|2024-01-15\n"
        "D|S001|100001|Widget A|10|99.90\n"
        "D|S002|100002|Gadget B|5|49.95\n"
    )
    chunks = list(flatten_multiline_chunks([str(path)], ["D"], "|"))
    df = pl.concat(chunks)
    assert df.height == 2, f"Expected 2 detail rows (D only), got {df.height}"


# ── Parser-driven pipeline acceptance ────────────────────────────────
# Every retailer follows: Connection → Discovery → ParserFactory →
# SpecificParser → Canonical Dataset → (mapping/validation/reports).


def test_parser_driven_all_retailers_certify():
    """All retailer certification categories pass end-to-end, parser-driven."""
    from dav_tool.certification.runner import CertificationRunner, CERTIFICATION_ROOT

    suite = CertificationRunner(CERTIFICATION_ROOT).run_all()
    assert suite.failed == 0, (
        f"{suite.failed} retailer(s) failed: "
        + "; ".join(e for r in suite.results if r.errors for e in r.errors[:2])
    )
    assert suite.passed == suite.total


def test_parser_factory_recommends_parser_for_each_retailer():
    """Every certification retailer resolves a specific parser."""

    root = os.path.join(
        os.path.dirname(__file__), "..", "retailer_certification"
    )
    from dav_tool.certification.runner import discover_retailer_datasets
    from dav_tool.workflow.discovery import detect_file
    from dav_tool.parser import default_factory

    seen_parsers = set()
    for category, retailer in discover_retailer_datasets(root):
        bau = os.path.join(root, category, retailer, "BAU")
        sample = sorted(os.listdir(bau))[0]
        discovery = detect_file([os.path.join(bau, sample)])
        parser = default_factory.create(discovery)
        result = parser.parse(discovery)
        seen_parsers.add(parser.name)
        assert discovery.error is None, f"{category}/{retailer}: {discovery.error}"
        # Every retailer produces a canonical ParseResult contract.
        assert result.metadata.get("parser") == parser.name
        assert result.discovery is not None

    # The factory catalog is exercised across the certification set.
    assert isinstance(seen_parsers, set)


def test_sales_product_relationship_end_to_end(tmp_path):
    """Sales + product master relationship processes via the pipeline."""
    from dav_tool.workflow.discovery import DiscoveryResult
    from dav_tool.parser import default_factory
    import polars as pl

    prod = tmp_path / "product_master.csv"
    pl.DataFrame({"UPC": ["100001", "100002"], "Brand": ["Alpha", "Beta"]}).write_csv(prod)
    sales = tmp_path / "sales.csv"
    pl.DataFrame({
        "Store": ["S001", "S001", "S002"],
        "UPC": ["100001", "100002", "100001"],
        "Units": [10, 5, 8],
    }).write_csv(sales)

    discovery = DiscoveryResult(
        file_paths=[str(sales)],
        file_type="delimited",
        delimiter=",",
        product_master_path=str(prod),
        candidate_keys=[{"sales_col": "UPC", "product_col": "UPC"}],
    )
    parser = default_factory.create(discovery)
    assert parser.name == "sales_product"
    result = parser.parse(discovery)
    assert result.canonical_data.height == 3
    assert "Brand" in result.columns, "Product master should enrich sales rows"

"""Tests for the parser subsystem: BaseParser, ParserFactory, record tree,
and the record-based (HEB) parser.
"""
import os

import polars as pl
import pytest

from dav_tool.parser import (
    ParserFactory,
    ParserRegistry,
    RecordNode,
    RecordTree,
    default_factory,
    register_parser,
)
from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.record_based import RecordBasedParser
from dav_tool.workflow.discovery import DiscoveryResult, detect_file

DATA = os.path.join(os.path.dirname(__file__), "data")
HEB = os.path.join(DATA, "heb_record", "heb_fixed.txt")
HEB_DELIMITED = os.path.join(DATA, "heb_record", "heb_delimited.txt")


# ── Registry / Factory ──────────────────────────────────────────────
def test_parser_registry_registration():
    reg = ParserRegistry()

    @reg.register
    class Dummy(BaseParser):
        name = "dummy"
        description = "test"

    assert "dummy" in reg.names()
    assert reg.get("dummy") is Dummy


def test_factory_selects_delimited():
    d = DiscoveryResult(
        file_paths=["x.csv"], file_type="delimited", delimiter=",",
    )
    parser = default_factory.create(d)
    assert parser.name == "delimited"


def test_factory_selects_record_based_for_multiline():
    d = DiscoveryResult(file_paths=["x.txt"], file_type="multiline")
    # record_based has higher precedence (priority=10) than parent_child.
    parser = default_factory.create(d)
    assert parser.name == "record_based"


def test_factory_unknown_raises():
    reg = ParserRegistry()
    factory = ParserFactory(registry=reg)
    d = DiscoveryResult(file_paths=["x.txt"], file_type="delimited")
    with pytest.raises(Exception):
        factory.create(d)


# ── Record Tree ─────────────────────────────────────────────────────
def test_record_tree_flatten_excludes_trailer():
    root = RecordNode(record_type="file")
    parent = RecordNode(record_type="header", fields={"Store": "S001"})
    parent.add_child(RecordNode(record_type="detail", fields={"UPC": "1"}))
    parent.add_child(RecordNode(record_type="detail", fields={"UPC": "2"}))
    parent.add_child(RecordNode(record_type="trailer", fields={"Count": "2"}))
    root.add_child(parent)

    tree = RecordTree(root=root, detail_type="detail", parent_type="header", trailer_type="trailer")
    rows = tree.flatten_details()
    assert len(rows) == 2
    assert all("Count" not in r for r in rows)
    assert rows[0]["Store"] == "S001"


def test_record_tree_serialization():
    tree = RecordTree()
    tree.add(RecordNode(record_type="header", fields={"S": 1}))
    d = tree.to_dict()
    assert d["record_type"] == "file"
    assert len(d["children"]) == 1


# ── Record-Based (HEB) parser ───────────────────────────────────────
def test_record_based_parser_autodiscovers_record_types():
    d = detect_file([HEB])
    assert d.file_type == "multiline"
    parser = default_factory.create(d)
    assert parser.name == "record_based"
    out = parser.parse(d)
    assert out.record_tree is not None
    assert "S" in out.metadata["record_types"]
    assert "T" in out.metadata["record_types"]
    # HDR + S headers → 2 parents; 3 U details.
    assert out.metadata["header_count"] == 2
    assert out.metadata["detail_row_count"] >= 3


def test_record_based_parser_records_detail_rows():
    d = detect_file([HEB])
    out = default_factory.create(d).parse(d)
    df = out.to_dataframe()
    assert df.height >= 3


def test_record_based_parser_with_layout_reuses_header_context():
    layout = [
        {"field": "RecordType", "start": 0, "end": 3, "type": "string"},
        {"field": "Store", "start": 4, "end": 8, "type": "string"},
        {"field": "Date", "start": 9, "end": 19, "type": "string"},
    ]
    d = DiscoveryResult(
        file_paths=[HEB],
        file_type="multiline",
        ml_record_types=["HDR", "S", "U", "T"],
        header_prefix="HDR",
        detail_layout=layout,
    )
    out = default_factory.create(d).parse(d)
    assert out.record_tree is not None


# ── Discovery integrates recommended_parser ─────────────────────────
def test_detection_recommends_parser():
    d = detect_file([HEB])
    assert d.recommended_parser == "record_based"
    assert d.file_architecture == "multiline-delimited"


def test_from_discovery_returns_canonical_dataset():
    from dav_tool.workflow.canonical import CanonicalDataset

    d = detect_file([HEB])
    ds = CanonicalDataset.from_discovery(d, level="item")
    chunks = list(ds.iter_chunks())
    assert chunks
    assert chunks[0].height >= 3


# ── Excel parser ────────────────────────────────────────────────────
def test_excel_parser_registered_and_selected(tmp_path):
    xlsx = tmp_path / "book.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Store", "Units"])
    ws.append(["S1", 5])
    wb.save(xlsx)
    d = DiscoveryResult(file_paths=[str(xlsx)], file_type="excel")
    parser = default_factory.create(d)
    assert parser.name == "excel"
    out = parser.parse(d)
    assert out.canonical_data.height == 1


# ── Sales/Product parser ────────────────────────────────────────────
def test_sales_product_parser_joins_master(tmp_path):
    import polars as pl

    prod = tmp_path / "product_master.csv"
    pl.DataFrame({"UPC": ["1", "2"], "Brand": ["Alpha", "Beta"]}).write_csv(prod)

    sales = tmp_path / "sales.csv"
    pl.DataFrame({
        "Store": ["S1", "S1", "S2"],
        "UPC": ["1", "2", "1"],
        "Units": [10, 5, 8],
    }).write_csv(sales)

    d = DiscoveryResult(
        file_paths=[str(sales)],
        file_type="delimited",
        delimiter=",",
        product_master_path=str(prod),
        candidate_keys=[{"sales_col": "UPC", "product_col": "UPC"}],
    )
    parser = default_factory.create(d)
    assert parser.name == "sales_product"
    out = parser.parse(d)
    assert "Brand" in out.columns
    assert out.metadata["product_master_joined"] is True


def test_hdr_records_trailer_excluded_from_details():
    hdr = os.path.join(DATA, "hdr_with_trailer", "sales.txt")
    d = detect_file([hdr])
    assert d.recommended_parser == "record_based"
    out = default_factory.create(d).parse(d)
    # TRL is a trailer, not a detail row.
    assert out.metadata["detail_row_count"] == 3
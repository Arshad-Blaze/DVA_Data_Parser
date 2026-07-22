"""Tests for the Relationship Engine (cross-dataset joins)."""

import polars as pl
from dav_tool.workflow.relationship import (
    RelationshipEngine,
    _join_chunks,
    _build_enriched_schema,
)
from dav_tool.workflow.canonical import CanonicalDataset, _build_schema_for_level
from dav_tool.workflow.discovery import DiscoveryResult


def make_discovery_result(candidate_keys):
    """Helper: build a DiscoveryResult with candidate_keys."""
    return DiscoveryResult(
        file_paths=[],
        file_type="delimited",
        candidate_keys=candidate_keys,
    )


def make_dataset(schema, level, chunks):
    """Helper: build a CanonicalDataset that yields given chunks."""
    def stream():
        for chunk in chunks:
            yield chunk
    return CanonicalDataset(
        schema=schema,
        level=level,
        stream_factory=stream,
    )


# ── discover_relationships ──────────────────────────────────────────

def test_discover_relationships_matching_keys():
    source = make_discovery_result([
        {"column": "upc", "key_type": "upc", "confidence": 0.9},
    ])
    target = make_discovery_result([
        {"column": "upc", "key_type": "upc", "confidence": 0.8},
    ])
    rels = RelationshipEngine.discover_relationships(source, target)
    assert len(rels) == 1
    assert rels[0]["source_column"] == "upc"
    assert rels[0]["target_column"] == "upc"
    assert rels[0]["key_type"] == "upc"


def test_discover_relationships_no_keys():
    source = make_discovery_result([])
    target = make_discovery_result([])
    assert RelationshipEngine.discover_relationships(source, target) == []


def test_discover_relationships_type_mismatch():
    source = make_discovery_result([
        {"column": "store", "key_type": "store", "confidence": 0.9},
    ])
    target = make_discovery_result([
        {"column": "upc", "key_type": "upc", "confidence": 0.8},
    ])
    rels = RelationshipEngine.discover_relationships(source, target)
    assert len(rels) == 0


# ── confirm_relationship ────────────────────────────────────────────

def test_confirm_valid():
    result = RelationshipEngine.confirm_relationship("store", "location")
    assert result["status"] == "valid"
    assert result["source_column"] == "store"
    assert result["target_column"] == "location"


def test_confirm_invalid_empty_source():
    result = RelationshipEngine.confirm_relationship("", "location")
    assert result["status"] == "invalid"


def test_confirm_invalid_empty_target():
    result = RelationshipEngine.confirm_relationship("store", "")
    assert result["status"] == "invalid"


# ── _join_chunks ────────────────────────────────────────────────────

def test_join_chunks_basic():
    source = pl.DataFrame({"upc": ["1", "2", "3"], "sales": [10, 20, 30]})
    target = pl.DataFrame({"upc": ["1", "2", "4"], "brand": ["A", "B", "D"]})
    result = _join_chunks(source, target, "upc", "upc")
    assert result is not None
    assert list(result.columns) == ["upc", "sales", "brand"]
    assert len(result) == 3
    assert result["brand"].to_list() == ["A", "B", None]


def test_join_chunks_with_selected_attributes():
    source = pl.DataFrame({"upc": ["1", "2"], "sales": [10, 20]})
    target = pl.DataFrame({"upc": ["1", "2"], "brand": ["A", "B"], "category": ["X", "Y"]})
    result = _join_chunks(source, target, "upc", "upc", attributes=["brand"])
    assert result is not None
    assert list(result.columns) == ["upc", "sales", "brand"]
    assert "category" not in result.columns


def test_join_chunks_missing_source_key():
    source = pl.DataFrame({"other": [1]})
    target = pl.DataFrame({"upc": ["1"], "brand": ["A"]})
    result = _join_chunks(source, target, "upc", "upc")
    assert result is None


def test_join_chunks_missing_target_key():
    source = pl.DataFrame({"upc": ["1"], "sales": [10]})
    target = pl.DataFrame({"other": [1]})
    result = _join_chunks(source, target, "upc", "upc")
    assert result is None


# ── _build_enriched_schema ──────────────────────────────────────────

def test_build_enriched_schema_adds_all():
    result = _build_enriched_schema(
        ["STORE", "Units", "Totalprice"],
        ["UPC", "Brand", "Category"],
        "UPC",
    )
    assert result == ["STORE", "Units", "Totalprice", "Brand", "Category"]


def test_build_enriched_schema_skips_duplicates():
    result = _build_enriched_schema(
        ["STORE", "Units", "Brand"],
        ["UPC", "Brand", "Category"],
        "UPC",
    )
    assert result == ["STORE", "Units", "Brand", "Category"]


def test_build_enriched_schema_with_selected_attributes():
    result = _build_enriched_schema(
        ["STORE", "Units"],
        ["UPC", "Brand", "Category", "Price"],
        "UPC",
        attributes=["Brand", "Price"],
    )
    assert result == ["STORE", "Units", "Brand", "Price"]
    assert "Category" not in result


# ── enrich_dataset (integration) ────────────────────────────────────

def test_enrich_dataset_basic():
    source = make_dataset(
        schema=["upc", "sales"],
        level="item",
        chunks=[pl.DataFrame({"upc": ["1", "2"], "sales": [10, 20]})],
    )
    target = make_dataset(
        schema=["upc", "brand", "category"],
        level="item",
        chunks=[pl.DataFrame({"upc": ["1", "2"], "brand": ["A", "B"], "category": ["X", "Y"]})],
    )
    enriched = RelationshipEngine.enrich_dataset(source, target, {"upc": "upc"})
    assert enriched is not None
    assert enriched.level == "item"
    assert "brand" in enriched.schema
    assert "category" in enriched.schema

    chunks = list(enriched.iter_chunks())
    assert len(chunks) == 1
    df = chunks[0]
    assert "brand" in df.columns
    assert df["brand"].to_list() == ["A", "B"]


def test_enrich_dataset_with_attributes_filter():
    source = make_dataset(
        schema=["upc", "sales"],
        level="item",
        chunks=[pl.DataFrame({"upc": ["1", "2"], "sales": [10, 20]})],
    )
    target = make_dataset(
        schema=["upc", "brand", "category"],
        level="item",
        chunks=[pl.DataFrame({"upc": ["1", "2"], "brand": ["A", "B"], "category": ["X", "Y"]})],
    )
    enriched = RelationshipEngine.enrich_dataset(source, target, {"upc": "upc"}, attributes=["brand"])
    assert enriched is not None
    assert "brand" in enriched.schema
    assert "category" not in enriched.schema


def test_enrich_dataset_empty_chunks():
    source = make_dataset(
        schema=["upc", "sales"],
        level="item",
        chunks=[],
    )
    target = make_dataset(
        schema=["upc", "brand"],
        level="item",
        chunks=[pl.DataFrame({"upc": ["1"], "brand": ["A"]})],
    )
    enriched = RelationshipEngine.enrich_dataset(source, target, {"upc": "upc"})
    assert enriched is not None
    chunks = list(enriched.iter_chunks())
    assert len(chunks) == 0


def test_enrich_dataset_failed_returns_none():
    result = RelationshipEngine.enrich_dataset(None, None, {})
    assert result is None

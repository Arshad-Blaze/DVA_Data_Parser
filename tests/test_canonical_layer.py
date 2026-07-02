"""Tests for the canonical data layer (normalizer)."""
import polars as pl
from dav_tool._normalizer import (
    apply_column_names,
    store_normalize_exprs,
    normalize_store_chunk,
    item_normalize_exprs,
    normalize_item_chunk,
    upc_normalize_exprs,
    normalize_upc_chunk,
)
from dav_tool._aggregators import stream_store_aggregate


def test_apply_column_names():
    df = pl.DataFrame({"Column_0": ["S1"], "Column_1": ["10"], "Column_2": ["50"]})
    result = apply_column_names(df, ["Store", "Units", "Price"])
    assert list(result.columns) == ["Store", "Units", "Price"]


def test_apply_column_names_none():
    df = pl.DataFrame({"Store": ["S1"]})
    result = apply_column_names(df, None)
    assert list(result.columns) == ["Store"]


def test_store_normalize_exprs():
    exprs = store_normalize_exprs("Store", "Units", "Price", False, False, "Total Price")
    assert len(exprs) == 3


def test_store_normalize_exprs_implied():
    exprs = store_normalize_exprs("Store", "Units", "Price", True, True, "Total Price")
    assert len(exprs) == 3


def test_store_normalize_exprs_unit_price():
    exprs = store_normalize_exprs("Store", "Units", "Price", False, False, "Unit Price")
    assert len(exprs) == 3


def test_normalize_store_chunk():
    df = pl.DataFrame({"Store": ["S1"], "Units": ["10"], "Price": ["50"]})
    result = normalize_store_chunk(df, "Store", "Units", "Price", False, False, "Total Price")
    assert "STORE_NUMBER" in result.columns
    assert "Units" in result.columns
    assert "Totalprice" in result.columns
    assert result["Units"].dtype == pl.Float64


def test_normalize_store_chunk_implied():
    df = pl.DataFrame({"Store": ["S1"], "Units": ["1000"], "Price": ["5000"]})
    result = normalize_store_chunk(df, "Store", "Units", "Price", True, True, "Total Price")
    assert result["Units"].to_list()[0] == 10.0
    assert result["Totalprice"].to_list()[0] == 50.0


def test_normalize_store_chunk_unit_price():
    df = pl.DataFrame({"Store": ["S1"], "Units": ["10"], "Price": ["5"]})
    result = normalize_store_chunk(df, "Store", "Units", "Price", False, False, "Unit Price")
    assert result["Totalprice"].to_list()[0] == 50.0


def test_normalize_store_chunk_unit_price_implied():
    df = pl.DataFrame({"Store": ["S1"], "Units": ["1000"], "Price": ["500"]})
    result = normalize_store_chunk(df, "Store", "Units", "Price", True, True, "Unit Price")
    assert result["Units"].to_list()[0] == 10.0
    assert result["Totalprice"].to_list()[0] == 50.0


def test_normalize_store_chunk_unit_price_delimited(tmp_path):
    import csv
    file = tmp_path / "test.csv"
    with open(file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "Units", "Price"])
        w.writerow(["S1", 10, 5])
    # Delimited path uses store_normalize_exprs (lazy), not normalize_store_chunk
    result = stream_store_aggregate(
        [str(file)], "delimited", "Store", "Units", "Price",
        delimiter=",", price_type="Unit Price",
    )
    assert not result.is_empty()
    assert result["Totalprice"].to_list()[0] == 50.0


def test_normalize_item_chunk():
    df = pl.DataFrame({"UPC": ["1001"], "Desc": ["Widget"], "Units": ["10"], "Price": ["50"]})
    result = normalize_item_chunk(df, "UPC", "Desc", "Units", "Price", False, False)
    assert "UPC_CODE" in result.columns
    assert "PRODUCT_DESCRIPTION" in result.columns
    assert "UNITS_SOLD" in result.columns
    assert "TOTAL_DOLLARS" in result.columns


def test_normalize_item_chunk_implied():
    df = pl.DataFrame({"UPC": ["1001"], "Desc": ["Widget"], "Units": ["1000"], "Price": ["5000"]})
    result = normalize_item_chunk(df, "UPC", "Desc", "Units", "Price", True, True)
    assert result["UNITS_SOLD"].to_list()[0] == 10.0
    assert result["TOTAL_DOLLARS"].to_list()[0] == 50.0


def test_normalize_upc_chunk():
    df = pl.DataFrame({"UPC": ["1001"], "Units": ["10"], "Price": ["50"]})
    result = normalize_upc_chunk(df, "UPC", "Units", "Price", False, False)
    assert "UPC" in result.columns
    assert "UNITS_SOLD" in result.columns
    assert "TOTAL_DOLLARS" in result.columns


def test_upc_normalize_exprs():
    exprs = upc_normalize_exprs("UPC", "Units", "Price", False, False)
    assert len(exprs) == 3


def test_upc_normalize_exprs_implied():
    exprs = upc_normalize_exprs("UPC", "Units", "Price", True, True)
    assert len(exprs) == 3


def test_item_normalize_exprs():
    exprs = item_normalize_exprs("UPC", "Desc", "Units", "Price", False, False)
    assert len(exprs) == 4


def test_item_normalize_exprs_implied():
    exprs = item_normalize_exprs("UPC", "Desc", "Units", "Price", True, True)
    assert len(exprs) == 4


def test_normalize_empty_chunk():
    df = pl.DataFrame({"Store": pl.Series([], dtype=pl.Utf8), "Units": pl.Series([], dtype=pl.Utf8), "Price": pl.Series([], dtype=pl.Utf8)})
    result = normalize_store_chunk(df, "Store", "Units", "Price", False, False, "Total Price")
    assert result.is_empty()
    assert "STORE_NUMBER" in result.columns
    assert "Units" in result.columns

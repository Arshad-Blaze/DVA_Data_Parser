"""Tests for the canonical data layer (normalizer)."""
import csv
import os
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
from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate, stream_upc_summary
from dav_tool._parsers import flatten_multiline_fixed_width, preview_flattened_multiline_fixed


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


def test_multiline_canonical_equivalence_delimited(tmp_path):
    data = [
        ("S001", "100001", "Widget A", "10", "99.90"),
        ("S001", "100002", "Gadget B", "5", "49.95"),
        ("S002", "100001", "Widget A", "8", "79.92"),
        ("S003", "100003", "Doohickey", "20", "199.80"),
    ]
    csv_path = os.path.join(tmp_path, "single.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "UPC", "Description", "Units", "Price"])
        for row in data:
            w.writerow(row)

    ml_path = os.path.join(tmp_path, "multiline.txt")
    with open(ml_path, "w") as f:
        for store, upc, desc, units, price in data:
            f.write(f"H|{store}|2024-01-15\n")
            f.write(f"D|{store}|{upc}|{desc}|{units}|{price}\n")

    ml_cols = ["Store", "UPC", "Description", "Units", "Price"]
    single_store = stream_store_aggregate(
        [csv_path], "delimited", "Store", "Units", "Price", delimiter=","
    )
    ml_store = stream_store_aggregate(
        [ml_path], "multiline", "Store", "Units", "Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_cols,
    )
    assert single_store.shape == ml_store.shape, "Store agg shape mismatch"
    assert single_store.sort("STORE_NUMBER").to_dicts() == ml_store.sort("STORE_NUMBER").to_dicts(), (
        f"Store agg mismatch:\n{single_store.sort('STORE_NUMBER')}\n{ml_store.sort('STORE_NUMBER')}"
    )

    single_item = stream_item_aggregate(
        [csv_path], "delimited", "UPC", "Description", "Units", "Price", delimiter=","
    )
    ml_item = stream_item_aggregate(
        [ml_path], "multiline", "UPC", "Description", "Units", "Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_cols,
    )
    assert single_item.shape == ml_item.shape, "Item agg shape mismatch"
    assert single_item.sort("UPC_CODE").to_dicts() == ml_item.sort("UPC_CODE").to_dicts(), (
        f"Item agg mismatch:\n{single_item.sort('UPC_CODE')}\n{ml_item.sort('UPC_CODE')}"
    )

    single_upc = stream_upc_summary(
        [csv_path], "delimited", "UPC", "Units", "Price", delimiter=","
    )
    ml_upc = stream_upc_summary(
        [ml_path], "multiline", "UPC", "Units", "Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_cols,
    )
    assert single_upc.shape == ml_upc.shape, "UPC summary shape mismatch"
    assert single_upc.sort("UPC").to_dicts() == ml_upc.sort("UPC").to_dicts(), (
        f"UPC summary mismatch:\n{single_upc.sort('UPC')}\n{ml_upc.sort('UPC')}"
    )


def test_flatten_multiline_fixed_width_backward_compat(tmp_path):
    """No trailer params = old behavior preserved (chunk-based flush)."""
    f = tmp_path / "test.txt"
    f.write_text(
        "HDR001Store 1\n"
        "DTL001Item A\n"
        "DTL002Item B\n"
        "HDR002Store 2\n"
        "DTL003Item C\n"
    )
    hdr_layout = [{"field": "store", "start": 6, "end": 13, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 6, "end": 12, "type": "text"}]
    chunks = list(flatten_multiline_fixed_width(
        [str(f)], "HDR", hdr_layout, dtl_layout, chunk_size=10
    ))
    assert len(chunks) == 1, "No trailer = single chunk expected"
    df = chunks[0]
    assert len(df) == 3, "3 detail rows expected"
    assert "store" in df.columns
    assert "item" in df.columns


def test_flatten_multiline_fixed_width_with_trailer(tmp_path):
    """TRL groups HDR+DTLs into transaction, TRL fields attach to DTL rows."""
    f = tmp_path / "test.txt"
    f.write_text(
        "HDR001Store 1\n"
        "DTL001Item A\n"
        "DTL002Item B\n"
        "TRL001   100\n"
    )
    hdr_layout = [{"field": "store", "start": 6, "end": 13, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 6, "end": 12, "type": "text"}]
    trl_layout = [{"field": "total", "start": 9, "end": 12, "type": "numeric"}]
    chunks = list(flatten_multiline_fixed_width(
        [str(f)], "HDR", hdr_layout, dtl_layout, chunk_size=10,
        trailer_prefix="TRL", trailer_layout=trl_layout,
    ))
    assert len(chunks) == 1, "One TRL = one flush"
    df = chunks[0]
    assert len(df) == 2, "2 detail rows expected"
    assert "store" in df.columns
    assert "item" in df.columns
    assert "total" in df.columns
    assert df["total"].to_list() == ["100", "100"]


def test_flatten_multiline_fixed_width_trailer_chunk_size_ignored(tmp_path):
    """With trailer active, chunk_size is ignored — TRL controls flush."""
    f = tmp_path / "test.txt"
    lines = []
    for i in range(5):
        lines.append(f"HDR00{i}  Store{i}\n")
        lines.append(f"DTL00{i}  Item{i}\n")
        lines.append(f"TRL00{i}  {i*10:>3}\n")
    f.write_text("".join(lines))
    hdr_layout = [{"field": "store", "start": 8, "end": 16, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 8, "end": 16, "type": "text"}]
    trl_layout = [{"field": "total", "start": 8, "end": 12, "type": "numeric"}]
    chunks = list(flatten_multiline_fixed_width(
        [str(f)], "HDR", hdr_layout, dtl_layout, chunk_size=1,
        trailer_prefix="TRL", trailer_layout=trl_layout,
    ))
    assert len(chunks) == 5, "5 TRL = 5 flushes, ignoring chunk_size=1"
    for i, chunk in enumerate(chunks):
        assert len(chunk) == 1, f"Chunk {i}: 1 DTL expected"
        assert chunk["total"].to_list() == [str(i * 10)]


def test_flatten_multiline_fixed_width_trailer_no_trl_at_end(tmp_path):
    """HDR without trailing TRL at EOF yields remaining DTLs."""
    f = tmp_path / "test.txt"
    f.write_text(
        "HDR001Store 1\n"
        "DTL001Item A\n"
        "TRL001   100\n"
        "HDR002Store 2\n"
        "DTL002Item B\n"
    )
    hdr_layout = [{"field": "store", "start": 6, "end": 13, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 6, "end": 12, "type": "text"}]
    trl_layout = [{"field": "total", "start": 9, "end": 12, "type": "numeric"}]
    chunks = list(flatten_multiline_fixed_width(
        [str(f)], "HDR", hdr_layout, dtl_layout, chunk_size=10,
        trailer_prefix="TRL", trailer_layout=trl_layout,
    ))
    assert len(chunks) == 2
    assert len(chunks[0]) == 1
    assert "store" in chunks[0].columns
    assert "total" in chunks[0].columns
    assert chunks[0]["store"].to_list() == ["Store 1"]
    assert chunks[0]["total"].to_list() == ["100"]
    assert len(chunks[1]) == 1
    assert "store" in chunks[1].columns
    assert "total" not in chunks[1].columns


def test_flatten_multiline_fixed_width_multiple_transactions(tmp_path):
    """Multiple HDR-DTLs-TRL groups all produce separate transactions."""
    f = tmp_path / "multitxn.txt"
    f.write_text(
        "HDR001Store A\n"
        "DTL001Item 1\n"
        "DTL002Item 2\n"
        "TRL001 1000\n"
        "HDR002Store B\n"
        "DTL003Item 3\n"
        "TRL002 2000\n"
    )
    hdr_layout = [{"field": "store", "start": 6, "end": 13, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 6, "end": 13, "type": "text"}]
    trl_layout = [{"field": "total", "start": 7, "end": 11, "type": "numeric"}]
    chunks = list(flatten_multiline_fixed_width(
        [str(f)], "HDR", hdr_layout, dtl_layout, chunk_size=10,
        trailer_prefix="TRL", trailer_layout=trl_layout,
    ))
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert chunks[0]["store"].to_list() == ["Store A", "Store A"]
    assert chunks[0]["total"].to_list() == ["1000", "1000"]
    assert len(chunks[1]) == 1
    assert chunks[1]["store"].to_list() == ["Store B"]
    assert chunks[1]["total"].to_list() == ["2000"]


def test_preview_flattened_multiline_fixed_with_trailer(tmp_path):
    """Preview function correctly passes trailer params through."""
    f = tmp_path / "preview.txt"
    f.write_text(
        "HDR001Store 1\n"
        "DTL001Item A\n"
        "DTL002Item B\n"
        "TRL001   100\n"
    )
    hdr_layout = [{"field": "store", "start": 6, "end": 13, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 6, "end": 12, "type": "text"}]
    trl_layout = [{"field": "total", "start": 9, "end": 12, "type": "numeric"}]
    result = preview_flattened_multiline_fixed(
        [str(f)], "HDR", hdr_layout, dtl_layout, n_rows=5,
        trailer_prefix="TRL", trailer_layout=trl_layout,
    )
    assert len(result) == 2
    assert "total" in result.columns
    assert result["total"].to_list() == ["100", "100"]


def test_flatten_multiline_fixed_width_trailer_no_trailer_layout(tmp_path):
    """TRL with prefix but no layout still flushes; no extra columns."""
    f = tmp_path / "test.txt"
    f.write_text(
        "HDR001Store 1\n"
        "DTL001Item A\n"
        "TRL001   100\n"
    )
    hdr_layout = [{"field": "store", "start": 6, "end": 13, "type": "text"}]
    dtl_layout = [{"field": "item", "start": 6, "end": 12, "type": "text"}]
    chunks = list(flatten_multiline_fixed_width(
        [str(f)], "HDR", hdr_layout, dtl_layout, chunk_size=10,
        trailer_prefix="TRL",
    ))
    assert len(chunks) == 1
    df = chunks[0]
    assert len(df) == 1
    assert df["store"].to_list() == ["Store 1"]
    assert "total" not in df.columns

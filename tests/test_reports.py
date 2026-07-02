"""Tests for the Reports layer."""
import csv
import polars as pl
from dav_tool._reports import generate_file_review
from dav_tool.validation.store import storelevelvalidation
from dav_tool.validation.item import run_item_validation


def test_generate_file_review_basic(tmp_path):
    file = tmp_path / "data.csv"
    with open(file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "UPC", "Desc", "Units", "Price"])
        w.writerow(["S1", "1001", "Widget", "10", "50"])
        w.writerow(["S2", "1002", "Gadget", "5", "25"])
    result = generate_file_review(
        [str(file)], "delimited", "Store", "UPC", "Units", "Price",
        delimiter=",",
    )
    assert not result.is_empty()
    assert "filename" in result.columns
    assert result["store_count"].to_list()[0] == 2
    assert result["upc_count"].to_list()[0] == 2
    assert result["total_units"].to_list()[0] == 15.0


def test_generate_file_review_empty(tmp_path):
    file = tmp_path / "empty.csv"
    file.write_text("Store,UPC,Desc,Units,Price\n")
    result = generate_file_review(
        [str(file)], "delimited", "Store", "UPC", "Units", "Price",
        delimiter=",",
    )
    assert not result.is_empty()
    assert result["store_count"].to_list()[0] == 0


def test_generate_file_review_multiple_files(tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"data_{i}.csv"
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Store", "UPC", "Desc", "Units", "Price"])
            w.writerow([f"S{i}", f"10{i:03d}", "Item", "5", "25"])
        paths.append(str(p))
    result = generate_file_review(
        paths, "delimited", "Store", "UPC", "Units", "Price",
        delimiter=",",
    )
    assert len(result) == 3


def test_storelevelvalidation_summary_cache(tmp_path):
    prod_file = tmp_path / "prod.csv"
    test_file = tmp_path / "test.csv"
    with open(prod_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "Units", "Price"])
        w.writerow(["S1", 10, 100])
    with open(test_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "Units", "Price"])
        w.writerow(["S1", 10, 100])
    prod_agg = pl.DataFrame({"STORE_NUMBER": ["S1"], "Units": [10.0], "Totalprice": [100.0]})
    test_agg = prod_agg.clone()
    result = storelevelvalidation(
        [str(prod_file)], [str(test_file)],
        "delimited", "delimited", ",", ",", None, None,
        "Store", "Units", "Price", "Store", "Units", "Price",
        "Total Price", "Total Price",
        False, False, False, False,
        prod_summary=prod_agg, test_summary=test_agg,
    )
    assert not result.is_empty()


def test_item_validation_summary_cache(tmp_path):
    prod_file = tmp_path / "prod.csv"
    test_file = tmp_path / "test.csv"
    with open(prod_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["UPC", "Desc", "Units", "Price"])
        w.writerow(["1001", "Widget", 10, 100])
    with open(test_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["UPC", "Desc", "Units", "Price"])
        w.writerow(["1001", "Widget", 10, 100])
    bau_agg = pl.DataFrame({"UPC_CODE": ["1001"], "PRODUCT_DESCRIPTION": ["Widget"], "UNITS_SOLD": [10.0], "TOTAL_DOLLARS": [100.0]})
    test_agg = bau_agg.clone()
    comparison, summary = run_item_validation(
        [str(prod_file)], [str(test_file)],
        "delimited", "delimited", ",", ",", None, None,
        "UPC", "Desc", "Units", "Price",
        bau_summary=bau_agg, test_summary=test_agg,
    )
    assert not comparison.is_empty()
    assert not summary.is_empty()

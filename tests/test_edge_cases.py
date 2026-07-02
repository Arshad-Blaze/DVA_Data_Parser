"""Edge case tests: empty files, corrupt data, duplicates, encodings."""
import polars as pl
import csv
from dav_tool.io import safe_read_csv
from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate
from dav_tool._parsers import scan_delimited, parse_fixed_width_chunks
from dav_tool.validation.store import compare_files, storelevelvalidation_from_df


def test_empty_csv(tmp_path):
    file = tmp_path / "empty.csv"
    file.write_text("")
    result = safe_read_csv(str(file))
    assert result.is_empty()


def test_empty_csv_header_only(tmp_path):
    file = tmp_path / "header.csv"
    file.write_text("a,b,c\n")
    result = safe_read_csv(str(file))
    assert result.is_empty() or len(result.columns) == 3


def test_empty_csv_only_header(tmp_path):
    # Delimited file with header but no data rows returns empty aggregation
    file = tmp_path / "header.csv"
    file.write_text("Store,Units,Price\n")
    result = stream_store_aggregate(
        [str(file)], "delimited", "Store", "Units", "Price", delimiter=",",
    )
    assert result.is_empty()


def test_corrupt_csv(tmp_path):
    file = tmp_path / "corrupt.csv"
    file.write_text("a,b\n1,2\nbad,line\ntoo,many,cols\n")
    result = safe_read_csv(str(file))
    assert not result.is_empty()


def test_duplicate_stores( tmp_path):
    file = tmp_path / "dups.csv"
    with open(file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "Units", "Price"])
        w.writerows([["S1", 5, 25], ["S1", 10, 50], ["S2", 3, 15]])
    result = stream_store_aggregate(
        [str(file)], "delimited", "Store", "Units", "Price", delimiter=",",
    )
    assert not result.is_empty()
    s1 = result.filter(pl.col("STORE_NUMBER") == "S1")
    assert s1["Units"].to_list()[0] == 15
    assert s1["Totalprice"].to_list()[0] == 75


def test_duplicate_upcs(tmp_path):
    file = tmp_path / "dup_upcs.csv"
    with open(file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["UPC", "Desc", "Units", "Price"])
        w.writerows([
            ["1001", "Widget", 5, 25],
            ["1001", "Widget", 3, 15],
        ])
    result = stream_item_aggregate(
        [str(file)], "delimited", "UPC", "Desc", "Units", "Price", delimiter=",",
    )
    assert not result.is_empty()
    row = result.filter(pl.col("UPC_CODE") == "1001")
    assert row["UNITS_SOLD"].to_list()[0] == 8


def test_mixed_encoding_utf8(tmp_path):
    file = tmp_path / "utf8.csv"
    file.write_bytes("col1\ncafé\n".encode("utf-8"))
    result = safe_read_csv(str(file))
    assert not result.is_empty()


def test_mixed_encoding_cp1252(tmp_path):
    file = tmp_path / "cp1252.csv"
    with open(file, "w", encoding="cp1252") as f:
        f.write("col1\ncafé\n")
    result = safe_read_csv(str(file))
    assert not result.is_empty()


def test_compare_both_empty():
    df1 = pl.DataFrame({"store": []}, schema={"store": pl.Utf8})
    df2 = pl.DataFrame({"store": []}, schema={"store": pl.Utf8})
    result = compare_files(df1, df2, "store", "store")
    assert result["missing_in_test"] == ""
    assert result["missing_in_prod"] == ""


def test_validation_from_df_empty():
    prod = pl.DataFrame({"STORE_NUMBER": pl.Series([], dtype=pl.Utf8), "Units": pl.Series([], dtype=pl.Float64), "Totalprice": pl.Series([], dtype=pl.Float64)})
    test = prod.clone()
    result = storelevelvalidation_from_df(prod, test)
    assert result.is_empty()


def test_validation_from_df_no_match():
    prod = pl.DataFrame({"STORE_NUMBER": ["A"], "Units": [10.0], "Totalprice": [100.0]})
    test = pl.DataFrame({"STORE_NUMBER": ["B"], "Units": [5.0], "Totalprice": [50.0]})
    result = storelevelvalidation_from_df(prod, test)
    assert not result.is_empty()
    assert "Units_Diff" in result.columns

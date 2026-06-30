import polars as pl
import os

from dav_tool.io import safe_read_csv


def test_safe_read_csv_utf8(tmp_path):
    file = tmp_path / "test.csv"
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    df.write_csv(file)
    result = safe_read_csv(str(file))
    assert not result.is_empty()
    assert list(result.columns) == ["a", "b"]


def test_safe_read_csv_cp1252(tmp_path):
    file = tmp_path / "test_cp1252.csv"
    with open(file, "w", encoding="cp1252") as f:
        f.write("col1\ncafé\n")
    result = safe_read_csv(str(file))
    assert not result.is_empty()
    assert "col1" in result.columns

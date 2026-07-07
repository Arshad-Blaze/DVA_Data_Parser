"""Tests for the configuration builder."""
import os

import polars as pl
import pytest

from dav_tool.config_builder import build_config, _infer_data_types


class TestBuildConfig:

    def test_build_config_delimited(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("Store,UPC,Description,Units,Price\nS001,100001,Widget,10,99.90\nS002,100002,Gadget,5,49.95\n")
        cfg = build_config([str(f)])
        assert cfg.file_type == "delimited"
        assert cfg.store_col == "Store"
        assert cfg.upc_col == "UPC"
        assert cfg.desc_col == "Description"
        assert cfg.units_col == "Units"
        assert cfg.price_col == "Price"
        assert cfg.detected_columns == ["Store", "UPC", "Description", "Units", "Price"]

    def test_build_config_with_source(self, tmp_path):
        f = tmp_path / "remote.csv"
        f.write_text("Store,UPC,Description,Units,Price\nS001,100001,Widget,10,99.90\n")
        from dav_tool.datasource.local import LocalDataSource
        source = LocalDataSource()
        source.connect()
        cfg = build_config([str(f)], source=source)
        assert cfg.file_type == "delimited"
        assert cfg.store_col == "Store"

    def test_build_config_no_files(self):
        cfg = build_config([])
        assert cfg.file_type is None

    def test_build_config_multiline_delimited(self, tmp_path):
        f = tmp_path / "multiline.txt"
        f.write_text("H|S001|2024-01-15\nD|S001|100001|Widget|10|99.90\n")
        cfg = build_config([str(f)], ml_record_types=["H", "D"], ml_delimiter="|")
        assert cfg.file_type == "multiline"

    def test_infer_data_types(self):
        df = pl.DataFrame({"a": ["1", "2"], "b": ["x", "y"]})
        types = _infer_data_types(df)
        assert "a" in types
        assert "b" in types

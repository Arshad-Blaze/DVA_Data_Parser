"""Tests for FormatConfig — load, save, and apply."""
import json
import os
import polars as pl
import pytest

from dav_tool.format_config import (
    FormatConfig,
    load_format_config,
    save_format_config,
    apply_format_config,
    config_from_ctx,
)
from dav_tool.processing_context import ProcessingContext


class TestFormatConfigRoundtrip:
    def test_save_and_load(self, tmp_path):
        cfg = FormatConfig(
            name="Test Retailer",
            file_type="delimited",
            delimiter="|",
            start_line=1,
            store_col="Store",
            upc_col="UPC",
            units_col="Qty",
            price_col="Sales",
            price_type="Total Price",
            implied_dollars=False,
            implied_units=True,
        )
        path = tmp_path / "config.json"
        save_format_config(cfg, str(path))

        assert path.exists()
        loaded = load_format_config(str(path))
        assert loaded.name == "Test Retailer"
        assert loaded.file_type == "delimited"
        assert loaded.delimiter == "|"
        assert loaded.start_line == 1
        assert loaded.store_col == "Store"
        assert loaded.upc_col == "UPC"
        assert loaded.implied_units is True
        assert loaded.implied_dollars is False

    def test_roundtrip_preserves_all_fields(self, tmp_path):
        cfg = FormatConfig(
            version=1,
            name="Full Config",
            file_type="multiline",
            delimiter=None,
            start_line=2,
            record_type="U",
            header_prefix="HDR",
            trailer_prefix="TRL",
            ml_record_types=["H", "D"],
            ml_delimiter=",",
            store_col="Store",
            upc_col="UPC",
        )
        path = tmp_path / "full.json"
        save_format_config(cfg, str(path))
        loaded = load_format_config(str(path))

        for key in ("file_type", "record_type", "header_prefix", "trailer_prefix",
                     "store_col", "upc_col", "ml_delimiter"):
            assert getattr(loaded, key) == getattr(cfg, key), f"Mismatch for {key}"
        assert loaded.ml_record_types == ["H", "D"]
        assert loaded.start_line == 2

    def test_load_partial_config(self, tmp_path):
        data = {"file_type": "fixed", "layout_file": "layouts/test.csv"}
        path = tmp_path / "partial.json"
        with open(path, "w") as f:
            json.dump(data, f)
        loaded = load_format_config(str(path))
        assert loaded.file_type == "fixed"
        assert loaded.layout_file == "layouts/test.csv"
        assert loaded.delimiter is None
        assert loaded.start_line == 0


class TestApplyFormatConfig:
    def test_apply_delimited(self):
        cfg = FormatConfig(
            file_type="delimited",
            delimiter=",",
            start_line=1,
            store_col="Store",
            upc_col="UPC",
        )
        ctx = ProcessingContext()
        apply_format_config(cfg, ctx, "/some/config/dir")
        assert ctx.file_type == "delimited"
        assert ctx.delimiter == ","
        assert ctx.start_line == 1
        assert ctx.store_col == "Store"
        assert ctx.upc_col == "UPC"
        assert ctx.ml_flattened is False

    def test_apply_multiline_delimited(self, tmp_path):
        hdr_path = tmp_path / "test_data.txt"
        hdr_path.write_text(
            "H|Store|Date\n"
            "D|S1|100|50\n"
            "D|S1|200|75\n"
        )
        cfg = FormatConfig(
            file_type="multiline",
            ml_record_types=["H", "D"],
            ml_delimiter="|",
            store_col="Store",
            upc_col="UPC",
        )
        ctx = ProcessingContext()
        ctx.file_paths = [str(hdr_path)]
        result = apply_format_config(cfg, ctx, str(tmp_path), [str(hdr_path)])
        assert ctx.file_type == "multiline"
        assert ctx.ml_flattened is True
        assert ctx.ml_record_types == ["H", "D"]
        assert ctx.ml_delimiter == "|"
        assert ctx.store_col == "Store"
        assert ctx.upc_col == "UPC"
        assert ctx.schema is not None
        assert len(ctx.schema) > 0

    def test_apply_multiline_hdr_with_layouts(self, tmp_path):
        data_file = tmp_path / "test_hdr.txt"
        data_file.write_text(
            "HDR01STR1      20250101\n"
            "DTL0101234567890ABCDEFGHIJ12345012345\n"
            "TRL0100002\n"
        )
        header_csv = tmp_path / "hdr_layout.csv"
        header_csv.write_text("field,from,length\nStore,6,4\nDate,16,8\n")
        detail_csv = tmp_path / "dtl_layout.csv"
        detail_csv.write_text("field,from,length\nUPC,6,10\nDesc,16,10\nUnits,26,5\nPrice,31,5\n")
        trailer_csv = tmp_path / "trl_layout.csv"
        trailer_csv.write_text("field,from,length\nRecordCount,6,5\n")

        cfg = FormatConfig(
            file_type="multiline",
            header_prefix="HDR",
            header_layout_file=str(header_csv),
            detail_layout_file=str(detail_csv),
            trailer_prefix="TRL",
            trailer_layout_file=str(trailer_csv),
            store_col="Store",
            upc_col="UPC",
        )
        ctx = ProcessingContext()
        apply_format_config(cfg, ctx, str(tmp_path), [str(data_file)])
        assert ctx.file_type == "multiline"
        assert ctx.header_prefix == "HDR"
        assert ctx.trailer_prefix == "TRL"
        assert ctx.ml_flattened is True
        assert ctx.header_layout is not None
        assert ctx.detail_layout is not None
        assert ctx.trailer_layout is not None
        assert ctx.schema is not None
        assert len(ctx.schema) > 0

    def test_apply_config_missing_layout_resolves_relative(self, tmp_path):
        data_file = tmp_path / "test_hdr.txt"
        data_file.write_text("HDR01STR1     20250101\nDTL0101234567890ABCDEFGHIJ1234501234\n")
        layout_dir = tmp_path / "layouts"
        layout_dir.mkdir()
        hdr_csv = layout_dir / "header.csv"
        hdr_csv.write_text("field,from,length\nStore,6,4\nDate,16,8\n")
        dtl_csv = layout_dir / "detail.csv"
        dtl_csv.write_text("field,from,length\nUPC,6,10\nDesc,16,10\nUnits,26,5\nPrice,31,5\n")

        cfg = FormatConfig(
            file_type="multiline",
            header_prefix="HDR",
            header_layout_file="layouts/header.csv",
            detail_layout_file="layouts/detail.csv",
        )
        ctx = ProcessingContext()
        apply_format_config(cfg, ctx, str(tmp_path), [str(data_file)])
        assert ctx.header_layout is not None
        assert ctx.detail_layout is not None

    def test_apply_config_missing_layout_file_does_not_crash(self, tmp_path):
        cfg = FormatConfig(
            file_type="multiline",
            header_prefix="HDR",
            header_layout_file="nonexistent.csv",
        )
        ctx = ProcessingContext()
        apply_format_config(cfg, ctx, str(tmp_path))
        assert ctx.header_prefix == "HDR"
        assert ctx.header_layout is None

    def test_apply_config_empty_file_paths_does_not_crash(self):
        cfg = FormatConfig(
            file_type="multiline",
            ml_record_types=["H", "D"],
            ml_delimiter="|",
        )
        ctx = ProcessingContext()
        result = apply_format_config(cfg, ctx, "/tmp", None)
        assert ctx.ml_flattened is True
        assert result is None


class TestConfigFromCtx:
    def test_basic_conversion(self):
        ctx = ProcessingContext()
        ctx.file_type = "delimited"
        ctx.delimiter = "\t"
        ctx.start_line = 2
        ctx.store_col = "StoreNumber"
        ctx.upc_col = "UPC12"
        ctx.desc_col = "Desc"
        ctx.units_col = "Qty"
        ctx.price_col = "Total"
        ctx.price_type = "Total Price"
        ctx.implied_dollars = True
        ctx.implied_units = False
        ctx.header_prefix = "HDR"

        cfg = config_from_ctx(ctx)
        assert cfg.file_type == "delimited"
        assert cfg.delimiter == "\t"
        assert cfg.start_line == 2
        assert cfg.store_col == "StoreNumber"
        assert cfg.upc_col == "UPC12"
        assert cfg.implied_dollars is True
        assert cfg.header_prefix == "HDR"

    def test_roundtrip_ctx_via_config(self, tmp_path):
        ctx = ProcessingContext()
        ctx.file_type = "multiline"
        ctx.ml_delimiter = ","
        ctx.ml_record_types = ["H", "D", "T"]
        ctx.detail_layout = [{"field": "UPC", "start": 0, "width": 10}]

        cfg = config_from_ctx(ctx)
        path = tmp_path / "rt.json"
        save_format_config(cfg, str(path))
        loaded = load_format_config(str(path))
        assert loaded.file_type == "multiline"
        assert loaded.ml_delimiter == ","
        assert loaded.ml_record_types == ["H", "D", "T"]

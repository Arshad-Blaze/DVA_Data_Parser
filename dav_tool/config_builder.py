"""Configuration Builder: inspect a SAMPLE, generate a FormatConfig.

Reads only the first N records of a file to detect its structure.
Never loads the full dataset.
"""
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from dav_tool._parsers import (
    preview_raw, preview_flattened_multiline, preview_flattened_multiline_fixed,
    load_layout, scan_delimited,
)
from dav_tool.config import DEFAULT_ENCODING, FALLBACK_ENCODING, DEFAULT_PREVIEW_ROWS, DELIMITERS
from dav_tool.detection import (
    is_multiline_record, detect_file_type, detect_record_types,
    detect_hdr_prefix, has_header,
)
from dav_tool.format_config import FormatConfig, ValidationConfig, ValidationRule
from dav_tool.ui.helpers import smart_column_indices

logger = logging.getLogger(__name__)

SAMPLE_SIZE = 100


def _infer_data_types(df: pl.DataFrame) -> Dict[str, str]:
    """Map column name -> inferred Polars data type string for a sample."""
    types = {}
    for col in df.columns:
        dtype = df[col].dtype
        types[col] = str(dtype)
    return types


def _detect_encoding(file_path: str) -> str:
    """Quick encoding detection by trying common encodings."""
    for enc in ["cp1252", "utf-8", "utf8-lossy", "latin-1"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf8-lossy"


def build_config(
    file_paths: List[str],
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    ml_record_types: Optional[List[str]] = None,
    ml_delimiter: str = "|",
) -> FormatConfig:
    """Build a FormatConfig by inspecting a sample of the data.

    Only ever reads *SAMPLE_SIZE* rows. Returns a configuration with
    detected metadata, schema, suggested column mapping, and default
    validation settings.
    """
    fp = file_paths[0] if file_paths else ""

    encoding = _detect_encoding(fp) if fp else DEFAULT_ENCODING

    if not file_type:
        if is_multiline_record(fp):
            file_type = "multiline"
        else:
            file_type, delimiter = detect_file_type(fp)

    cfg = FormatConfig(
        version=2,
        file_type=file_type,
        encoding=encoding,
    )

    if file_type == "multiline":
        if not header_prefix:
            hdr_prefixes = detect_hdr_prefix(fp) if fp else []
            header_prefix = hdr_prefixes[0] if hdr_prefixes else None

        if header_prefix:
            cfg.header_prefix = header_prefix
        else:
            if not ml_record_types:
                ml_record_types = detect_record_types(fp) if fp else ["H", "D"]
            cfg.ml_record_types = ml_record_types
            cfg.ml_delimiter = ml_delimiter

        cfg.has_header = False
        cfg.delimiter = ml_delimiter

        if header_prefix and header_layout and detail_layout:
            sample = preview_flattened_multiline_fixed(
                file_paths, header_prefix, header_layout, detail_layout,
                n_rows=SAMPLE_SIZE,
                trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
            )
        else:
            rtypes = ml_record_types or ["H", "D"]
            sample = preview_flattened_multiline(
                file_paths, rtypes, ml_delimiter, n_rows=SAMPLE_SIZE,
            )
    else:
        cfg.has_header = has_header(fp, delimiter or ",") if fp else True

        if file_type == "fixed" and layout:
            sample = preview_raw(
                file_paths, file_type, delimiter or ",", layout,
                n_rows=SAMPLE_SIZE,
            )
        elif file_type == "delimited":
            try:
                sample = pl.read_csv(
                    fp, separator=delimiter or ",",
                    n_rows=SAMPLE_SIZE, encoding=FALLBACK_ENCODING,
                )
            except Exception:
                sample = preview_raw(
                    file_paths, file_type, delimiter or ",",
                    n_rows=SAMPLE_SIZE,
                )
        else:
            sample = preview_raw(
                file_paths, file_type, delimiter or ",",
                n_rows=SAMPLE_SIZE,
            )

    if sample is not None and not sample.is_empty():
        cfg.detected_columns = list(sample.columns)
        cfg.detected_data_types = _infer_data_types(sample)

        indices = smart_column_indices(sample.columns)
        mapping = {}
        for role, (idx, col) in indices.items():
            if col:
                mapping[role] = col
        cfg.suggested_mapping = mapping

        cfg.store_col = mapping.get("store")
        cfg.upc_col = mapping.get("upc")
        cfg.desc_col = mapping.get("description")
        cfg.units_col = mapping.get("units")
        cfg.price_col = mapping.get("price")

        cfg.schema = list(sample.columns)

    return cfg


def config_to_summary_dict(cfg: FormatConfig) -> Dict[str, Any]:
    """Convert a FormatConfig to a human-readable summary dict for UI display."""
    sections = {
        "File Information": {
            "Name": cfg.name or "—",
            "Type": cfg.file_type or "—",
            "Encoding": cfg.encoding,
            "Has Header": "Yes" if cfg.has_header else "No",
        },
        "Delimiter / Layout": {
            "Delimiter": cfg.delimiter or "—",
            "Start Line": cfg.start_line,
            "Record Type": cfg.record_type or "—",
        },
    }

    if cfg.file_type == "multiline":
        ml_info = {
            "Multiline": "Yes",
            "Delimiter": cfg.ml_delimiter,
        }
        if cfg.header_prefix:
            ml_info["Header Prefix"] = cfg.header_prefix
        else:
            ml_info["Record Types"] = ", ".join(cfg.ml_record_types or [])
        sections["Multiline Settings"] = ml_info

    schema_info = {}
    if cfg.detected_columns:
        schema_info["Columns"] = ", ".join(cfg.detected_columns)
    if cfg.detected_data_types:
        type_strs = [f"{k}: {v}" for k, v in cfg.detected_data_types.items()]
        schema_info["Data Types"] = "; ".join(type_strs)
    if schema_info:
        sections["Schema"] = schema_info

    sections["Column Mapping"] = {
        "Store": cfg.store_col or "—",
        "UPC": cfg.upc_col or "—",
        "Description": cfg.desc_col or "—",
        "Units": cfg.units_col or "—",
        "Price": cfg.price_col or "—",
        "Price Type": cfg.price_type,
        "Implied Dollars": "Yes" if cfg.implied_dollars else "No",
        "Implied Units": "Yes" if cfg.implied_units else "No",
    }

    return sections

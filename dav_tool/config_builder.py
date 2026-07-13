"""Configuration Builder: inspect a SAMPLE, generate a FormatConfig.

Reads only the first N records of a file to detect its structure.
Never loads the full dataset.

Supports progressive building via stage-specific builders.
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
from dav_tool.format_config import (
    FormatConfig, ValidationConfig, ValidationRule, ConfigSection,
)
from dav_tool.datasource.base import IDataSource
from dav_tool.datasource.manager import get_active_source
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)

SAMPLE_SIZE = 100


def _infer_data_types(df: pl.DataFrame) -> Dict[str, str]:
    """Map column name -> inferred Polars data type string for a sample."""
    types = {}
    for col in df.columns:
        dtype = df[col].dtype
        types[col] = str(dtype)
    return types


def _detect_encoding(
    file_path: str,
    source: Optional[IDataSource] = None,
) -> str:
    """Quick encoding detection by trying common encodings."""
    sample = None
    if source is not None:
        try:
            sample = source.read_sample(file_path, n=5)
        except Exception:
            pass
    if sample is not None:
        for enc in ["cp1252", "utf-8", "utf8-lossy", "latin-1"]:
            try:
                sample.encode(enc)
                return enc
            except (UnicodeEncodeError, UnicodeError):
                continue
        return "utf8-lossy"
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
    source: Optional[IDataSource] = None,
    discovery: Optional[DiscoveryResult] = None,
) -> FormatConfig:
    """Build a FormatConfig by inspecting a sample of the data.

    Only ever reads *SAMPLE_SIZE* rows. Returns a configuration with
    detected metadata, schema, suggested column mapping, and default
    validation settings.

    If *discovery* is provided, reuses its detected file_type, delimiter,
    and structure — no re-detection is performed for those fields.
    """
    fp = file_paths[0] if file_paths else ""

    if not fp:
        return FormatConfig()

    if source is None:
        source = get_active_source()

    # Use discovery results when available — skip re-detection
    if discovery is not None:
        if not file_type:
            file_type = discovery.file_type
        if not delimiter:
            delimiter = discovery.delimiter
        if not header_prefix:
            header_prefix = discovery.header_prefix
        if not ml_record_types:
            ml_record_types = discovery.ml_record_types
        if not header_layout:
            header_layout = discovery.header_layout
        if not detail_layout:
            detail_layout = discovery.detail_layout
        if not trailer_prefix:
            trailer_prefix = discovery.trailer_prefix
        if not trailer_layout:
            trailer_layout = discovery.trailer_layout

    if source is not None:
        sample_text = source.read_sample(fp, n=SAMPLE_SIZE) if fp else ""
        import tempfile
        _tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sample", mode="w")
        _tmp.write(sample_text)
        _tmp.close()
        _sample_path = _tmp.name
        fp_local = _sample_path
        file_paths_local = [_sample_path]
    else:
        fp_local = fp
        file_paths_local = file_paths

    encoding = _detect_encoding(fp_local) if fp_local else DEFAULT_ENCODING

    try:
        if not file_type:
            if is_multiline_record(fp_local):
                file_type = "multiline"
            else:
                file_type, delimiter = detect_file_type(fp_local)

        cfg = FormatConfig(
            version=2,
            file_type=file_type,
            encoding=encoding,
        )

        if file_type == "multiline":
            if not header_prefix:
                hdr_prefixes = detect_hdr_prefix(fp_local) if fp_local else []
                header_prefix = hdr_prefixes[0] if hdr_prefixes else None

            if header_prefix:
                cfg.header_prefix = header_prefix
            else:
                if not ml_record_types:
                    ml_record_types = detect_record_types(fp_local) if fp_local else ["H", "D"]
                cfg.ml_record_types = ml_record_types
                cfg.ml_delimiter = ml_delimiter

            cfg.has_header = False
            cfg.delimiter = ml_delimiter

            if header_prefix and header_layout and detail_layout:
                sample = preview_flattened_multiline_fixed(
                    file_paths_local, header_prefix, header_layout, detail_layout,
                    n_rows=SAMPLE_SIZE,
                    trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
                )
            else:
                rtypes = ml_record_types or ["H", "D"]
                sample = preview_flattened_multiline(
                    file_paths_local, rtypes, ml_delimiter, n_rows=SAMPLE_SIZE,
                )
        else:
            if file_type == "delimited":
                cfg.delimiter = delimiter
            cfg.has_header = has_header(fp_local, delimiter or ",") if fp_local else True

            if file_type == "fixed" and layout:
                sample = preview_raw(
                    file_paths_local, file_type, delimiter or ",", layout,
                    n_rows=SAMPLE_SIZE,
                )
            elif file_type == "delimited":
                try:
                    sample = pl.read_csv(
                        fp_local, separator=delimiter or ",",
                        n_rows=SAMPLE_SIZE, encoding=FALLBACK_ENCODING,
                    )
                except Exception:
                    sample = preview_raw(
                        file_paths_local, file_type, delimiter or ",",
                        n_rows=SAMPLE_SIZE,
                    )
            else:
                sample = preview_raw(
                    file_paths_local, file_type, delimiter or ",",
                    n_rows=SAMPLE_SIZE,
                )

        if sample is not None and not sample.is_empty():
            cols = list(sample.columns)
            cfg.physical_schema = cols
            cfg.canonical_schema = list(cols)
            cfg.detected_data_types = _infer_data_types(sample)

            from dav_tool._column_utils import smart_column_indices
            indices = smart_column_indices(cols)
            mapping = {}
            for role, (idx, col) in indices.items():
                if col:
                    mapping[role] = col
            cfg.suggested_mapping = mapping

            cfg.store_col = mapping.get("store")
            cfg.upc_col = mapping.get("upc")
            cfg.desc_col = mapping.get("description")
            cfg.quantity_col = mapping.get("units")
            cfg.price_col = mapping.get("price")
    finally:
        if source is not None and fp_local != fp:
            try:
                os.unlink(fp_local)
            except Exception:
                pass

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
    if cfg.physical_schema:
        schema_info["Physical Columns"] = ", ".join(cfg.physical_schema)
    if cfg.detected_data_types:
        type_strs = [f"{k}: {v}" for k, v in cfg.detected_data_types.items()]
        schema_info["Data Types"] = "; ".join(type_strs)
    if schema_info:
        sections["Physical Schema"] = schema_info

    if cfg.canonical_schema:
        sections["Canonical Schema"] = {
            "Columns": ", ".join(cfg.canonical_schema),
        }

    sections["Business Mapping"] = {
        "Store": cfg.store_col or "—",
        "UPC": cfg.upc_col or "—",
        "Description": cfg.desc_col or "—",
        "Quantity": cfg.quantity_col or "—",
        "Price": cfg.price_col or "—",
        "Price Type": cfg.price_type,
        "Implied Dollars": "Yes" if cfg.implied_dollars else "No",
        "Implied Units": "Yes" if cfg.implied_units else "No",
    }

    sections["Quantity Configuration"] = {
        "Quantity Type": cfg.quantity_type,
        "Weight Column": cfg.weight_col or "—",
        "Weight UOM": cfg.weight_uom,
        "Resolution Rule": cfg.resolution_rule,
    }

    return sections


# ── Progressive Stage Builders ──────────────────────────────────────


def build_file_info_section(
    cfg: FormatConfig,
    file_paths: List[str],
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    source: Optional[IDataSource] = None,
) -> FormatConfig:
    """Stage A: detect and set file type, encoding, delimiter."""
    fp = file_paths[0] if file_paths else ""
    if not fp:
        return cfg

    if source is None:
        source = get_active_source()

    local_fp = _resolve_sample(fp, source)

    if not file_type:
        if is_multiline_record(local_fp):
            file_type = "multiline"
        else:
            file_type, delimiter = detect_file_type(local_fp)

    cfg.file_type = file_type
    cfg.delimiter = delimiter
    cfg.encoding = _detect_encoding(local_fp, source)
    cfg.has_header = has_header(local_fp, delimiter or ",") if file_type != "multiline" else False

    _cleanup_sample(fp, local_fp, source)
    return cfg


def build_record_info_section(
    cfg: FormatConfig,
    file_paths: List[str],
    source: Optional[IDataSource] = None,
) -> FormatConfig:
    """Stage B: detect record structure (multiline, HDR, layout)."""
    fp = file_paths[0] if file_paths else ""
    if not fp or cfg.file_type != "multiline":
        return cfg

    if source is None:
        source = get_active_source()

    local_fp = _resolve_sample(fp, source)

    hdr_prefixes = detect_hdr_prefix(local_fp) if local_fp else []
    if hdr_prefixes:
        cfg.header_prefix = hdr_prefixes[0]
    else:
        types = detect_record_types(local_fp) if local_fp else ["H", "D"]
        cfg.ml_record_types = types
        cfg.ml_delimiter = cfg.delimiter or "|"

    _cleanup_sample(fp, local_fp, source)
    return cfg


def build_schema_section(
    cfg: FormatConfig,
    file_paths: List[str],
    layout: Optional[List[Dict]] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> FormatConfig:
    """Stage C: detect schema, columns, and data types from a sample."""
    fp = file_paths[0] if file_paths else ""
    if not fp:
        return cfg

    if source is None:
        source = get_active_source()

    local_fp = _resolve_sample(fp, source)
    file_paths_local = [local_fp]

    sample = _load_sample(
        file_paths_local, cfg.file_type, cfg.delimiter or ",",
        layout, cfg.start_line, cfg.record_type,
        cfg.header_prefix, header_layout, detail_layout,
        cfg.ml_record_types, cfg.ml_delimiter,
        trailer_prefix, trailer_layout,
    )

    if sample is not None and not sample.is_empty():
        cols = list(sample.columns)
        cfg.physical_schema = cols
        cfg.canonical_schema = list(cols)
        cfg.detected_data_types = _infer_data_types(sample)

        from dav_tool._column_utils import smart_column_indices
        indices = smart_column_indices(cols)
        mapping = {}
        for role, (idx, col) in indices.items():
            if col:
                mapping[role] = col
        cfg.suggested_mapping = mapping
        cfg.store_col = mapping.get("store")
        cfg.upc_col = mapping.get("upc")
        cfg.desc_col = mapping.get("description")
        cfg.quantity_col = mapping.get("units")
        cfg.price_col = mapping.get("price")

    _cleanup_sample(fp, local_fp, source)
    return cfg


def build_business_rules_section(
    cfg: FormatConfig,
    store_col: Optional[str] = None,
    upc_col: Optional[str] = None,
    desc_col: Optional[str] = None,
    quantity_col: Optional[str] = None,
    price_col: Optional[str] = None,
    price_type: str = "Total Price",
    implied_dollars: bool = False,
    implied_units: bool = False,
) -> FormatConfig:
    """Stage D: set business rules (column mapping, price settings)."""
    if store_col:
        cfg.store_col = store_col
    if upc_col:
        cfg.upc_col = upc_col
    if desc_col:
        cfg.desc_col = desc_col
    if quantity_col:
        cfg.quantity_col = quantity_col
    if price_col:
        cfg.price_col = price_col
    cfg.price_type = price_type
    cfg.implied_dollars = implied_dollars
    cfg.implied_units = implied_units
    return cfg


# ── Internal Helpers ────────────────────────────────────────────────


def _resolve_sample(fp: str, source: Optional[IDataSource]) -> str:
    """Download a small sample to local temp for detection."""
    if source is not None:
        try:
            text = source.read_sample(fp, n=SAMPLE_SIZE)
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sample", mode="w")
            tmp.write(text)
            tmp.close()
            return tmp.name
        except Exception as e:
            logger.warning("Failed to download sample from source for %s: %s", fp, e)
    return fp


def _cleanup_sample(original_fp: str, local_fp: str, source: Optional[IDataSource]):
    """Remove temporary sample file if one was created."""
    if source is not None and local_fp != original_fp:
        try:
            os.unlink(local_fp)
        except Exception as e:
            logger.warning("Failed to cleanup sample file %s: %s", local_fp, e)


def _load_sample(
    file_paths: List[str],
    file_type: str,
    delimiter: str,
    layout: Optional[List[Dict]],
    start_line: int,
    record_type: Optional[str],
    header_prefix: Optional[str],
    header_layout: Optional[List[Dict]],
    detail_layout: Optional[List[Dict]],
    ml_record_types: Optional[List[str]],
    ml_delimiter: str,
    trailer_prefix: Optional[str],
    trailer_layout: Optional[List[Dict]],
) -> Optional[pl.DataFrame]:
    """Load a small sample for schema detection."""
    fp = file_paths[0] if file_paths else ""
    if not fp:
        return None

    if file_type == "multiline":
        if header_prefix and header_layout and detail_layout:
            return preview_flattened_multiline_fixed(
                file_paths, header_prefix, header_layout, detail_layout,
                n_rows=SAMPLE_SIZE,
                trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
            )
        rtypes = ml_record_types or ["H", "D"]
        return preview_flattened_multiline(
            file_paths, rtypes, ml_delimiter, n_rows=SAMPLE_SIZE,
        )

    if file_type == "fixed" and layout:
        return preview_raw(
            file_paths, file_type, delimiter, layout,
            n_rows=SAMPLE_SIZE,
        )

    if file_type == "delimited":
        try:
            from dav_tool.config import FALLBACK_ENCODING
            return pl.read_csv(
                fp, separator=delimiter,
                n_rows=SAMPLE_SIZE, encoding=FALLBACK_ENCODING,
            )
        except Exception:
            pass

    return preview_raw(
        file_paths, file_type, delimiter,
        n_rows=SAMPLE_SIZE,
    )

import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import polars as pl

from dav_tool._parsers import load_layout, preview_flattened_multiline, preview_flattened_multiline_fixed
from dav_tool.processing_context import ProcessingContext


@dataclass
class FormatConfig:
    """Serializable description of a data file format.

    Can be saved to / loaded from JSON to bypass manual UI setup.
    """
    version: int = 1
    name: str = ""
    file_type: Optional[str] = None
    delimiter: Optional[str] = None
    start_line: int = 0
    record_type: Optional[str] = None
    layout_file: Optional[str] = None
    header_prefix: Optional[str] = None
    header_layout_file: Optional[str] = None
    detail_layout_file: Optional[str] = None
    trailer_prefix: Optional[str] = None
    trailer_layout_file: Optional[str] = None
    ml_record_types: Optional[List[str]] = None
    ml_delimiter: str = "|"
    store_col: Optional[str] = None
    upc_col: Optional[str] = None
    desc_col: Optional[str] = None
    units_col: Optional[str] = None
    price_col: Optional[str] = None
    price_type: str = "Total Price"
    implied_dollars: bool = False
    implied_units: bool = False


def load_format_config(path: str) -> FormatConfig:
    """Load a FormatConfig from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    version = data.pop("version", 1)
    name = data.pop("name", "")
    return FormatConfig(version=version, name=name, **data)


def save_format_config(config: FormatConfig, path: str):
    """Save a FormatConfig to a JSON file."""
    d = asdict(config)
    with open(path, "w") as f:
        json.dump(d, f, indent=2, default=str)


def apply_format_config(
    config: FormatConfig,
    ctx: ProcessingContext,
    config_dir: str,
    file_paths: Optional[List[str]] = None,
):
    """Apply parsing settings from a FormatConfig to a ProcessingContext.

    Sets all fields, loads referenced layout CSVs (resolved relative to
    *config_dir*), flattens multiline data, and auto-applies schema.

    Returns the flattened preview DataFrame (or None if not applicable).
    """
    config_dir = config_dir or "."

    def _resolve(p: Optional[str]) -> Optional[str]:
        if not p:
            return None
        if os.path.isabs(p):
            return p
        return os.path.normpath(os.path.join(config_dir, p))

    ctx.file_type = config.file_type
    ctx.delimiter = config.delimiter
    ctx.start_line = config.start_line
    ctx.record_type = config.record_type
    ctx.header_prefix = config.header_prefix
    ctx.trailer_prefix = config.trailer_prefix
    ctx.ml_record_types = config.ml_record_types
    ctx.ml_delimiter = config.ml_delimiter
    ctx.store_col = config.store_col
    ctx.upc_col = config.upc_col
    ctx.desc_col = config.desc_col
    ctx.units_col = config.units_col
    ctx.price_col = config.price_col
    ctx.price_type = config.price_type
    ctx.implied_dollars = config.implied_dollars
    ctx.implied_units = config.implied_units

    resolved_layout_file = _resolve(config.layout_file)
    if resolved_layout_file and os.path.exists(resolved_layout_file):
        ctx.layout = load_layout(resolved_layout_file)

    resolved_header = _resolve(config.header_layout_file)
    if resolved_header and os.path.exists(resolved_header):
        ctx.header_layout = load_layout(resolved_header)

    resolved_detail = _resolve(config.detail_layout_file)
    if resolved_detail and os.path.exists(resolved_detail):
        ctx.detail_layout = load_layout(resolved_detail)

    resolved_trailer = _resolve(config.trailer_layout_file)
    if resolved_trailer and os.path.exists(resolved_trailer):
        ctx.trailer_layout = load_layout(resolved_trailer)

    config_has_mapping = bool(config.store_col or config.upc_col or config.units_col or config.price_col)
    if ctx.file_type != "multiline":
        ctx.ml_flattened = False
        return None
    ctx.ml_flattened = True

    file_paths = file_paths or ctx.file_paths
    if not file_paths:
        return None

    if ctx.header_prefix and ctx.header_layout and ctx.detail_layout:
        flat = preview_flattened_multiline_fixed(
            file_paths,
            ctx.header_prefix,
            ctx.header_layout,
            ctx.detail_layout,
            n_rows=10,
            trailer_prefix=ctx.trailer_prefix,
            trailer_layout=ctx.trailer_layout,
        )
    elif ctx.ml_record_types:
        flat = preview_flattened_multiline(
            file_paths, ctx.ml_record_types, ctx.ml_delimiter, n_rows=10,
        )
    else:
        return None

    if flat is not None and not flat.is_empty():
        ctx.schema = list(flat.columns)
        if config_has_mapping:
            ctx.columns = list(flat.columns)
        return flat

    return None


def config_from_ctx(ctx: ProcessingContext) -> FormatConfig:
    """Build a FormatConfig from a configured ProcessingContext.

    Used for saving the current configuration.
    """
    return FormatConfig(
        name="",
        file_type=ctx.file_type,
        delimiter=ctx.delimiter,
        start_line=ctx.start_line,
        record_type=ctx.record_type,
        header_prefix=ctx.header_prefix,
        trailer_prefix=ctx.trailer_prefix,
        ml_record_types=ctx.ml_record_types,
        ml_delimiter=ctx.ml_delimiter,
        store_col=ctx.store_col,
        upc_col=ctx.upc_col,
        desc_col=ctx.desc_col,
        units_col=ctx.units_col,
        price_col=ctx.price_col,
        price_type=ctx.price_type,
        implied_dollars=ctx.implied_dollars,
        implied_units=ctx.implied_units,
    )

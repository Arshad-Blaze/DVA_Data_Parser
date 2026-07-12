"""Discovery Service — file detection, type detection, schema detection.

Moved from UI layer to be testable and reusable.
No Streamlit imports. No rendering. Pure logic.
"""
import logging
import os
from typing import List, Dict, Optional, Tuple

import polars as pl

from dav_tool.detection import (
    is_multiline_record, detect_file_type, detect_record_types,
    detect_hdr_prefix, has_header,
)
from dav_tool._parsers import (
    preview_raw, preview_flattened_multiline, preview_flattened_multiline_fixed,
    load_layout,
)
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)


class DiscoveryResult:
    """Result of file discovery — the single source of truth for detection metadata.

    Produced once during the Connection → Discovery phase and consumed
    by all downstream phases (Configuration, Config Validation, Processing).
    Downstream phases MUST NOT re-detect file type, delimiter, columns, or
    structure that this result already provides.
    """

    def __init__(
        self,
        file_paths: Optional[List[str]] = None,
        file_type: Optional[str] = None,
        delimiter: Optional[str] = None,
        columns: Optional[List[str]] = None,
        schema: Optional[List[str]] = None,
        header_prefix: Optional[str] = None,
        header_layout: Optional[List[Dict]] = None,
        detail_layout: Optional[List[Dict]] = None,
        trailer_prefix: Optional[str] = None,
        trailer_layout: Optional[List[Dict]] = None,
        ml_record_types: Optional[List[str]] = None,
        ml_delimiter: str = "|",
        ml_flattened: bool = False,
        start_line: int = 0,
        record_type: Optional[str] = None,
        layout: Optional[List[Dict]] = None,
        error: Optional[str] = None,
    ):
        self.file_paths = file_paths
        self.file_type = file_type
        self.delimiter = delimiter
        self.columns = columns
        self.schema = schema
        self.header_prefix = header_prefix
        self.header_layout = header_layout
        self.detail_layout = detail_layout
        self.trailer_prefix = trailer_prefix
        self.trailer_layout = trailer_layout
        self.ml_record_types = ml_record_types
        self.ml_delimiter = ml_delimiter
        self.ml_flattened = ml_flattened
        self.start_line = start_line
        self.record_type = record_type
        self.layout = layout
        self.error = error

    @property
    def is_ready(self) -> bool:
        """True if discovery produced a valid file type and columns."""
        return bool(self.file_type and self.columns)

    @property
    def needs_flattening(self) -> bool:
        """True if the file structure requires flattening before column extraction.

        Only multiline (delimited multiline or HDR fixed-width) files need
        flattening. Standard delimited and simple fixed-width files do NOT.
        """
        return self.file_type == "multiline" and not self.ml_flattened

    @classmethod
    def from_context(cls, ctx) -> "DiscoveryResult":
        """Build a DiscoveryResult from an existing ProcessingContext.

        Used when consuming detection results already stored in context.
        """
        return cls(
            file_paths=getattr(ctx, "file_paths", None),
            file_type=getattr(ctx, "file_type", None),
            delimiter=getattr(ctx, "delimiter", None),
            columns=getattr(ctx, "columns", None),
            schema=getattr(ctx, "schema", None),
            header_prefix=getattr(ctx, "header_prefix", None),
            header_layout=getattr(ctx, "header_layout", None),
            detail_layout=getattr(ctx, "detail_layout", None),
            trailer_prefix=getattr(ctx, "trailer_prefix", None),
            trailer_layout=getattr(ctx, "trailer_layout", None),
            ml_record_types=getattr(ctx, "ml_record_types", None),
            ml_delimiter=getattr(ctx, "ml_delimiter", "|"),
            ml_flattened=getattr(ctx, "ml_flattened", False),
            start_line=getattr(ctx, "start_line", 0),
            record_type=getattr(ctx, "record_type", None),
            layout=getattr(ctx, "layout", None),
        )

    def apply_to_context(self, ctx) -> None:
        """Apply discovery results to a ProcessingContext.

        Populates all detection-derived fields so downstream phases
        never need to re-detect.
        """
        ctx.file_paths = self.file_paths
        ctx.file_type = self.file_type
        ctx.delimiter = self.delimiter
        ctx.columns = self.columns
        ctx.schema = self.schema or self.columns
        ctx.header_prefix = self.header_prefix
        ctx.header_layout = self.header_layout
        ctx.detail_layout = self.detail_layout
        ctx.trailer_prefix = self.trailer_prefix
        ctx.trailer_layout = self.trailer_layout
        ctx.ml_record_types = self.ml_record_types
        ctx.ml_delimiter = self.ml_delimiter
        ctx.ml_flattened = self.ml_flattened
        ctx.start_line = self.start_line
        ctx.record_type = self.record_type
        ctx.layout = self.layout


def detect_file(
    file_paths: List[str],
    source: Optional[IDataSource] = None,
) -> DiscoveryResult:
    """Detect file type and structure from the first file.

    Returns a DiscoveryResult with detected metadata.
    This is the SINGLE detection entry point. Downstream phases
    must consume this result instead of re-detecting.
    No UI rendering. Pure detection logic.
    """
    if not file_paths:
        return DiscoveryResult(error="No files provided")

    fp = file_paths[0]

    try:
        if is_multiline_record(fp, source=source):
            result = _detect_multiline(file_paths, source=source)
        else:
            result = _detect_simple(file_paths, source=source)
    except Exception as e:
        logger.error("Detection failed: %s", str(e), exc_info=True)
        return DiscoveryResult(file_paths=file_paths, error=str(e))

    result.file_paths = file_paths
    return result


def _detect_simple(
    file_paths: List[str],
    source: Optional[IDataSource] = None,
) -> DiscoveryResult:
    """Detect delimited or fixed-width files."""
    fp = file_paths[0]
    file_type, delimiter = detect_file_type(fp, source=source)

    if file_type == "delimited":
        columns = _get_delimited_columns(file_paths, delimiter, source=source)
        return DiscoveryResult(
            file_type="delimited",
            delimiter=delimiter,
            columns=columns,
        )
    elif file_type == "fixed":
        return DiscoveryResult(
            file_type="fixed",
            error="Fixed-width files require a layout CSV",
        )
    else:
        return DiscoveryResult(error=f"Unrecognized file type: {file_type}")


def _detect_multiline(
    file_paths: List[str],
    source: Optional[IDataSource] = None,
) -> DiscoveryResult:
    """Detect multiline (HDR delimited or HDR fixed-width) files."""
    fp = file_paths[0]
    hdr_prefixes = detect_hdr_prefix(fp, source=source)

    if hdr_prefixes:
        return DiscoveryResult(
            file_type="multiline",
            header_prefix=hdr_prefixes[0],
        )
    else:
        detected_types = detect_record_types(fp, source=source)
        return DiscoveryResult(
            file_type="multiline",
            ml_record_types=detected_types or ["H", "D"],
            ml_delimiter="|",
        )


def flatten_multiline(
    file_paths: List[str],
    discovery: DiscoveryResult,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> DiscoveryResult:
    """Flatten multiline data and return updated discovery with schema.

    For HDR fixed-width: requires header_layout + detail_layout.
    For delimited multiline: requires ml_record_types + ml_delimiter.
    """
    if discovery.header_prefix and header_layout and detail_layout:
        flat = preview_flattened_multiline_fixed(
            file_paths,
            discovery.header_prefix,
            header_layout,
            detail_layout,
            n_rows=10,
            trailer_prefix=discovery.trailer_prefix,
            trailer_layout=trailer_layout,
            source=source,
        )
    elif discovery.ml_record_types:
        flat = preview_flattened_multiline(
            file_paths,
            discovery.ml_record_types,
            discovery.ml_delimiter,
            n_rows=10,
            source=source,
        )
    else:
        return DiscoveryResult(error="Cannot flatten: no record types or HDR prefix")

    if flat is not None and not flat.is_empty():
        schema = list(flat.columns)
        return DiscoveryResult(
            file_type=discovery.file_type,
            delimiter=discovery.delimiter,
            columns=schema,
            schema=schema,
            header_prefix=discovery.header_prefix,
            header_layout=header_layout,
            detail_layout=detail_layout,
            trailer_prefix=discovery.trailer_prefix,
            trailer_layout=trailer_layout,
            ml_record_types=discovery.ml_record_types,
            ml_delimiter=discovery.ml_delimiter,
            ml_flattened=True,
        )

    return DiscoveryResult(error="Flattening produced empty result")


def get_preview(
    file_paths: List[str],
    file_type: str,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    n_rows: int = 10,
    start_line: int = 0,
    record_type: Optional[str] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> Optional[pl.DataFrame]:
    """Get a preview DataFrame for display. Pure logic, no UI."""
    try:
        if file_type == "multiline":
            if header_prefix and header_layout and detail_layout:
                return preview_flattened_multiline_fixed(
                    file_paths, header_prefix, header_layout, detail_layout,
                    n_rows=n_rows,
                    trailer_prefix=trailer_prefix,
                    trailer_layout=trailer_layout,
                    source=source,
                )
            elif header_prefix is None:
                ml_rt = record_type.split(",") if record_type else ["H", "D"]
                return preview_flattened_multiline(
                    file_paths, ml_rt, delimiter or "|",
                    n_rows=n_rows, source=source,
                )
        else:
            return preview_raw(
                file_paths, file_type, delimiter or ",", layout,
                n_rows=n_rows, start_line=start_line,
                record_type=record_type, source=source,
            )
    except Exception as e:
        logger.warning("Preview failed: %s", e)
    return None


def get_column_names_from_file(
    file_paths: List[str],
    file_type: str,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    start_line: int = 0,
    record_type: Optional[str] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
) -> List[str]:
    """Extract column names from file without full parsing."""
    from dav_tool._parsers import parse_fixed_width_chunks

    if not file_paths:
        return []

    try:
        if file_type == "delimited":
            from dav_tool.io import safe_read_csv
            df = safe_read_csv(file_paths[0], separator=delimiter or ",", n_rows=5, source=source)
            return df.columns
        elif file_type == "fixed" and layout:
            chunks = list(parse_fixed_width_chunks(
                file_paths[:1], layout, start_line, record_type,
                chunk_size=5, source=source,
            ))
            if chunks:
                return chunks[0].columns
        elif file_type == "multiline":
            if header_prefix and header_layout:
                flat = preview_flattened_multiline_fixed(
                    file_paths, header_prefix, header_layout, layout or [],
                    n_rows=5,
                    trailer_prefix=trailer_prefix,
                    trailer_layout=trailer_layout,
                    source=source,
                )
            else:
                rt_list = record_type.split(",") if record_type else ["H", "D"]
                flat = preview_flattened_multiline(
                    file_paths, rt_list, delimiter or "|",
                    n_rows=5, source=source,
                )
            if flat is not None and not flat.is_empty():
                return flat.columns
    except Exception as e:
        logger.warning("Could not determine column names: %s", e)

    return []


def _get_delimited_columns(
    file_paths: List[str],
    delimiter: Optional[str] = None,
    source: Optional[IDataSource] = None,
) -> List[str]:
    """Get column names from a delimited file."""
    from dav_tool.io import safe_read_csv
    try:
        df = safe_read_csv(file_paths[0], separator=delimiter or ",", n_rows=5, source=source)
        return df.columns
    except Exception as e:
        logger.warning("Could not read delimited columns: %s", e)
        return []

"""Discovery Service — file detection, type detection, schema detection.

Moved from UI layer to be testable and reusable.
No Streamlit imports. No rendering. Pure logic.
"""
import logging
from typing import List, Dict, Optional

from dav_tool.detection import (
    is_multiline_record, detect_file_type, detect_record_types,
    detect_hdr_prefix,
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

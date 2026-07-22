"""Discovery Service — file detection, type detection, schema detection.

Moved from UI layer to be testable and reusable.
No Streamlit imports. No rendering. Pure logic.
"""
import logging
from typing import List, Dict, Optional

from dav_tool.detection import (
    is_multiline_record, detect_file_type, detect_record_types,
    detect_hdr_prefix, detect_trailer_prefix, detect_candidate_columns,
    generate_detection_summary,
)
from dav_tool.datasource.base import IDataSource
from dav_tool.io import safe_read_csv

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
        record_length: Optional[int] = None,
        candidate_layout: Optional[List[Dict]] = None,
        disclaimer_lines: Optional[List[int]] = None,
        record_prefix: Optional[List[str]] = None,
        candidate_keys: Optional[List[Dict]] = None,
        suggested_joins: Optional[List[Dict]] = None,
        error: Optional[str] = None,
        confidence: float = 0.0,
        candidate_columns: Optional[Dict[str, Optional[str]]] = None,
        warnings: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        confidence_breakdown: Optional[List[str]] = None,
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
        self.record_length = record_length
        self.candidate_layout = candidate_layout or []
        self.disclaimer_lines = disclaimer_lines or []
        self.record_prefix = record_prefix or []
        self.candidate_keys = candidate_keys or []
        self.suggested_joins = suggested_joins or []
        self.error = error
        self.confidence = confidence
        self.candidate_columns = candidate_columns or {}
        self.warnings = warnings or []
        self.recommendations = recommendations or []
        self.confidence_breakdown = confidence_breakdown or []

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
            record_length=getattr(ctx, "record_length", None),
            candidate_layout=getattr(ctx, "candidate_layout", []),
            disclaimer_lines=getattr(ctx, "disclaimer_lines", []),
            record_prefix=getattr(ctx, "record_prefix", []),
            candidate_keys=getattr(ctx, "candidate_keys", []),
            suggested_joins=getattr(ctx, "suggested_joins", []),
            confidence=getattr(ctx, "confidence", 0.0),
            candidate_columns=getattr(ctx, "candidate_columns", {}),
            warnings=getattr(ctx, "warnings", []),
            recommendations=getattr(ctx, "recommendations", []),
            confidence_breakdown=getattr(ctx, "confidence_breakdown", []),
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
        ctx.record_length = self.record_length
        ctx.candidate_layout = self.candidate_layout
        ctx.disclaimer_lines = self.disclaimer_lines
        ctx.record_prefix = self.record_prefix
        ctx.candidate_keys = self.candidate_keys
        ctx.suggested_joins = self.suggested_joins
        ctx.confidence = self.confidence
        ctx.confidence_breakdown = self.confidence_breakdown
        ctx.candidate_columns = self.candidate_columns
        ctx.warnings = self.warnings
        ctx.recommendations = self.recommendations


def detect_file(
    file_paths: List[str],
    source: Optional[IDataSource] = None,
) -> DiscoveryResult:
    """Detect file type and structure from the first file.

    Returns a DiscoveryResult with detected metadata, confidence score,
    candidate column mappings, warnings, and recommendations.
    This is the SINGLE detection entry point. Downstream phases
    must consume this result instead of re-detecting.
    No UI rendering. Pure detection logic.
    """
    if not file_paths:
        return DiscoveryResult(error="No files provided")

    fp = file_paths[0]

    try:
        summary = generate_detection_summary(fp, source=source)

        result = DiscoveryResult(
            file_paths=file_paths,
            file_type=summary["file_type"],
            delimiter=summary["delimiter"],
            columns=summary["columns"] or [],
            header_prefix=summary["header_prefix"],
            trailer_prefix=summary["trailer_prefix"],
            ml_record_types=summary["ml_record_types"],
            record_length=summary.get("record_length"),
            candidate_layout=summary.get("candidate_layout", []),
            start_line=summary.get("start_line", 0),
            disclaimer_lines=summary.get("disclaimer_lines", []),
            record_prefix=summary.get("record_prefix", []),
            candidate_keys=summary.get("candidate_keys", []),
            confidence=summary["confidence"],
            confidence_breakdown=summary.get("confidence_breakdown", []),
            warnings=summary["warnings"],
            recommendations=summary["recommendations"],
        )

        if summary["file_type"] == "fixed" and not summary.get("candidate_layout"):
            result.error = "Fixed-width files require a layout definition (use the Layout Builder)"

        # Propose candidate column mappings
        if result.columns:
            result.candidate_columns = detect_candidate_columns(result.columns)

        return result

    except Exception as e:
        logger.error("Detection failed: %s", str(e), exc_info=True)
        return DiscoveryResult(file_paths=file_paths, error=str(e))


def _get_delimited_columns(
    file_paths: List[str],
    delimiter: Optional[str] = None,
    source: Optional[IDataSource] = None,
) -> List[str]:
    """Get column names from a delimited file."""
    try:
        df = safe_read_csv(file_paths[0], separator=delimiter or ",", n_rows=5, source=source)
        return df.columns
    except Exception as e:
        logger.warning("Could not read delimited columns: %s", e)
        return []

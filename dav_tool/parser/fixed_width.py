"""Fixed-width parser — positional records using a column layout."""
import logging
from typing import Any, List, Optional

import polars as pl

from dav_tool import _parsers
from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.factory import register_parser
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


@register_parser
class FixedWidthParser(BaseParser):
    name = "fixed_width"
    description = "Fixed-width positional records parsed with a column layout."

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        if discovery.file_type != "fixed":
            return False
        return bool(discovery.candidate_layout or discovery.layout)

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        layout = discovery.candidate_layout or discovery.layout or []
        if not layout:
            return ParsedResult(
                canonical_data=pl.DataFrame(),
                metadata={"parser": self.name, "error": "missing layout"},
                discovery=discovery,
                warnings=["Fixed-width files require a layout definition."],
            )

        chunks: List[pl.DataFrame] = []
        for chunk in _parsers.parse_fixed_width_chunks(
            discovery.file_paths,
            layout,
            start_line=discovery.start_line or 0,
            record_type=discovery.record_type,
            chunk_size=kwargs.get("chunk_size") or 10_000,
            source=kwargs.get("source"),
        ):
            chunks.append(chunk)

        data = pl.concat(chunks) if chunks else pl.DataFrame()
        return ParsedResult(
            canonical_data=data,
            metadata={
                "parser": self.name,
                "file_type": discovery.file_type,
                "layout_fields": [c["field"] for c in layout],
                "start_line": discovery.start_line,
                "record_type": discovery.record_type,
                "chunk_count": len(chunks),
            },
            discovery=discovery,
            schema=[c["field"] for c in layout],
        )
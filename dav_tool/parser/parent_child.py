"""Parent/child parser — flattens multi-record files into leaf detail rows.

Handles two architectures:
- **Delimited multiline** (``H|D|T``): a parent prefix row is carried forward
  into every following child row.
- **Fixed-width HDR/detail** (``HDR`` + detail prefixes + optional trailer):
  header fields are parsed with ``header_layout`` and merged into detail rows
  parsed with ``detail_layout``.
"""
import logging
from typing import Any, List, Optional

import polars as pl

from dav_tool import _parsers
from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.factory import register_parser
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


@register_parser
class ParentChildParser(BaseParser):
    name = "parent_child"
    description = "Flattens H/D/T delimited or HDR/detail fixed-width multi-record files."
    priority = 20

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        if discovery.ml_flattened:
            return True
        if discovery.file_type == "multiline":
            return True
        return bool(discovery.header_prefix and discovery.detail_layout)

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        chunk_size = kwargs.get("chunk_size") or 10_000
        chunks: List[pl.DataFrame] = []
        warnings: List[str] = []

        if discovery.header_layout is not None and discovery.detail_layout:
            for chunk in _parsers.flatten_multiline_fixed_width(
                discovery.file_paths,
                discovery.header_prefix or "HDR",
                discovery.header_layout or [],
                discovery.detail_layout,
                chunk_size=chunk_size,
                trailer_prefix=discovery.trailer_prefix,
                trailer_layout=discovery.trailer_layout,
                source=kwargs.get("source"),
            ):
                chunks.append(chunk)
            architecture = "fixed-width"
        else:
            rtypes = discovery.ml_record_types or ["H", "D"]
            for chunk in _parsers.flatten_multiline_chunks(
                discovery.file_paths,
                rtypes,
                delimiter=discovery.ml_delimiter or "|",
                chunk_size=chunk_size,
                source=kwargs.get("source"),
            ):
                chunks.append(chunk)
            architecture = "delimited"

        data = pl.concat(chunks) if chunks else pl.DataFrame()
        return ParsedResult(
            canonical_data=data,
            metadata={
                "parser": self.name,
                "architecture": architecture,
                "record_types": discovery.ml_record_types,
                "chunk_count": len(chunks),
            },
            discovery=discovery,
            schema=list(discovery.columns or data.columns),
            warnings=warnings,
        )
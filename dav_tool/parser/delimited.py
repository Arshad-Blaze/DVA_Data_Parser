"""Delimited parser — plain comma/pipe/tab separated files."""
import logging
from typing import Any, Iterator, List, Optional

import polars as pl

from dav_tool import _parsers
from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.factory import register_parser
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


@register_parser
class DelimitedParser(BaseParser):
    name = "delimited"
    description = "Plain delimited files (comma, pipe, tab) with optional header."

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        return discovery.file_type in ("delimited", "csv", "tsv", "tab")

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        delimiter = discovery.delimiter or ","
        chunk_size = kwargs.get("chunk_size") or 10_000
        chunks: List[pl.DataFrame] = []
        warnings: List[str] = []

        for chunk in _parsers.parse_delimited_chunks(
            discovery.file_paths,
            delimiter,
            chunk_size=chunk_size,
            source=kwargs.get("source"),
        ):
            chunks.append(chunk)

        data = pl.concat(chunks) if chunks else pl.DataFrame()
        return ParsedResult(
            canonical_data=data,
            metadata={
                "parser": self.name,
                "file_type": discovery.file_type,
                "delimiter": delimiter,
                "chunk_count": len(chunks),
            },
            discovery=discovery,
            schema=list(discovery.columns or data.columns),
            warnings=warnings,
        )
"""Flatten Engine — unified interface for multi-record file flattening.

Supports:
- Delimited multiline (H|D|T patterns)
- Fixed-width HDR/Detail/Trailer
- S/U/T and H/D/T record types
- Parent → Child with header caching and value replication
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Union

import polars as pl

from dav_tool.config import DEFAULT_CHUNK_SIZE
from dav_tool.datasource.base import IDataSource
from dav_tool.rejection import RejectionCollector

logger = logging.getLogger(__name__)


@dataclass
class FlattenConfig:
    file_paths: Union[str, List[str]]
    header_prefix: Optional[str] = None
    detail_prefix: Optional[str] = None
    trailer_prefix: Optional[str] = None
    header_layout: Optional[List[Dict[str, Any]]] = None
    detail_layout: Optional[List[Dict[str, Any]]] = None
    trailer_layout: Optional[List[Dict[str, Any]]] = None
    record_types: Optional[List[str]] = None
    delimiter: str = "|"
    chunk_size: int = DEFAULT_CHUNK_SIZE
    source: Optional[IDataSource] = None
    rejection_collector: Optional[RejectionCollector] = None


class FlattenEngine:
    """Unified flattening engine for multi-record files.

    Auto-detects delimited vs. fixed-width format and delegates to the
    appropriate flattening strategy.

    - **Delimited multiline**: lines start with a record type prefix (H, D, T)
      followed by a delimiter.  The prefix is stripped and the remainder split.
    - **Fixed-width multiline**: lines have a header/detail/trailer prefix
      (HDR, S, H, etc.) followed by fixed-width fields defined by layouts.
      Header values are cached and replicated into each detail row.
    - **Parent → Child**: when a header (parent) is encountered, its fields
      are carried forward to all subsequent detail (child) rows until the
      next header or trailer.
    """

    def __init__(self, config: FlattenConfig):
        self._config = config
        self._is_delimited = self._detect_format()

    def _detect_format(self) -> bool:
        cfg = self._config
        if cfg.header_layout is not None:
            return False
        if cfg.header_prefix is not None and cfg.detail_layout is not None:
            return False
        return True

    def iter_flattened(self) -> Iterator[pl.DataFrame]:
        cfg = self._config
        if self._is_delimited:
            yield from self._flatten_delimited()
        else:
            yield from self._flatten_fixed_width()

    def _flatten_delimited(self) -> Iterator[pl.DataFrame]:
        from dav_tool._parsers import flatten_multiline_chunks

        cfg = self._config
        rtypes = cfg.record_types or [cfg.header_prefix or "H", cfg.detail_prefix or "D"]
        if cfg.trailer_prefix and cfg.trailer_prefix not in rtypes:
            rtypes = list(rtypes) + [cfg.trailer_prefix]

        yield from flatten_multiline_chunks(
            cfg.file_paths,
            rtypes,
            delimiter=cfg.delimiter,
            chunk_size=cfg.chunk_size,
            source=cfg.source,
            rejection_collector=cfg.rejection_collector,
        )

    def _flatten_fixed_width(self) -> Iterator[pl.DataFrame]:
        from dav_tool._parsers import flatten_multiline_fixed_width

        cfg = self._config
        hdr_prefix = cfg.header_prefix or "HDR"
        dtl_layout = cfg.detail_layout or []
        trl_prefix = cfg.trailer_prefix
        trl_layout = cfg.trailer_layout

        yield from flatten_multiline_fixed_width(
            cfg.file_paths,
            hdr_prefix,
            cfg.header_layout or [],
            dtl_layout,
            chunk_size=cfg.chunk_size,
            trailer_prefix=trl_prefix,
            trailer_layout=trl_layout,
            source=cfg.source,
            rejection_collector=cfg.rejection_collector,
        )

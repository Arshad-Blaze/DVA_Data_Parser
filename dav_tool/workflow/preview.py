"""Preview Service — raw-data preview wrappers for the UI layer.

Thin delegation layer that keeps the architecture boundary:
UI → Workflow → Parser instead of UI → Parser directly.
"""
from typing import Any, List, Dict, Optional, Iterator, Union

import polars as pl

from dav_tool._parsers import (
    preview_raw as _preview_raw,
    preview_raw_lines as _preview_raw_lines,
    preview_flattened_multiline as _preview_flattened_multiline,
    preview_flattened_multiline_fixed as _preview_flattened_multiline_fixed,
    load_layout as _load_layout,
    parse_fixed_width_chunks as _parse_fixed_width_chunks,
)
from dav_tool.datasource.base import IDataSource


DEFAULT_PREVIEW_ROWS = 10


def preview_raw(
    file_paths: Union[str, List[str]],
    file_type: str,
    delimiter: str = ",",
    layout: Optional[List[Dict]] = None,
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    start_line: int = 0,
    record_type: Optional[str] = None,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    return _preview_raw(
        file_paths, file_type, delimiter=delimiter, layout=layout,
        n_rows=n_rows, start_line=start_line, record_type=record_type,
        source=source,
    )


def preview_raw_lines(
    file_paths: Union[str, List[str]],
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    source: Optional[IDataSource] = None,
) -> List[str]:
    return _preview_raw_lines(file_paths, n_rows=n_rows, source=source)


def preview_flattened_multiline(
    file_paths: Union[str, List[str]],
    record_types: List[str],
    delimiter: str = "|",
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    return _preview_flattened_multiline(
        file_paths, record_types, delimiter=delimiter,
        n_rows=n_rows, source=source,
    )


def preview_flattened_multiline_fixed(
    file_paths: Union[str, List[str]],
    header_prefix: str,
    header_layout: List[Dict[str, Any]],
    detail_layout: List[Dict[str, Any]],
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict[str, Any]]] = None,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    return _preview_flattened_multiline_fixed(
        file_paths, header_prefix, header_layout, detail_layout,
        n_rows=n_rows, trailer_prefix=trailer_prefix,
        trailer_layout=trailer_layout, source=source,
    )


def load_layout(layout_file: str) -> List[Dict[str, Any]]:
    return _load_layout(layout_file)


def parse_fixed_width_chunks(
    file_paths: Union[str, List[str]],
    layout: List[Dict[str, Any]],
    start_line: int = 0,
    record_type: Optional[str] = None,
    chunk_size: int = 100_000,
    source: Optional[IDataSource] = None,
) -> Iterator[pl.DataFrame]:
    return _parse_fixed_width_chunks(
        file_paths, layout, start_line=start_line,
        record_type=record_type, chunk_size=chunk_size, source=source,
    )

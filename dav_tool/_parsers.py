import csv
import io
import logging
import os
import polars as pl
from typing import Iterator, List, Dict, Any, Optional, Union, BinaryIO

from dav_tool.config import DEFAULT_ENCODING, FALLBACK_ENCODING, DEFAULT_CHUNK_SIZE, DEFAULT_PREVIEW_ROWS
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)


def safe_numeric(column: str) -> pl.Expr:
    return (
        pl.col(column)
        .cast(pl.Utf8)
        .str.replace_all(r"[^0-9.eE+\-]", "")
        .cast(pl.Float64)
        .fill_null(0.0)
    )


def load_layout(layout_file: str) -> List[Dict[str, Any]]:
    layout_df = pl.read_csv(layout_file, encoding=FALLBACK_ENCODING)
    cols = [c.strip().lower() for c in layout_df.columns]
    layout_df.columns = cols

    layout = []
    for row in layout_df.iter_rows(named=True):
        start = int(row["from"]) - 1
        length = int(row["length"])
        layout.append({
            "field": str(row["field"]).strip(),
            "start": start,
            "end": start + length,
            "type": str(row.get("type", "text")).lower(),
        })
    return layout


def _open_text_stream(
    file_path: str,
    source: Optional[IDataSource] = None,
    encoding: str = DEFAULT_ENCODING,
) -> io.TextIOBase:
    """Open a text stream from a file path or a remote source.

    When *source* is provided, uses ``source.open_stream()``.
    Falls back to ``open()`` for local files.
    """
    if source is not None:
        try:
            raw: BinaryIO = source.open_stream(file_path)
            return io.TextIOWrapper(raw, encoding=encoding, errors="ignore")
        except Exception:
            logger.exception("Failed to open stream for %s", file_path)
    return open(file_path, "r", encoding=encoding, errors="ignore")


def parse_fixed_width_chunks(
    file_paths: Union[str, List[str]],
    layout: List[Dict[str, Any]],
    start_line: int = 0,
    record_type: Optional[str] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    source: Optional[IDataSource] = None,
) -> Iterator[pl.DataFrame]:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if source is None and not os.path.exists(file_path):
            continue

        with _open_text_stream(file_path, source) as f:
            buffer = []
            for i, line in enumerate(f):
                if i < start_line:
                    continue
                if record_type and not line.startswith(record_type):
                    continue

                record = {}
                for col in layout:
                    end = min(col["end"], len(line))
                    raw = line[col["start"] : end].strip()
                    if col["type"] == "numeric":
                        raw = raw.lstrip("0") or "0"
                    elif col["type"] == "date" and len(raw) == 6:
                        raw = f"20{raw[:2]}-{raw[2:4]}-{raw[4:6]}"
                    record[col["field"]] = raw

                buffer.append(record)
                if len(buffer) >= chunk_size:
                    yield pl.DataFrame(buffer)
                    buffer.clear()

            if buffer:
                yield pl.DataFrame(buffer)


def scan_delimited(
    file_paths: Union[str, List[str]],
    delimiter: str,
    columns: Optional[List[str]] = None,
) -> pl.LazyFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    scans = []
    for f in file_paths:
        scan = pl.scan_csv(
            f, separator=delimiter, encoding=FALLBACK_ENCODING,
            infer_schema_length=0, low_memory=True,
        )
        scans.append(scan)

    lazy = pl.concat(scans)
    if columns:
        lazy = lazy.select([pl.col(c) for c in columns])
    return lazy


def parse_delimited_chunks(
    file_paths: Union[str, List[str]],
    delimiter: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    encoding: str = DEFAULT_ENCODING,
    source: Optional[IDataSource] = None,
) -> Iterator[pl.DataFrame]:
    """Read delimited files in chunks from a stream or file path.

    When *source* is provided, uses ``source.open_stream()`` to stream
    directly from the remote source without downloading the full file.
    Otherwise falls back to ``open(path, "r")``.

    Each chunk is a ``pl.DataFrame`` with string columns.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if source is not None:
            try:
                raw: BinaryIO = source.open_stream(file_path)
                f: io.TextIOBase = io.TextIOWrapper(raw, encoding=encoding, errors="ignore")
            except Exception:
                logger.exception("Failed to open stream for %s, falling back to file path", file_path)
                if not os.path.exists(file_path):
                    continue
                f = open(file_path, "r", encoding=encoding, errors="ignore")
        else:
            if not os.path.exists(file_path):
                continue
            f = open(file_path, "r", encoding=encoding, errors="ignore")

        with f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                header = next(reader)
            except StopIteration:
                continue

            buffer_rows = []
            for row in reader:
                buffer_rows.append(row)
                if len(buffer_rows) >= chunk_size:
                    yield _rows_to_df(buffer_rows, header)
                    buffer_rows.clear()

            if buffer_rows:
                yield _rows_to_df(buffer_rows, header)


def _rows_to_df(rows: List[List[str]], header: List[str]) -> pl.DataFrame:
    """Convert a batch of rows + header into a polars DataFrame."""
    data = {}
    for i, col_name in enumerate(header):
        data[col_name] = [row[i] if i < len(row) else "" for row in rows]
    return pl.DataFrame(data)


def _fields_to_df(buffer):
    max_cols = max(len(row) for row in buffer)
    data = {}
    for i in range(max_cols):
        col_name = f"Column_{i}"
        data[col_name] = [row[i] if i < len(row) else "" for row in buffer]
    return pl.DataFrame(data)


def flatten_multiline_chunks(
    file_paths: Union[str, List[str]],
    record_types: List[str],
    delimiter: str = "|",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    source: Optional[IDataSource] = None,
) -> Iterator[pl.DataFrame]:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if source is None and not os.path.exists(file_path):
            continue

        with _open_text_stream(file_path, source) as f:
            buffer = []
            for line in f:
                line = line.rstrip("\n\r")
                if not line:
                    continue

                for rt in record_types:
                    if line.startswith(rt):
                        rest = line[len(rt) :]
                        if rest.startswith(delimiter):
                            rest = rest[len(delimiter) :]
                        if rest:
                            fields = rest.split(delimiter)
                            buffer.append(fields)
                        break

                if len(buffer) >= chunk_size:
                    yield _fields_to_df(buffer)
                    buffer.clear()

            if buffer:
                yield _fields_to_df(buffer)


def _parse_fields(line: str, layout: List[Dict[str, Any]]) -> Dict[str, str]:
    """Parse fields from *line* using *layout* spec (start/end/type)."""
    record: Dict[str, str] = {}
    for col in layout:
        end = min(col["end"], len(line))
        raw = line[col["start"] : end].strip()
        if col["type"] == "numeric":
            raw = raw.lstrip("0") or "0"
        elif col["type"] == "date" and len(raw) == 6:
            raw = f"20{raw[:2]}-{raw[2:4]}-{raw[4:6]}"
        record[col["field"]] = raw
    return record


def flatten_multiline_fixed_width(
    file_paths: Union[str, List[str]],
    header_prefix: str,
    header_layout: List[Dict[str, Any]],
    detail_layout: List[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict[str, Any]]] = None,
    source: Optional[IDataSource] = None,
) -> Iterator[pl.DataFrame]:
    """Flatten HDR-fixed-width files: extract header fields, merge into detail rows.

    Lines starting with *header_prefix* are parsed with *header_layout* and
    their values carried forward to all subsequent detail (non-header) lines,
    which are parsed with *detail_layout*.

    When *trailer_prefix* and *trailer_layout* are provided, lines starting
    with the trailer prefix act as transaction boundaries: trailer fields are
    attached to each buffered detail row and the buffer is flushed.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if source is None and not os.path.exists(file_path):
            continue

        with _open_text_stream(file_path, source) as f:
            buffer: List[Dict[str, str]] = []
            current_header: Dict[str, str] = {}

            for line in f:
                line = line.rstrip("\n\r")
                if not line:
                    continue

                if line.startswith(header_prefix):
                    current_header = _parse_fields(line, header_layout)
                elif trailer_prefix and line.startswith(trailer_prefix):
                    trailer = _parse_fields(line, trailer_layout) if trailer_layout else {}

                    for record in buffer:
                        record.update(trailer)

                    if buffer:
                        yield pl.DataFrame(buffer)
                        buffer.clear()
                    current_header = {}
                else:
                    if not current_header:
                        continue
                    record = dict(current_header)
                    record.update(_parse_fields(line, detail_layout))
                    buffer.append(record)

                    if not trailer_prefix and len(buffer) >= chunk_size:
                        yield pl.DataFrame(buffer)
                        buffer.clear()

            if buffer:
                yield pl.DataFrame(buffer)


def preview_raw_lines(
    file_paths: Union[str, List[str]],
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    source: Optional[IDataSource] = None,
) -> List[str]:
    """Read raw lines from a file without ANY parsing or interpretation.

    Displays exactly what exists inside the source file — no delimiter
    splitting, no canonical conversion, no flattening, no column mapping.
    This is intended ONLY for understanding source data format.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if not file_paths:
        return []

    fp = file_paths[0]
    if source is None and not os.path.exists(fp):
        return []

    try:
        lines = []
        with _open_text_stream(fp, source) as f:
            for i, line in enumerate(f):
                if n_rows and len(lines) >= n_rows:
                    break
                line = line.rstrip("\n\r")
                if line:
                    lines.append(line)
        return lines
    except Exception:
        logger.warning("preview_raw_lines failed for %s", fp)
        return []


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
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if not file_paths:
        return pl.DataFrame()

    fp = file_paths[0]
    if source is None and not os.path.exists(fp):
        return pl.DataFrame()

    try:
        if file_type == "delimited":
            rows = []
            with _open_text_stream(fp, source) as f:
                for i, line in enumerate(f):
                    if i < start_line:
                        continue
                    if n_rows and len(rows) >= n_rows:
                        break
                    line = line.rstrip("\n\r")
                    if line:
                        rows.append(line.split(delimiter))
            if not rows:
                return pl.DataFrame()
            return (
                pl.DataFrame(rows[1:], schema=rows[0], orient="row")
                if len(rows) > 1
                else pl.DataFrame(rows, orient="row")
            )

        elif file_type == "fixed":
            cols = [c["field"] for c in (layout or [])]
            records = []
            with _open_text_stream(fp, source) as f:
                for i, line in enumerate(f):
                    if i < start_line:
                        continue
                    if record_type and not line.startswith(record_type):
                        continue
                    if n_rows and len(records) >= n_rows:
                        break
                    line = line.rstrip("\n\r")
                    if not line:
                        continue
                    record = {}
                    for col in layout or []:
                        raw = line[col["start"] : col["end"]].strip()
                        record[col["field"]] = raw
                    records.append(record)
            return pl.DataFrame(records) if records else pl.DataFrame()

        elif file_type == "multiline":
            rows = []
            with _open_text_stream(fp, source) as f:
                for i, line in enumerate(f):
                    if n_rows and len(rows) >= n_rows:
                        break
                    line = line.rstrip("\n\r")
                    if line:
                        rows.append([line])
            return (
                pl.DataFrame({"raw_line": [r[0] for r in rows]})
                if rows
                else pl.DataFrame()
            )

        return pl.DataFrame()
    except Exception:
        logger.warning("preview_raw failed for %s (type=%s)", fp, file_type)
        return pl.DataFrame()


def preview_flattened_multiline(
    file_paths: Union[str, List[str]],
    record_types: List[str],
    delimiter: str = "|",
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    source: Optional[IDataSource] = None,
) -> pl.DataFrame:
    for chunk in flatten_multiline_chunks(
        file_paths, record_types, delimiter, chunk_size=n_rows, source=source,
    ):
        return chunk.head(n_rows)
    return pl.DataFrame()


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
    for chunk in flatten_multiline_fixed_width(
        file_paths, header_prefix, header_layout, detail_layout, chunk_size=n_rows,
        trailer_prefix=trailer_prefix, trailer_layout=trailer_layout, source=source,
    ):
        return chunk.head(n_rows)
    return pl.DataFrame()

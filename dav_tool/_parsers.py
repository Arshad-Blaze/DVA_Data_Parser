import os
import polars as pl
from typing import Iterator, List, Dict, Any, Optional, Union

from dav_tool.config import DEFAULT_ENCODING, FALLBACK_ENCODING, DEFAULT_CHUNK_SIZE, DEFAULT_PREVIEW_ROWS


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


def parse_fixed_width_chunks(
    file_paths: Union[str, List[str]],
    layout: List[Dict[str, Any]],
    start_line: int = 0,
    record_type: Optional[str] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[pl.DataFrame]:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
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
) -> Iterator[pl.DataFrame]:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
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


def flatten_multiline_fixed_width(
    file_paths: Union[str, List[str]],
    header_prefix: str,
    header_layout: List[Dict[str, Any]],
    detail_layout: List[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[pl.DataFrame]:
    """Flatten HDR-fixed-width files: extract header fields, merge into detail rows.

    Lines starting with *header_prefix* are parsed with *header_layout* and
    their values carried forward to all subsequent detail (non-header) lines,
    which are parsed with *detail_layout*.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    for file_path in file_paths:
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            buffer = []
            current_header: Dict[str, str] = {}

            for line in f:
                line = line.rstrip("\n\r")
                if not line:
                    continue

                if line.startswith(header_prefix):
                    current_header = {}
                    for col in header_layout:
                        raw = line[col["start"] : col["end"]].strip()
                        if col["type"] == "numeric":
                            raw = raw.lstrip("0") or "0"
                        elif col["type"] == "date" and len(raw) == 6:
                            raw = f"20{raw[:2]}-{raw[2:4]}-{raw[4:6]}"
                        current_header[col["field"]] = raw
                else:
                    if not current_header:
                        continue
                    record = dict(current_header)
                    for col in detail_layout:
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


def preview_raw(
    file_paths: Union[str, List[str]],
    file_type: str,
    delimiter: str = ",",
    layout: Optional[List[Dict]] = None,
    n_rows: int = DEFAULT_PREVIEW_ROWS,
    start_line: int = 0,
    record_type: Optional[str] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if not file_paths:
        return pl.DataFrame()

    fp = file_paths[0]
    if not os.path.exists(fp):
        return pl.DataFrame()

    if file_type == "delimited":
        rows = []
        with open(fp, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
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
            pl.DataFrame(rows[1:], schema=rows[0])
            if len(rows) > 1
            else pl.DataFrame(rows)
        )

    elif file_type == "fixed":
        cols = [c["field"] for c in (layout or [])]
        records = []
        with open(fp, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
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
        with open(fp, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
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


def preview_flattened_multiline(
    file_paths: Union[str, List[str]],
    record_types: List[str],
    delimiter: str = "|",
    n_rows: int = DEFAULT_PREVIEW_ROWS,
) -> pl.DataFrame:
    for chunk in flatten_multiline_chunks(
        file_paths, record_types, delimiter, chunk_size=n_rows
    ):
        return chunk.head(n_rows)
    return pl.DataFrame()


def preview_flattened_multiline_fixed(
    file_paths: Union[str, List[str]],
    header_prefix: str,
    header_layout: List[Dict[str, Any]],
    detail_layout: List[Dict[str, Any]],
    n_rows: int = DEFAULT_PREVIEW_ROWS,
) -> pl.DataFrame:
    for chunk in flatten_multiline_fixed_width(
        file_paths, header_prefix, header_layout, detail_layout, chunk_size=n_rows
    ):
        return chunk.head(n_rows)
    return pl.DataFrame()

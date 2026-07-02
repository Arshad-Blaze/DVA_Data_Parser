import os
import glob
import logging
import polars as pl
from dav_tool._parsers import (
    parse_fixed_width_chunks, preview_flattened_multiline,
    preview_flattened_multiline_fixed,
)
from dav_tool.config import FALLBACK_ENCODING
from dav_tool.io import safe_read_csv

logger = logging.getLogger(__name__)


def clean_path(path):
    if not path:
        return path
    path = path.strip().replace('"', "").replace("'", "")
    path = "".join(c for c in path if c.isprintable())
    return os.path.abspath(os.path.normpath(path))


def get_file_list(path):
    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*")))
    return []


def load_storelist(path, delimiter):
    ext = os.path.splitext(path)[-1].lower()
    if ext in [".xlsx", ".xls"]:
        return pl.read_excel(path)
    return safe_read_csv(path, separator=delimiter)


def get_column_names(paths, file_type, delimiter=",", layout=None, start_line=0,
                     record_type=None, header_prefix=None, header_layout=None):
    if not paths:
        return []
    try:
        if file_type == "delimited":
            df = pl.read_csv(paths[0], separator=delimiter, encoding=FALLBACK_ENCODING, n_rows=5)
            return df.columns
        elif file_type == "fixed" and layout:
            chunks = list(parse_fixed_width_chunks(paths[:1], layout, start_line, record_type, chunk_size=5))
            if chunks:
                return chunks[0].columns
        elif file_type == "multiline":
            if header_prefix and header_layout:
                flat = preview_flattened_multiline_fixed(
                    paths, header_prefix, header_layout, layout or [], n_rows=5
                )
            else:
                rt_list = record_type.split(",") if record_type else ["H", "D"]
                flat = preview_flattened_multiline(paths, rt_list, delimiter, n_rows=5)
            if not flat.is_empty():
                return flat.columns
    except Exception as e:
        logger.warning("Could not determine column names: %s", e)
    return []

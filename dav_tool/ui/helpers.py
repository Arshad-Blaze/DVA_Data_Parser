import os
import glob
import logging
import streamlit as st
import polars as pl
from dav_tool._parsers import (
    parse_fixed_width_chunks, preview_flattened_multiline,
    preview_flattened_multiline_fixed,
)
from dav_tool.config import FALLBACK_ENCODING
from dav_tool.io import safe_read_csv

logger = logging.getLogger(__name__)


def display_execution_summary(metrics):
    st.divider()
    st.markdown("### Execution Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Files Processed", metrics.files_processed)
        st.metric("Rows Processed", f"{metrics.rows_processed:,}")
        st.metric("Unique Stores", f"{metrics.stores_processed:,}")
        st.metric("Unique UPCs", f"{metrics.upcs_processed:,}")
    with c2:
        st.metric("Parse Time", f"{metrics.parse_time:.2f}s")
        st.metric("Aggregation Time", f"{metrics.aggregation_time:.2f}s")
        st.metric("Validation Time", f"{metrics.validation_time:.2f}s")
        st.metric("Report Time", f"{metrics.report_time:.2f}s")
    with c3:
        st.metric("Total Time", f"{metrics.total_execution_time:.2f}s")
        st.metric("Peak Memory", f"{metrics.peak_memory:.1f} MB")
        st.metric("Peak CPU", f"{metrics.peak_cpu:.1f}%")
    if metrics.warnings:
        for w in metrics.warnings:
            st.caption(f":warning: {w}")
    if metrics.errors:
        for e in metrics.errors:
            st.caption(f":x: {e}")


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

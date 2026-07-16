import csv
import io
import logging
import os
from typing import List, Dict, Optional, Tuple

import polars as pl
import streamlit as st

from dav_tool._parsers import preview_raw_lines
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)

LAYOUT_COLUMNS = ["field", "from", "length", "type", "format", "nullable", "description"]
DEFAULT_TYPES = ["text", "numeric", "date"]
SESSION_KEY = "_layout_builder_state"

_DATA_TYPE_SYNONYMS = {
    "text": "text",
    "string": "text",
    "character": "text",
    "char": "text",
    "varchar": "text",
    "numeric": "numeric",
    "number": "numeric",
    "decimal": "numeric",
    "integer": "numeric",
    "int": "numeric",
    "float": "numeric",
    "real": "numeric",
    "date": "date",
    "datetime": "date",
    "timestamp": "date",
}


def _normalize_type(raw: str) -> str:
    t = raw.strip().lower()
    return _DATA_TYPE_SYNONYMS.get(t, "text")


def _layout_to_rows(layout: Optional[List[Dict]]) -> List[dict]:
    if not layout:
        return []
    rows = []
    for col in layout:
        rows.append({
            "field": col.get("field", ""),
            "from": col.get("from", col.get("start", 0) + 1),
            "length": col.get("length", col.get("end", 0) - col.get("start", 0)),
            "type": _normalize_type(col.get("type", "text")),
            "format": col.get("format", ""),
            "nullable": col.get("nullable", False),
            "description": col.get("description", ""),
        })
    return rows


def _rows_to_layout(rows: List[dict]) -> List[Dict]:
    layout = []
    for row in rows:
        start = int(row.get("from", 1)) - 1
        length = int(row.get("length", 1))
        field = str(row.get("field", "")).strip()
        if not field:
            continue
        layout.append({
            "field": field,
            "start": start,
            "end": start + length,
            "from": start + 1,
            "length": length,
            "type": _normalize_type(row.get("type", "text")),
            "format": str(row.get("format", "")),
            "nullable": bool(row.get("nullable", False)),
            "description": str(row.get("description", "")),
        })
    return layout


def _layout_to_csv(layout: List[Dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field", "from", "length", "type", "format", "nullable", "description"])
    for col in layout:
        writer.writerow([
            col["field"],
            col.get("from", col["start"] + 1),
            col.get("length", col["end"] - col["start"]),
            col.get("type", "text"),
            col.get("format", ""),
            col.get("nullable", ""),
            col.get("description", ""),
        ])
    return buf.getvalue()


def _validate_layout(layout: List[Dict]) -> List[str]:
    errors = []
    if not layout:
        errors.append("Layout is empty — add at least one column.")
        return errors
    seen_fields = set()
    for i, col in enumerate(layout):
        field = col.get("field", "").strip()
        if not field:
            errors.append(f"Row {i+1}: Column name is required.")
        elif field in seen_fields:
            errors.append(f"Row {i+1}: Duplicate column name '{field}'.")
        seen_fields.add(field)
        start = col.get("start", 0)
        length = col.get("length", 0)
        if length < 1:
            errors.append(f"Row {i+1}: Length must be >= 1 (got {length}).")
        if start < 0:
            errors.append(f"Row {i+1}: Start position must be >= 1 (got {start+1}).")
        col_type = _normalize_type(col.get("type", "text"))
        if col_type not in ("text", "numeric", "date"):
            errors.append(f"Row {i+1}: Unknown type '{col.get('type')}'. Use text, numeric, or date.")
    overlap_errors = _check_overlaps(layout)
    errors.extend(overlap_errors)
    return errors


def _check_overlaps(layout: List[Dict]) -> List[str]:
    errors = []
    sorted_cols = sorted(layout, key=lambda c: (c.get("start", 0), -(c.get("length", 0))))
    prev_end = 0
    for col in sorted_cols:
        start = col.get("start", 0)
        if start < prev_end:
            errors.append(
                f"Overlap: '{col.get('field', '?')}' starts at {start+1} "
                f"but previous field ends at {prev_end}."
            )
        end = start + col.get("length", 0)
        if end > prev_end:
            prev_end = end
    return errors


def _preview_extracted_columns(
    raw_lines: List[str],
    layout: List[Dict],
    max_rows: int = 20,
) -> pl.DataFrame:
    if not raw_lines or not layout:
        return pl.DataFrame()
    records = []
    for line in raw_lines[:max_rows]:
        record = {}
        for col in layout:
            start = col["start"]
            end = col["end"]
            raw = line[start:end] if start < len(line) else ""
            record[col["field"]] = raw
        records.append(record)
    return pl.DataFrame(records) if records else pl.DataFrame()


def render_layout_builder(
    file_paths: List[str],
    existing_layout: Optional[List[Dict]] = None,
    source: Optional[IDataSource] = None,
    key_prefix: str = "fw",
) -> Optional[List[Dict]]:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = {}
    state = st.session_state[SESSION_KEY]

    st.markdown("#### Raw Preview")
    raw_lines = preview_raw_lines(file_paths, n_rows=10, source=source)
    if raw_lines:
        st.code("\n".join(raw_lines), language="text")
    else:
        st.info("No raw data available for preview.")

    st.markdown("#### Layout Builder")
    st.caption("Define each column's position in the fixed-width record.")

    if "layout_rows" not in state:
        rows = _layout_to_rows(existing_layout)
        state["layout_rows"] = rows if rows else [
            {"field": "", "from": 1, "length": 10, "type": "text", "format": "", "nullable": False, "description": ""},
        ]

    rows = state["layout_rows"]

    uploaded_file = st.file_uploader(
        "Upload existing Layout CSV",
        type=["csv"],
        key=f"{key_prefix}_layout_upload",
    )
    if uploaded_file is not None:
        try:
            df = pl.read_csv(uploaded_file)
            cols = [c.strip().lower() for c in df.columns]
            df.columns = cols
            if all(c in cols for c in ["field", "from", "length"]):
                uploaded_rows = []
                for row in df.iter_rows(named=True):
                    uploaded_rows.append({
                        "field": str(row.get("field", "")).strip(),
                        "from": int(row.get("from", 1)),
                        "length": int(row.get("length", 1)),
                        "type": _normalize_type(str(row.get("type", "text"))),
                        "format": str(row.get("format", "")),
                        "nullable": bool(row.get("nullable", False)),
                        "description": str(row.get("description", "")),
                    })
                state["layout_rows"] = uploaded_rows
                st.success(f"Loaded {len(uploaded_rows)} columns from uploaded CSV.")
                st.rerun()
            else:
                st.error("Uploaded CSV must contain 'field', 'from', and 'length' columns.")
        except Exception as e:
            st.error(f"Failed to parse uploaded CSV: {e}")

    edited_df_data = []
    for r in rows:
        edited_df_data.append({
            "Column Name": r.get("field", ""),
            "Start": r.get("from", 1),
            "Length": r.get("length", 1),
            "Type": _normalize_type(r.get("type", "text")),
            "Format": r.get("format", ""),
            "Nullable": r.get("nullable", False),
            "Description": r.get("description", ""),
        })
    if not edited_df_data:
        edited_df_data.append({
            "Column Name": "", "Start": 1, "Length": 10,
            "Type": "text", "Format": "", "Nullable": False, "Description": "",
        })

    edited_df = pl.DataFrame(edited_df_data)

    column_config = {
        "Column Name": st.column_config.TextColumn("Column Name", width="medium", required=True),
        "Start": st.column_config.NumberColumn("Start", min_value=1, step=1, required=True),
        "Length": st.column_config.NumberColumn("Length", min_value=1, step=1, required=True),
        "Type": st.column_config.SelectColumn("Type", options=DEFAULT_TYPES, required=True),
        "Format": st.column_config.TextColumn("Format", width="small"),
        "Nullable": st.column_config.CheckboxColumn("Nullable"),
        "Description": st.column_config.TextColumn("Description", width="medium"),
    }

    edited = st.data_editor(
        edited_df.to_pandas(),
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{key_prefix}_layout_editor",
    )

    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

    with col1:
        if st.button("Validate Layout", key=f"{key_prefix}_validate_btn", use_container_width=True):
            layout = _rows_to_layout(edited.to_dict("records"))
            errors = _validate_layout(layout)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                st.success("Layout is valid.")

    with col2:
        if st.button("Clear All", key=f"{key_prefix}_clear_btn", use_container_width=True):
            state["layout_rows"] = [
                {"field": "", "from": 1, "length": 10, "type": "text", "format": "", "nullable": False, "description": ""},
            ]
            st.rerun()

    with col3:
        csv_data = None
        layout_for_export = _rows_to_layout(edited.to_dict("records"))
        if layout_for_export:
            csv_data = _layout_to_csv(layout_for_export)
        st.download_button(
            "Download CSV",
            data=csv_data or "",
            file_name="layout.csv",
            mime="text/csv",
            disabled=not csv_data,
            use_container_width=True,
            key=f"{key_prefix}_download_btn",
        )

    with col4:
        if st.button("Preview Extracted Columns", key=f"{key_prefix}_preview_btn", use_container_width=True):
            layout_for_preview = _rows_to_layout(edited.to_dict("records"))
            if layout_for_preview and raw_lines:
                preview_df = _preview_extracted_columns(raw_lines, layout_for_preview, max_rows=10)
                if not preview_df.is_empty():
                    st.dataframe(preview_df.to_pandas(), use_container_width=True)
                else:
                    st.info("No data could be extracted with current layout.")
            else:
                st.info("Define at least one column and ensure raw data is available.")

    st.divider()

    confirm_disabled = False
    layout_confirmed = st.button(
        "Confirm Layout \u2192",
        type="primary",
        use_container_width=True,
        disabled=confirm_disabled,
        key=f"{key_prefix}_confirm_layout",
    )

    if layout_confirmed:
        layout = _rows_to_layout(edited.to_dict("records"))
        errors = _validate_layout(layout)
        if errors:
            for err in errors:
                st.error(err)
            return None
        state["layout_rows"] = edited.to_dict("records")
        return layout

    return None

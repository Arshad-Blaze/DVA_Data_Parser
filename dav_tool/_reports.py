import os
import polars as pl
from typing import List, Dict, Optional, Union

from dav_tool._aggregators import stream_store_aggregate, stream_upc_summary


def generate_file_review(
    file_paths: Union[str, List[str]],
    file_type: str,
    store_col: str,
    upc_col: str,
    units_col: str,
    dollars_col: str,
    date_col: Optional[str] = None,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    price_type: str = "Total Price",
    implied_dollars: bool = False,
    implied_units: bool = False,
    start_line: int = 0,
    record_type: Optional[str] = None,
    multiline_record_types: Optional[List[str]] = None,
    multiline_delimiter: str = "|",
    column_names: Optional[List[str]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
) -> pl.DataFrame:
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    rows = []
    for f in file_paths:
        fname = os.path.basename(f)

        sa = stream_store_aggregate(
            [f], file_type, store_col, units_col, dollars_col,
            delimiter=delimiter, layout=layout,
            price_type=price_type,
            implied_dollars=implied_dollars, implied_units=implied_units,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix,
            header_layout=header_layout,
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
        )

        ua = stream_upc_summary(
            [f], file_type, upc_col, units_col, dollars_col,
            delimiter=delimiter, layout=layout,
            implied_units=implied_units, implied_dollars=implied_dollars,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix,
            header_layout=header_layout,
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
        )

        store_count = sa.height if sa is not None and not sa.is_empty() else 0
        upc_count = ua.height if ua is not None and not ua.is_empty() else 0
        total_units = ua["UNITS_SOLD"].sum() if ua is not None and "UNITS_SOLD" in ua.columns else 0.0
        total_dollars = ua["TOTAL_DOLLARS"].sum() if ua is not None and "TOTAL_DOLLARS" in ua.columns else 0.0

        rows.append({
            "filename": fname,
            "store_count": store_count,
            "upc_count": upc_count,
            "total_units": float(total_units),
            "total_dollars": round(float(total_dollars), 2),
        })

    return pl.DataFrame(rows)

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LayoutField:
    field: str
    start: int
    end: int
    type: str = "text"


@dataclass
class FileConfig:
    paths: list[str]
    file_type: str
    delimiter: Optional[str] = None
    layout: Optional[list[LayoutField]] = None
    start_line: int = 0
    record_type: Optional[str] = None
    multiline_record_types: Optional[list[str]] = None
    multiline_delimiter: str = "|"
    column_names: Optional[list[str]] = None


@dataclass
class AggregateConfig:
    store_col: str = ""
    upc_col: str = ""
    desc_col: str = ""
    units_col: str = ""
    dollars_col: str = ""
    price_type: str = "Total Price"
    implied_units: bool = False
    implied_dollars: bool = False

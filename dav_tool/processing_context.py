from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import polars as pl
from dav_tool._observability import ProcessingMetrics


@dataclass
class ProcessingContext:
    """State for one data processing pipeline (one file set).

    All fields default to None, 0, False, or sensible defaults so that
    a fresh instance represents an empty/unstarted pipeline.
    """

    # === Observability ===
    metrics: ProcessingMetrics = field(default_factory=ProcessingMetrics)

    # === Phase ===
    phase: int = 0

    # === File Detection / Parsing Configuration ===
    file_paths: Optional[List[str]] = None
    file_type: Optional[str] = None
    delimiter: Optional[str] = None
    layout: Optional[List[Dict[str, Any]]] = None
    start_line: int = 0
    record_type: Optional[str] = None
    columns: Optional[List[str]] = None

    # === Multiline / HDR ===
    header_prefix: Optional[str] = None
    header_layout: Optional[List[Dict[str, Any]]] = None
    detail_layout: Optional[List[Dict[str, Any]]] = None
    ml_record_types: Optional[List[str]] = None
    ml_delimiter: str = "|"
    ml_flattened: bool = False
    schema: Optional[List[str]] = None

    # === Column Mapping ===
    store_col: Optional[str] = None
    upc_col: Optional[str] = None
    desc_col: Optional[str] = None
    units_col: Optional[str] = None
    price_col: Optional[str] = None
    price_type: str = "Total Price"
    implied_dollars: bool = False
    implied_units: bool = False

    # === Effective Config (frozen at Save Mapping) ===
    eff_type: Optional[str] = None
    eff_delimiter: Optional[str] = None
    eff_record_type: Optional[str] = None
    eff_layout: Optional[List[Dict[str, Any]]] = None

    # === Store List (onboarding) ===
    storelist_path: Optional[str] = None
    storelist_delim: Optional[str] = None
    storelist_store_col: Optional[str] = None

    # === Pre-computed Aggregations ===
    store_agg: Optional[pl.DataFrame] = None
    item_agg: Optional[pl.DataFrame] = None

    # === Results ===
    compare_result: Optional[Dict[str, str]] = None
    upc_summary: Optional[pl.DataFrame] = None
    file_review: Optional[pl.DataFrame] = None
    done: bool = False

    # === Combined Validation Results (existing flow only) ===
    store_df: Optional[pl.DataFrame] = None
    comparison_df: Optional[pl.DataFrame] = None
    summary_df: Optional[pl.DataFrame] = None
    validation_done: bool = False
    fr_prod: Optional[pl.DataFrame] = None
    fr_test: Optional[pl.DataFrame] = None


@dataclass
class ExistingContext:
    """Session state for the existing (two-sided) comparison flow.

    Wraps two ProcessingContext instances (prod / BAU and test) plus
    shared comparison-level state.
    """
    # === Observability ===
    metrics: ProcessingMetrics = field(default_factory=ProcessingMetrics)

    phase: int = 0
    ml_delimiter: str = "|"
    prod: ProcessingContext = field(default_factory=ProcessingContext)
    test: ProcessingContext = field(default_factory=ProcessingContext)

    # Combined / comparison-level results
    compare_result: Optional[Dict[str, str]] = None
    store_df: Optional[pl.DataFrame] = None
    comparison_df: Optional[pl.DataFrame] = None
    summary_df: Optional[pl.DataFrame] = None
    validation_done: bool = False
    fr_prod: Optional[pl.DataFrame] = None
    fr_test: Optional[pl.DataFrame] = None

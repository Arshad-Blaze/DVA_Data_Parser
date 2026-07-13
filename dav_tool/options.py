"""Immutable option objects for the DVA processing pipeline.

Replaces the 20+ parameter lists in aggregation, validation, and workflow functions.
Each option object bundles related parameters into a single, testable, serializable unit.

Design:
- All fields are immutable (frozen dataclasses)
- Optional fields have sensible defaults
- Objects are constructed once per workflow phase, then passed down
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

from dav_tool.datasource.base import IDataSource


class OutputMode(str, Enum):
    """Determines which downstream stages execute after aggregation.

    VALIDATE        — full pipeline: aggregation → validation → reports
    AGGREGATE_ONLY  — stop after aggregation; export becomes available
    STATISTICS      — aggregation → statistics; skip validation/reports
    EXPORT          — aggregation → export; skip validation/reports
    """
    VALIDATE = "validate"
    AGGREGATE_ONLY = "aggregate_only"
    STATISTICS = "statistics"
    EXPORT = "export"


@dataclass(frozen=True)
class ParseOptions:
    """File parsing configuration — everything the parser needs to know.

    This is the processing contract: once accepted, the parser trusts it
    and does not re-infer anything.
    """
    file_type: str
    delimiter: Optional[str] = None
    encoding: str = "cp1252"
    has_header: bool = True
    start_line: int = 0
    record_type: Optional[str] = None
    layout: Optional[List[Dict[str, Any]]] = None
    column_names: Optional[List[str]] = None
    chunk_size: int = 100_000

    # Multiline / HDR / TRL
    header_prefix: Optional[str] = None
    header_layout: Optional[List[Dict[str, Any]]] = None
    detail_layout: Optional[List[Dict[str, Any]]] = None
    trailer_prefix: Optional[str] = None
    trailer_layout: Optional[List[Dict[str, Any]]] = None
    multiline_record_types: Optional[List[str]] = None
    multiline_delimiter: str = "|"

    @property
    def effective_type(self) -> str:
        """Return the effective file type for the parser.

        For multiline files that have been flattened, the parser
        should treat them as their underlying type.
        """
        return self.file_type

    @classmethod
    def from_context(cls, ctx) -> "ParseOptions":
        """Build ParseOptions from a ProcessingContext."""
        return cls(
            file_type=ctx.file_type or "delimited",
            delimiter=ctx.delimiter,
            encoding=getattr(ctx, "encoding", "cp1252"),
            has_header=getattr(ctx, "has_header", True),
            start_line=ctx.start_line or 0,
            record_type=ctx.record_type,
            layout=ctx.layout,
            column_names=ctx.schema,
            header_prefix=ctx.header_prefix,
            header_layout=ctx.header_layout,
            detail_layout=ctx.detail_layout,
            trailer_prefix=ctx.trailer_prefix,
            trailer_layout=ctx.trailer_layout,
            multiline_record_types=ctx.ml_record_types,
            multiline_delimiter=ctx.ml_delimiter or "|",
        )


@dataclass(frozen=True)
class ColumnMapping:
    """Column mapping for one data side (BAU or Test).

    Maps user-selected column names to the canonical roles
    used by the aggregation and calculation engines.
    """
    store: str
    upc: str
    description: str
    units: str
    price: str
    price_type: str = "Total Price"
    implied_dollars: bool = False
    implied_units: bool = False

    @classmethod
    def from_context(cls, ctx) -> "ColumnMapping":
        """Build ColumnMapping from a ProcessingContext."""
        return cls(
            store=ctx.store_col or "",
            upc=ctx.upc_col or "",
            description=ctx.desc_col or "",
            units=ctx.units_col or "",
            price=ctx.price_col or "",
            price_type=getattr(ctx, "price_type", "Total Price"),
            implied_dollars=getattr(ctx, "implied_dollars", False),
            implied_units=getattr(ctx, "implied_units", False),
        )


@dataclass(frozen=True)
class AggregationOptions:
    """Options for a single aggregation task.

    Bundles ParseOptions + ColumnMapping + level into one object
    that can be passed to aggregate() without 20+ parameters.
    """
    parse: ParseOptions
    mapping: ColumnMapping
    level: str  # "store", "item", "upc"
    source: Optional[IDataSource] = None

    @property
    def file_paths(self) -> Optional[List[str]]:
        return None  # Set by caller, not part of options


@dataclass(frozen=True)
class ValidationOptions:
    """Options for running validations.

    Determines which validations to run and with what settings.
    """
    run_store_validation: bool = True
    run_item_validation: bool = True
    run_compare_store_list: bool = False
    run_summary: bool = True
    run_file_review: bool = True
    store_list_path: Optional[str] = None
    store_list_delimiter: str = ","
    store_list_store_col: Optional[str] = None


@dataclass(frozen=True)
class WorkflowState:
    """Immutable snapshot of a workflow's current state.

    Created at the start of each phase transition.
    UI reads this to render; workflow services write new states.
    """
    phase: int = 0
    file_paths: Optional[List[str]] = None
    parse: Optional[ParseOptions] = None
    mapping: Optional[ColumnMapping] = None
    validation: Optional[ValidationOptions] = None
    output_mode: OutputMode = OutputMode.VALIDATE
    is_complete: bool = False
    error: Optional[str] = None


def validation_options_for_mode(
    mode: OutputMode,
    base: Optional[ValidationOptions] = None,
) -> ValidationOptions:
    """Return ValidationOptions appropriate for the given OutputMode.

    AGGREGATE_ONLY / STATISTICS / EXPORT disable all validation and report
    flags.  VALIDATE keeps whatever the caller specified (or the defaults).
    """
    if mode == OutputMode.VALIDATE:
        return base or ValidationOptions()

    return ValidationOptions(
        run_store_validation=False,
        run_item_validation=False,
        run_compare_store_list=False,
        run_summary=False,
        run_file_review=False,
    )

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

from dav_tool._numeric import NumericParsingConfig


class OutputMode(str, Enum):
    """Determines which downstream stages execute after aggregation.

    RAW_REVIEW          — preview raw canonical data, no aggregation
    AGGREGATE_ONLY      — stop after aggregation; export becomes available
    AGGREGATE_CALCULATE — aggregation + statistics + calculations
    VALIDATE            — full pipeline: aggregation → validation → reports
    STATISTICS          — aggregation → statistics; skip validation/reports
    EXPORT              — aggregation → export; skip validation/reports
    """
    RAW_REVIEW = "raw_review"
    AGGREGATE_ONLY = "aggregate_only"
    AGGREGATE_CALCULATE = "aggregate_calculate"
    VALIDATE = "validate"
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

    # Numeric parsing configuration
    numeric_config: Optional[NumericParsingConfig] = None

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
            numeric_config=getattr(ctx, "numeric_config", None),
        )


@dataclass(frozen=True)
class ColumnMapping:
    """Column mapping for one data side (BAU or Test).

    Maps user-selected column names to the canonical roles
    used by the aggregation and calculation engines.

    ``quantity_strategy`` replaces the older ``quantity_type``:
    - ``"auto"`` (default): weight takes precedence, units fallback
    - ``"prefer_weight"``: same as auto (explicit)
    - ``"prefer_units"``: units take precedence, weight fallback
    - ``"weight_only"``: only weight, ignore units
    - ``"units_only"``: only units, ignore weight

    When ``weight_uom_col`` is set, per-row UOM values are read from
    that column and converted to pounds before aggregation.
    """
    store: str
    upc: str
    description: str
    units: str
    price: str
    price_type: str = "Total Price"
    implied_dollars: bool = False
    implied_units: bool = False
    quantity_type: str = "units"
    weight_col: Optional[str] = None
    weight_uom: str = "lb"
    weight_uom_col: Optional[str] = None
    quantity_strategy: str = "auto"
    weight_qty_col: Optional[str] = None
    units_uom: Optional[str] = None

    @classmethod
    def from_context(cls, ctx) -> "ColumnMapping":
        """Build ColumnMapping from a ProcessingContext."""
        strategy = getattr(ctx, "quantity_strategy", "auto")
        weight_qty_col = getattr(ctx, "weight_qty_col", None) or getattr(ctx, "weight_col", None)
        units_uom = getattr(ctx, "units_uom", None)
        return cls(
            store=ctx.store_col or "",
            upc=ctx.upc_col or "",
            description=ctx.desc_col or "",
            units=ctx.units_col or "",
            price=ctx.price_col or "",
            price_type=getattr(ctx, "price_type", "Total Price"),
            implied_dollars=getattr(ctx, "implied_dollars", False),
            implied_units=getattr(ctx, "implied_units", False),
            quantity_type=getattr(ctx, "quantity_type", "units"),
            weight_col=getattr(ctx, "weight_col", None),
            weight_uom=getattr(ctx, "weight_uom", "lb"),
            weight_uom_col=getattr(ctx, "weight_uom_col", None),
            quantity_strategy=strategy,
            weight_qty_col=weight_qty_col,
            units_uom=units_uom,
        )


@dataclass(frozen=True)
class CanonicalContext:
    """Internal construction contract — consolidated into ``CanonicalDataset``.

    RC2: Downstream layers should prefer ``CanonicalDataset``
    (``dav_tool.workflow.canonical``) as the single input contract.
    This class remains as a construction helper for the Operation Layer
    and is not consumed directly by Processing.
    """
    parse: ParseOptions
    mapping: ColumnMapping
    canonical_schema: List[str] = field(default_factory=list)

    @classmethod
    def from_context(cls, ctx, canonical_schema=None) -> "CanonicalContext":
        """Build CanonicalContext from a ProcessingContext."""
        from dav_tool.workflow.canonical import CanonicalSchema
        parse = ParseOptions.from_context(ctx)
        mapping = ColumnMapping.from_context(ctx)
        if canonical_schema is None:
            schema = getattr(ctx, 'schema', None) or getattr(ctx, 'columns', None) or []
        else:
            schema = canonical_schema
        return cls(
            parse=parse,
            mapping=mapping,
            canonical_schema=list(schema),
        )

    def to_dataset(self, file_paths, level: str, source=None) -> "CanonicalDataset":
        """Convert to a ``CanonicalDataset`` for Processing consumption."""
        from dav_tool.workflow.canonical import CanonicalDataset
        return CanonicalDataset.from_parse_options(
            file_paths, self.parse, self.mapping, level, source=source,
        )



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



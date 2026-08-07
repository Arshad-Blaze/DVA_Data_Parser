"""Pipeline contracts — immutable dataclasses exchanged between stages.

Every stage receives one contract and returns one contract.  Contracts are
immutable (``frozen=True``) so no stage can mutate another stage's output.

Contracts flow:

    ConnectionResult
      ↓
    DiscoveryResult        (reused from dav_tool.workflow.discovery)
      ↓
    DatasetGraph
      ↓
    TransformationPlan
      ↓
    TransformedDataset
      ↓
    ParsedDataset
      ↓
    CanonicalMapping
      ↓
    QuantityResolution
      ↓
    CanonicalDataset       (reused from dav_tool.workflow.canonical)
      ↓
    DataQualityReport
      ↓
    AggregatedDataset
      ↓
    ValidationDataset
      ↓
    InsightsDataset
      ↓
    ReportDataset
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from dav_tool._observability import ProcessingMetrics
from dav_tool.datasource.base import IDataSource
from dav_tool.workflow.discovery import DiscoveryResult


@dataclass(frozen=True)
class ConnectionResult:
    """Contract produced by the Connection Stage.

    Captures the active data source plus resolved file paths.  Downstream
    stages use ``source`` to open streams and ``resolved_paths`` to address
    files without re-running connection logic.
    """
    source: Optional[IDataSource] = None
    resolved_paths: Tuple[str, ...] = ()
    connection_string: str = ""
    supports_direct_path: bool = False


@dataclass(frozen=True)
class DatasetNode:
    """A single dataset participating in the pipeline.

    Attributes:
        role: Semantic role (``"sales"``, ``"product"``, ``"store_list"``).
        file_paths: Source file paths for this dataset.
        columns: Detected physical columns.
        file_type: Detected file type (``delimited``, ``fixed``, ``multiline``).
        delimiter: Detected delimiter (delimited only).
    """
    role: str
    file_paths: Tuple[str, ...] = ()
    columns: Tuple[str, ...] = ()
    file_type: str = "delimited"
    delimiter: Optional[str] = None


@dataclass(frozen=True)
class DatasetGraph:
    """Dataset Graph — describes input datasets and their relationships.

    Produced by the Dataset Graph Stage from a DiscoveryResult.  Consumed by
    the Transformation Planning Stage to derive a TransformationPlan.

    Attributes:
        datasets: Ordered nodes, primary (sales) dataset first.
        relationships: Join key candidates (source column → target column).
        hierarchy: Record hierarchy for multiline files (parent → child types).
        join_keys: Candidate join keys discovered during detection.
        file_roles: Path → role mapping.
        parser_recommendation: Recommended pipeline name.
        confidence: Detection confidence (0.0–1.0).
        metadata: Free-form metadata (encoding, architecture, etc.).
    """
    datasets: Tuple[DatasetNode, ...] = ()
    relationships: Tuple[Dict[str, str], ...] = ()
    hierarchy: Dict[str, str] = field(default_factory=dict)
    join_keys: Tuple[Dict[str, Any], ...] = ()
    file_roles: Dict[str, str] = field(default_factory=dict)
    parser_recommendation: str = "delimited"
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def primary(self) -> Optional[DatasetNode]:
        """The primary (sales) dataset, if any."""
        for node in self.datasets:
            if node.role == "sales":
                return node
        return self.datasets[0] if self.datasets else None


@dataclass(frozen=True)
class TransformationPlan:
    """Transformation Plan — the set of data transformations to apply.

    Produced by the Transformation Planning Stage from a DatasetGraph.
    Consumed by the Parser Pipeline Stage.

    Attributes:
        flatten_operations: Multiline flatten descriptions (record tree config).
        join_operations: Enrichment joins (left joins against product masters).
        header_removal: Lines to skip at the top of the file.
        trailer_removal: Record prefixes that mark trailers to drop.
        metadata_removal: Record prefixes that are pure metadata.
        parent_replication: Parent fields to replicate onto child rows.
        child_expansion: Child record types to expand into detail rows.
        column_normalization: Physical → canonical column normalization.
    """
    flatten_operations: Tuple[Dict[str, Any], ...] = ()
    join_operations: Tuple[Dict[str, Any], ...] = ()
    header_removal: int = 0
    trailer_removal: Tuple[str, ...] = ()
    metadata_removal: Tuple[str, ...] = ()
    parent_replication: Tuple[str, ...] = ()
    child_expansion: Tuple[str, ...] = ()
    column_normalization: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TransformedDataset:
    """Transformed Dataset — the output of the Transformation Engine Stage.

    Produced by executing a :class:`TransformationPlan` against the raw
    input records.  This contract carries the *transformed* records — headers,
    trailers and metadata removed, parents replicated onto children
    (flattened), and relationship joins applied — so parsers consume clean
    records and never see raw file structure.

    The Transformation Engine performs no parsing: it only reshapes records.
    Attributes:
        records: Transformed record DataFrame (physical ``Column_N`` fields).
        record_types: Surviving record type prefixes.
        layout: Fixed-width layout applied (if any).
        operations: Names of the operations executed.
        metadata: Execution metadata (delimiter, file type, etc.).
        warnings: Non-fatal transformation warnings.
        discovery: The DiscoveryResult that drove the plan.
    """
    records: pl.DataFrame = field(default_factory=pl.DataFrame)
    record_types: Tuple[str, ...] = ()
    layout: Optional[List[Dict[str, Any]]] = None
    operations: Tuple[str, ...] = ()
    join_operations: Tuple[Dict[str, Any], ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: Tuple[str, ...] = ()
    discovery: Optional[DiscoveryResult] = None


@dataclass(frozen=True)
class ParsedDataset:
    """Parsed Dataset — the output of the Parser Pipeline Stage.

    Wraps the parser result with a stable schema description.  All file
    format details are resolved by this point.

    Attributes:
        data: Parsed, flattened DataFrame (physical columns).
        schema: Column names (physical).
        parser_name: Parser that produced the result.
        discovery: The DiscoveryResult that drove parsing.
        row_count: Number of rows in ``data``.
        metadata: Parse metadata (chunk count, record types, etc.).
        warnings: Parsing warnings.
    """
    data: pl.DataFrame = field(default_factory=pl.DataFrame)
    schema: Tuple[str, ...] = ()
    parser_name: str = "delimited"
    discovery: Optional[DiscoveryResult] = None
    row_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ColumnAssignment:
    """One canonical field → physical column assignment.

    Attributes:
        canonical: Canonical field name (see ``canonical_schema.CANONICAL_FIELDS``).
        physical: Physical column name, or None when unmapped.
        confidence: Mapping confidence (0.0–1.0).
        source: ``"suggestion"``, ``"alias"``, or ``"override"``.
        aliases: Known retailer spellings that matched.
    """
    canonical: str
    physical: Optional[str] = None
    confidence: float = 0.0
    source: str = "alias"
    aliases: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalMapping:
    """Canonical Mapping — explicit physical → canonical column mapping.

    Produced by the Canonical Mapping Stage from the ParsedDataset's physical
    schema plus user overrides.  Consumed by the Quantity Resolution and
    Canonical Dataset stages.  No downstream layer reads retailer column
    names; they only read canonical fields through this mapping.

    Attributes:
        assignments: One :class:`ColumnAssignment` per canonical field.
        level: Aggregation level (``"store"``, ``"item"``, ``"upc"``).
        suggestions: Detection-provided suggested mappings (canonical → physical).
        overrides: User overrides (canonical → physical).
        confidence: Overall mapping confidence (0.0–1.0).
        metadata: Free-form metadata (physical columns, detected roles, etc.).
    """
    assignments: Tuple[ColumnAssignment, ...] = ()
    level: str = "item"
    suggestions: Dict[str, str] = field(default_factory=dict)
    overrides: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def physical(self, canonical: str) -> Optional[str]:
        """Return the mapped physical column for *canonical*, or None."""
        for a in self.assignments:
            if a.canonical == canonical:
                return a.physical
        return None

    def has(self, canonical: str) -> bool:
        return self.physical(canonical) is not None


@dataclass(frozen=True)
class QuantityResolution:
    """Quantity Resolution — how mixed units/weight are resolved.

    Produced by the Quantity Resolution Stage from the CanonicalMapping and
    user configuration.  Consumed by the Canonical Dataset Stage, which
    preserves provenance columns when ``preserve_provenance`` is True.

    Attributes:
        strategy: ``QuantityStrategy`` value (``auto``, ``prefer_units``, ...).
        weight_uom: Default weight UOM (``"lb"`` unless overridden).
        weight_uom_col: Physical column carrying per-row UOM, if any.
        units_uom: UOM of the units column, if any.
        preserve_provenance: Emit OriginalUnits/OriginalWeight/ResolvedQuantity/
            QuantitySource/WeightUOM columns.
        columns: Provenance columns that will be emitted.
        metadata: Free-form metadata (mapping confidence, quantity type, etc.).
    """
    strategy: str = "auto"
    weight_uom: str = "lb"
    weight_uom_col: Optional[str] = None
    units_uom: Optional[str] = None
    preserve_provenance: bool = True
    columns: Tuple[str, ...] = (
        "OriginalUnits", "OriginalWeight", "ResolvedQuantity",
        "QuantitySource", "WeightUOM",
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataQualityCheck:
    """A single data-quality check result."""
    check: str
    passed: bool = True
    count: int = 0
    details: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DataQualityReport:
    """Data Quality Report — output of the Data Quality Stage.

    Runs on the canonical dataset BEFORE aggregation.  The report records
    warnings/errors but never stops the pipeline unless ``rejected`` is set
    (configurable).  Aggregation proceeds regardless.

    Attributes:
        checks: Every executed check.
        warnings: Non-fatal findings (duplicates, nulls, invalid values).
        errors: Rejectable findings (missing mandatory columns, corrupt data).
        rejected: Whether the dataset is rejected (configured failure).
        row_count: Total canonical rows inspected.
        metadata: Free-form metadata (pipeline, file paths, elapsed).
    """
    checks: Tuple[DataQualityCheck, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    rejected: bool = False
    row_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InsightsDataset:
    """Insights Dataset — output of the Insights Engine Stage.

    Produced from the AggregatedDataset (and optionally the ValidationDataset).
    Consumed exclusively by the Reporting Stage, which only formats these
    frames — it never computes business metrics.

    Attributes:
        frames: Named insight frames (top stores, categories, brands, etc.).
        kpis: Single-row summary KPI DataFrame.
        metadata: Free-form metadata (level, row counts, elapsed).
    """
    frames: Dict[str, pl.DataFrame] = field(default_factory=dict)
    kpis: Optional[pl.DataFrame] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedDataset:
    """Aggregated Dataset — the output of the Aggregation Stage.

    Consumed exclusively by the Validation Stage.  Aggregation must never
    know about UI, parser, or discovery details.

    For the two-sided (format-change) flow, ``prod_*``/``test_*`` carry the
    BAU and TEST aggregations; the single-side ``store``/``item``/``upc``
    fields carry the primary side.
    """
    level: str = "item"
    store: Optional[pl.DataFrame] = None
    item: Optional[pl.DataFrame] = None
    upc: Optional[pl.DataFrame] = None
    prod_store: Optional[pl.DataFrame] = None
    prod_item: Optional[pl.DataFrame] = None
    test_store: Optional[pl.DataFrame] = None
    test_item: Optional[pl.DataFrame] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleResult:
    """Result of a single validation rule."""
    rule: str
    passed: bool = True
    message: str = ""
    data: Optional[pl.DataFrame] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationDataset:
    """Validation Dataset — the output of the Validation Stage.

    Consumed exclusively by the Reporting Stage.  Validation never calls
    reporting; it only produces this contract.

    ``summaries`` carries the aggregated summary frames forward so Reporting
    can build KPIs without re-aggregating or touching Aggregation internals.
    Reporting reads every value it needs from this single contract.

    Attributes:
        rule_results: Results of every executed rule.
        store_difference: Store-level BAU vs TEST comparison.
        item_difference: Item-level BAU vs TEST comparison.
        item_summary: Item comparison summary.
        store_list_result: Store-list set-difference result.
        summaries: Aggregated summary frames (store/UPC) for reporting KPIs.
        metadata: Report-oriented metadata (file paths, file type, labels).
        errors: Recoverable rule errors.
        warnings: Rule warnings.
    """
    rule_results: Tuple[RuleResult, ...] = ()
    store_difference: Optional[pl.DataFrame] = None
    item_difference: Optional[pl.DataFrame] = None
    item_summary: Optional[pl.DataFrame] = None
    store_list_result: Optional[Dict[str, str]] = None
    summaries: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DownloadArtifact:
    """A single downloadable report file."""
    filename: str
    data: str
    label: str = ""
    mime_type: str = "text/csv"


@dataclass(frozen=True)
class ReportDataset:
    """Report Dataset — the output of the Reporting Stage.

    Consumed by the UI for rendering.  Reporting never performs aggregation,
    parsing, or metric calculation; it only formats a ValidationDataset and an
    InsightsDataset into downloadable artifacts and summary worksheets.

    Attributes:
        artifacts: Downloadable CSV artifacts.
        summary_kpis: Summary analytics DataFrame (from the Insights Dataset).
        summary_sheets: Named worksheets (top stores, top UPCs, etc.).
        metrics: Execution metrics snapshot.
        migration_report_json: Optional JSON migration/certification report.
    """
    artifacts: Tuple[DownloadArtifact, ...] = ()
    summary_kpis: Optional[pl.DataFrame] = None
    summary_sheets: Dict[str, pl.DataFrame] = field(default_factory=dict)
    metrics: Optional[Dict[str, Any]] = None
    migration_report_json: Optional[str] = None


@dataclass(frozen=True)
class PipelineRun:
    """Immutable snapshot of a completed pipeline execution."""
    pipeline_name: str
    stages_completed: Tuple[str, ...] = ()
    started_at: float = 0.0
    finished_at: float = 0.0
    elapsed: float = 0.0
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    metrics: Optional[ProcessingMetrics] = None

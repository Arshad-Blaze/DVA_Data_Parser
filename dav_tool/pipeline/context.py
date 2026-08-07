"""Pipeline Context — the single context carried through the pipeline.

Replaces the multiple independent contexts (ProcessingContext,
ExistingContext) with one PipelineContext.  Every stage reads and writes only
its own section; no stage may reach into another stage's internal state.

Sections map 1:1 to the data contracts:

    connection         → ConnectionResult
    discovery          → DiscoveryResult
    graph              → DatasetGraph
    plan               → TransformationPlan
    transformed        → TransformedDataset
    parsed             → ParsedDataset
    mapping            → CanonicalMapping
    quantity_resolution→ QuantityResolution
    canonical          → CanonicalDataset
    quality            → DataQualityReport
    aggregated         → AggregatedDataset
    validation         → ValidationDataset
    insights           → InsightsDataset
    report             → ReportDataset

Cross-cutting state (metrics, warnings, errors, progress) lives on the
context itself, not inside any contract.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dav_tool._observability import ProcessingMetrics
from dav_tool.workflow.canonical import CanonicalDataset
from dav_tool.workflow.discovery import DiscoveryResult

from .contracts import (
    AggregatedDataset,
    CanonicalMapping,
    ConnectionResult,
    DataQualityReport,
    DatasetGraph,
    InsightsDataset,
    ParsedDataset,
    QuantityResolution,
    ReportDataset,
    TransformedDataset,
    TransformationPlan,
    ValidationDataset,
)

logger = logging.getLogger(__name__)


class PipelineContext:
    """Single container for all pipeline state.

    Each attribute is a *section* owned by exactly one stage.  Stages are
    handed the context and write only their section.  Consumers read only
    the sections produced by earlier stages.
    """

    def __init__(
        self,
        pipeline_name: str = "standard_delimited",
        phase: int = 0,
        source: Optional[Any] = None,
    ) -> None:
        # ── Identity / progress ─────────────────────────────────────
        self.pipeline_name: str = pipeline_name
        self.phase: int = phase
        self.completed_stages: List[str] = []

        # ── Cross-cutting ───────────────────────────────────────────
        self.metrics: ProcessingMetrics = ProcessingMetrics()
        self.warnings: List[str] = []
        self.errors: List[str] = []

        # ── Stage sections ──────────────────────────────────────────
        self.connection: Optional[ConnectionResult] = None
        self.discovery: Optional[DiscoveryResult] = None
        self.graph: Optional[DatasetGraph] = None
        self.plan: Optional[TransformationPlan] = None
        self.transformed: Optional[TransformedDataset] = None
        self.parsed: Optional[ParsedDataset] = None
        self.mapping: Optional[CanonicalMapping] = None
        self.quantity_resolution: Optional[QuantityResolution] = None
        self.canonical: Optional[CanonicalDataset] = None
        self.quality: Optional[DataQualityReport] = None
        self.aggregated: Optional[AggregatedDataset] = None
        self.validation: Optional[ValidationDataset] = None
        self.insights: Optional[InsightsDataset] = None
        self.report: Optional[ReportDataset] = None

        # ── Shared execution inputs (owned by the engine / UI) ──────
        self.source: Optional[Any] = source
        self.file_paths: List[str] = []
        self.user_config: Dict[str, Any] = {}

    # ── Section accessors (read-only for consumers) ────────────────

    @property
    def has_connection(self) -> bool:
        return self.connection is not None

    @property
    def has_discovery(self) -> bool:
        return self.discovery is not None

    @property
    def has_graph(self) -> bool:
        return self.graph is not None

    @property
    def has_plan(self) -> bool:
        return self.plan is not None

    @property
    def has_transformed(self) -> bool:
        return self.transformed is not None

    @property
    def has_parsed(self) -> bool:
        return self.parsed is not None

    @property
    def has_mapping(self) -> bool:
        return self.mapping is not None

    @property
    def has_quantity_resolution(self) -> bool:
        return self.quantity_resolution is not None

    @property
    def has_canonical(self) -> bool:
        return self.canonical is not None

    @property
    def has_quality(self) -> bool:
        return self.quality is not None

    @property
    def has_aggregated(self) -> bool:
        return self.aggregated is not None

    @property
    def has_validation(self) -> bool:
        return self.validation is not None

    @property
    def has_insights(self) -> bool:
        return self.insights is not None

    @property
    def has_report(self) -> bool:
        return self.report is not None

    # ── Observability helpers ──────────────────────────────────────

    def record_stage(self, stage_name: str, elapsed: float) -> None:
        """Record a completed stage name and duration on metrics."""
        self.completed_stages.append(stage_name)
        self.metrics.record("parse", stage_name, elapsed) if stage_name.startswith("parse") else None
        try:
            self.metrics.record("aggregation", stage_name, elapsed)
        except Exception as exc:  # defensive — never break the pipeline
            logger.debug("metrics.record failed for %s: %s", stage_name, exc)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error("%s", message)

    def summarize(self) -> Dict[str, Any]:
        """Return a plain-dict snapshot (for UI display and reports)."""
        return {
            "pipeline": self.pipeline_name,
            "phase": self.phase,
            "completed_stages": list(self.completed_stages),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metrics": {
                "rows_processed": getattr(self.metrics, "rows_processed", 0),
                "total_execution_time": getattr(self.metrics, "total_execution_time", 0.0),
                "peak_memory": getattr(self.metrics, "peak_memory", 0.0),
            },
        }

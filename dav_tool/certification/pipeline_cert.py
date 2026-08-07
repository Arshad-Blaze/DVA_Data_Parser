"""Pipeline Certification — prove every retailer runs the SAME architecture.

Drives each retailer dataset through the unified :class:`WorkflowEngine`
pipeline (Connection → Discovery → Dataset Graph → Transformation Planner →
Transformation Engine → Parser Pipeline → Canonical Mapping → Quantity
Resolution → Canonical Dataset → Data Quality → Aggregation → Validation →
Insights Engine → Reporting → Downloads).

Only DiscoveryResult, DatasetGraph and TransformationPlan may differ across
retailers.  Every retailer executes the identical stage sequence.

Also maps each certification dataset to one or more of the 20 documented
retailer scenarios.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from dav_tool.datasource.local import LocalDataSource
from dav_tool.format_config import FormatConfig, apply_format_config, load_format_config
from dav_tool.pipeline.context import PipelineContext
from dav_tool.pipeline.engine import WorkflowEngine
from dav_tool.pipeline.registry import PipelineRegistry
from dav_tool.pipeline.standard_pipelines import register_standard_pipelines
from dav_tool.processing_context import ProcessingContext

from .runner import CERTIFICATION_ROOT, discover_retailer_datasets

logger = logging.getLogger(__name__)

#: canonical stage order the certification asserts for every retailer
REQUIRED_STAGES = [
    "connection", "discovery", "dataset_graph", "transform_plan",
    "transformation_engine", "parser_pipeline", "canonical_mapping",
    "quantity_resolution", "canonical_dataset", "data_quality",
    "aggregation", "validation", "insights", "reporting",
]

#: scenario manifest — dataset key → scenario list (see PROMPT.md §RETAILER
#: CERTIFICATION).  Some scenarios exercise the same dataset; scenarios not
#: yet backed by a dataset are covered by targeted scenario datasets.
SCENARIO_MANIFEST: Dict[str, List[int]] = {
    ("delimited", "retailer_grocery"): [1, 4, 11],
    ("delimited", "retailer_pharmacy"): [1, 4, 15, 16],
    ("fixed_width", "retailer_pharmacy_fw"): [2],
    ("record_based", "retailer_heb"): [3],
    ("multiline", "retailer_wholesale"): [8, 9, 10, 13],
    ("header_detail", "retailer_apparel"): [6, 8, 12],
    ("malformed", "retailer_legacy"): [12, 16],
    ("unicode", "retailer_global"): [12, 15],
}

#: scenario → human-readable label
SCENARIO_LABELS: Dict[int, str] = {
    1: "Delimited — weight + units",
    2: "Pure fixed width",
    3: "HEB record-based (HDR/Store/Detail/Trailer)",
    4: "Simple delimited",
    5: "Sales + Product (relationship)",
    6: "Header delimiter differs from detail delimiter",
    7: "Parent child",
    8: "Header trailer",
    9: "Metadata blocks",
    10: "Blank lines",
    11: "Mixed quantity",
    12: "Different encodings",
    13: "Variable width records",
    14: "Large files",
    15: "Quoted delimiters",
    16: "Missing headers",
    17: "Duplicate headers",
    18: "Multiple sheets (Excel)",
    19: "Relationship datasets",
    20: "Future unknown retailer",
}


@dataclass
class StageTrace:
    """Per-stage certification trace (input/output/time/warnings/errors)."""
    name: str = ""
    input_: str = ""
    output: str = ""
    elapsed: float = 0.0
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    recovery: str = ""


@dataclass
class PipelineCertificationResult:
    """Result of certifying a single retailer through the pipeline."""
    category: str = ""
    retailer: str = ""
    scenarios: List[int] = field(default_factory=list)
    passed: bool = False
    duration: float = 0.0
    stages: List[str] = field(default_factory=list)
    traces: List[StageTrace] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineCertificationSuite:
    """Aggregated result across all retailer pipeline certifications."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    duration: float = 0.0
    results: List[PipelineCertificationResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"{self.passed}/{self.total} retailers certified ({self.duration:.2f}s)"


class PipelineCertificationRunner:
    """Runs every retailer dataset through the unified WorkflowEngine."""

    def __init__(self, root: Optional[str] = None):
        self.root = root or CERTIFICATION_ROOT
        self._registry = PipelineRegistry()
        register_standard_pipelines(self._registry)

    # ── Public API ────────────────────────────────────────────────

    def run_all(self) -> PipelineCertificationSuite:
        suite = PipelineCertificationSuite()
        datasets = discover_retailer_datasets(self.root)
        t0 = time.perf_counter()
        for category, retailer in datasets:
            result = self.run_one(category, retailer)
            suite.results.append(result)
            suite.total += 1
            if result.passed:
                suite.passed += 1
            else:
                suite.failed += 1
        suite.duration = time.perf_counter() - t0
        return suite

    def run_one(self, category: str, retailer: str) -> PipelineCertificationResult:
        result = PipelineCertificationResult(
            category=category,
            retailer=retailer,
            scenarios=SCENARIO_MANIFEST.get((category, retailer), []),
        )
        t0 = time.perf_counter()
        retailer_dir = os.path.join(self.root, category, retailer)
        bau_files = _files_in(os.path.join(retailer_dir, "BAU"))
        config_path = os.path.join(retailer_dir, "Config", "config.json")

        if not bau_files:
            result.errors.append("No BAU files found")
            result.duration = time.perf_counter() - t0
            return result

        user_config, load_errors = self._build_user_config(
            retailer_dir, bau_files, config_path,
        )
        if load_errors:
            result.errors.extend(load_errors)
            result.duration = time.perf_counter() - t0
            return result

        ctx = PipelineContext(
            pipeline_name="standard_delimited",
            source=LocalDataSource(),
        )
        ctx.file_paths = bau_files
        ctx.user_config = user_config

        engine = WorkflowEngine(registry=self._registry, context=ctx)
        run = engine.run(ctx)

        result.stages = list(ctx.completed_stages)
        result.traces = _build_traces(ctx)
        result.warnings = list(run.warnings)
        result.errors = list(run.errors)

        _append_quality_errors(result.errors, ctx)
        result.details = {
            "file_type": user_config.get("file_type"),
            "file_count": len(bau_files),
            "mapping_confidence": getattr(ctx.mapping, "confidence", None),
            "quantity_strategy": user_config.get("quantity_strategy", "auto"),
            "aggregated_rows": _aggregated_rows(ctx),
            "insight_frames": sorted(ctx.insights.frames.keys())
            if ctx.insights is not None else [],
            "quality_checks": len(ctx.quality.checks)
            if ctx.quality is not None else 0,
            "artifacts": [a.filename for a in (ctx.report.artifacts if ctx.report else [])],
        }
        result.passed = self._assess(ctx, result)
        result.duration = time.perf_counter() - t0
        return result

    # ── Config → user_config ──────────────────────────────────────

    def _build_user_config(
        self,
        retailer_dir: str,
        bau_files: List[str],
        config_path: str,
    ) -> Tuple[Dict[str, Any], List[str]]:
        errors: List[str] = []
        user_config: Dict[str, Any] = {
            "level": "item",
            "preserve_quantity_provenance": True,
        }
        try:
            cfg = load_format_config(config_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Config load error: {exc}")
            return user_config, errors

        ctx = ProcessingContext()
        try:
            apply_format_config(cfg, ctx, os.path.dirname(config_path), bau_files)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Config application error: {exc}")
            return user_config, errors

        user_config.update(_ctx_to_user_config(ctx))
        user_config["schema_template"] = (
            "enriched" if user_config.get("category_col") or user_config.get("brand_col")
            else "minimal"
        )
        return user_config, errors

    # ── Assessment ────────────────────────────────────────────────

    def _assess(self, ctx: PipelineContext, result: PipelineCertificationResult) -> bool:
        if result.errors:
            return False
        missing = [s for s in REQUIRED_STAGES if s not in result.stages]
        if missing:
            result.errors.append(f"Missing stages: {missing}")
            return False
        if ctx.aggregated is None:
            result.errors.append("No AggregatedDataset produced")
            return False
        if ctx.validation is None:
            result.errors.append("No ValidationDataset produced")
            return False
        if ctx.insights is None:
            result.errors.append("No InsightsDataset produced")
            return False
        if ctx.report is None:
            result.errors.append("No ReportDataset produced")
            return False
        return True

    # ── Reports ───────────────────────────────────────────────────

    def generate_report(self, suite: PipelineCertificationSuite, fmt: str = "markdown") -> str:
        if fmt == "json":
            return json.dumps(_suite_to_dict(suite), indent=2)
        return _report_markdown(suite)


# ── Helpers ────────────────────────────────────────────────────────


def _files_in(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f) for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f)) and not f.startswith(".")
    )


def _ctx_to_user_config(ctx: ProcessingContext) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "file_type": ctx.file_type,
        "delimiter": ctx.delimiter,
        "encoding": getattr(ctx, "encoding", None),
        "start_line": ctx.start_line,
        "record_type": ctx.record_type,
        "store_col": ctx.store_col,
        "upc_col": ctx.upc_col,
        "desc_col": ctx.desc_col,
        "units_col": ctx.units_col,
        "price_col": ctx.price_col,
        "price_type": ctx.price_type,
        "implied_dollars": ctx.implied_dollars,
        "implied_units": ctx.implied_units,
        "quantity_strategy": ctx.quantity_strategy or "auto",
        "weight_uom": ctx.weight_uom or "lb",
        "weight_qty_col": ctx.weight_qty_col or ctx.weight_col,
        "weight_uom_col": ctx.weight_uom_col,
        "date_col": getattr(ctx, "date_col", None),
    }
    if ctx.header_prefix:
        cfg["header_prefix"] = ctx.header_prefix
    if ctx.header_layout:
        cfg["header_layout"] = ctx.header_layout
    if ctx.detail_layout:
        cfg["detail_layout"] = ctx.detail_layout
    if ctx.trailer_prefix:
        cfg["trailer_prefix"] = ctx.trailer_prefix
    if ctx.trailer_layout:
        cfg["trailer_layout"] = ctx.trailer_layout
    if ctx.ml_record_types:
        cfg["multiline_record_types"] = ctx.ml_record_types
        cfg["multiline_delimiter"] = ctx.ml_delimiter or "|"
    if ctx.layout:
        cfg["layout"] = ctx.layout
        fields = [
            d.get("field") or d.get("Field") or d.get("name")
            for d in ctx.layout if (d.get("field") or d.get("Field") or d.get("name"))
        ]
        if fields:
            cfg["column_names"] = fields
    elif ctx.schema or ctx.columns:
        cfg["column_names"] = list(ctx.schema or ctx.columns)
    if getattr(ctx, "numeric_config", None) is not None:
        cfg["numeric_config"] = ctx.numeric_config
    return cfg


def _build_traces(ctx: PipelineContext) -> List[StageTrace]:
    traces: List[StageTrace] = []
    for name in REQUIRED_STAGES:
        elapsed = 0.0
        try:
            elapsed = _stage_elapsed(ctx, name)
        except Exception:  # noqa: BLE001
            elapsed = 0.0
        traces.append(
            StageTrace(
                name=name,
                input_=_stage_input(ctx, name),
                output=_stage_output(ctx, name),
                elapsed=elapsed,
                warnings=(),
                errors=(),
                recovery="continue",
            )
        )
    return traces


def _stage_elapsed(ctx: PipelineContext, name: str) -> float:
    metrics = ctx.metrics
    table = getattr(metrics, "_records", None)
    if table is None:
        return 0.0
    try:
        import polars as pl
        df = table if isinstance(table, pl.DataFrame) else None
        if df is None:
            return 0.0
        matches = df.filter(pl.col("phase") == name)
        if matches.is_empty():
            return 0.0
        return float(matches["elapsed"].first())
    except Exception:  # noqa: BLE001
        return 0.0


def _stage_input(ctx: PipelineContext, name: str) -> str:
    mapping = {
        "connection": "file paths",
        "discovery": "ConnectionResult",
        "dataset_graph": "DiscoveryResult",
        "transform_plan": "DatasetGraph",
        "transformation_engine": "TransformationPlan",
        "parser_pipeline": "TransformedDataset",
        "canonical_mapping": "ParsedDataset",
        "quantity_resolution": "CanonicalMapping",
        "canonical_dataset": "QuantityResolution",
        "data_quality": "CanonicalDataset",
        "aggregation": "CanonicalDataset",
        "validation": "AggregatedDataset",
        "insights": "AggregatedDataset",
        "reporting": "ValidationDataset + InsightsDataset",
    }
    return mapping.get(name, "")


def _stage_output(ctx: PipelineContext, name: str) -> str:
    mapping = {
        "connection": "ConnectionResult",
        "discovery": "DiscoveryResult",
        "dataset_graph": "DatasetGraph",
        "transform_plan": "TransformationPlan",
        "transformation_engine": "TransformedDataset",
        "parser_pipeline": "ParsedDataset",
        "canonical_mapping": "CanonicalMapping",
        "quantity_resolution": "QuantityResolution",
        "canonical_dataset": "CanonicalDataset",
        "data_quality": "DataQualityReport",
        "aggregation": "AggregatedDataset",
        "validation": "ValidationDataset",
        "insights": "InsightsDataset",
        "reporting": "ReportDataset",
    }
    return mapping.get(name, "")


def _aggregated_rows(ctx: PipelineContext) -> int:
    if ctx.aggregated is None:
        return 0
    return sum(
        df.height for df in (
            ctx.aggregated.store, ctx.aggregated.item, ctx.aggregated.upc,
        ) if df is not None
    )


def _append_quality_errors(errors: List[str], ctx: PipelineContext) -> None:
    if ctx.quality is None:
        return
    for e in ctx.quality.errors:
        errors.append(f"Data quality: {e}")


def _suite_to_dict(suite: PipelineCertificationSuite) -> Dict[str, Any]:
    return {
        "suite": {
            "total": suite.total,
            "passed": suite.passed,
            "failed": suite.failed,
            "duration_seconds": round(suite.duration, 3),
        },
        "results": [
            {
                "category": r.category,
                "retailer": r.retailer,
                "scenarios": r.scenarios,
                "passed": r.passed,
                "duration_seconds": round(r.duration, 3),
                "stages": r.stages,
                "errors": r.errors,
                "details": r.details,
            }
            for r in suite.results
        ],
    }


def _report_markdown(suite: PipelineCertificationSuite) -> str:
    lines = [
        "# Pipeline Certification Suite",
        "",
        f"**Total:** {suite.total} | **Passed:** {suite.passed} | "
        f"**Failed:** {suite.failed} | **Duration:** {suite.duration:.2f}s",
        "",
        "| Category | Retailer | Scenarios | Status | Stages | Duration |",
        "|----------|----------|-----------|--------|--------|----------|",
    ]
    for r in suite.results:
        status = "✓" if r.passed else "✗"
        sc = ",".join(str(s) for s in r.scenarios) or "—"
        lines.append(
            f"| {r.category} | {r.retailer} | {sc} | {status} "
            f"| {len(r.stages)}/{len(REQUIRED_STAGES)} | {r.duration:.2f}s |"
        )
    lines.append("")
    failed = [r for r in suite.results if not r.passed]
    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.category}/{r.retailer}")
            for err in r.errors:
                lines.append(f"- {err}")
            lines.append("")
    return "\n".join(lines)

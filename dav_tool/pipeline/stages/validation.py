"""Validation Stage — AggregatedDataset → ValidationDataset.

Responsibility: run the enabled rules from the Rule Registry against the
AggregatedDataset and produce a ValidationDataset.  Validation never calls
Reporting.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

from dav_tool.validation.rules.registry import RuleRegistry, default_rule_registry
from dav_tool.validation.rules.tolerance import ToleranceRule

from ..contracts import (
    AggregatedDataset,
    RuleResult,
    ValidationDataset,
)
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class ValidationStage(BaseStage):
    """Executes validation rules and assembles a ValidationDataset."""

    name = "validation"
    label = "Validation"

    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
        enabled_rules: Optional[List[str]] = None,
        tolerance_pct: float = 5.0,
    ) -> None:
        super().__init__()
        self._registry = registry or default_rule_registry
        self._enabled = enabled_rules
        self._tolerance_pct = tolerance_pct

    def execute(self, ctx) -> StageResult:
        aggregated = ctx.aggregated
        if aggregated is None:
            raise FatalStageError(
                "Validation requires an AggregatedDataset (run Aggregation first).",
                user_message="No aggregated dataset available.",
            )

        t0 = time.perf_counter()
        results = self._registry.run_enabled(aggregated, enabled=self._enabled)
        store_diff = _extract_store_diff(results)
        results = _run_tolerance(self._registry, aggregated, store_diff, self._enabled, self._tolerance_pct, results)

        errors, warnings = _partition_results(results)
        validation = ValidationDataset(
            rule_results=tuple(results),
            store_difference=store_diff,
            item_difference=_find_data(results, "item_difference"),
            item_summary=_find_data(results, "upc_difference"),
            summaries=_build_summaries(aggregated),
            metadata=_build_metadata(ctx),
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

        elapsed = time.perf_counter() - t0
        ctx.metrics.record("validation", "validation_stage", elapsed)
        ctx.validation = validation
        return StageResult(stage=self.name)


def _extract_store_diff(results: List[RuleResult]) -> Optional[object]:
    for r in results:
        if r.rule == "store_difference" and r.data is not None:
            return r.data
    return None


def _run_tolerance(
    registry: RuleRegistry,
    aggregated: AggregatedDataset,
    store_diff,
    enabled: Optional[List[str]],
    tolerance_pct: float,
    results: List[RuleResult],
) -> List[RuleResult]:
    """Run the tolerance rule explicitly so it sees the store-diff frame."""
    if enabled is not None and "tolerance" not in enabled:
        return results
    if store_diff is None:
        return results
    rule = registry.get("tolerance")
    if rule is None:
        rule = ToleranceRule(tolerance_pct=tolerance_pct)
    try:
        result = rule.evaluate(aggregated, store_difference=store_diff)
        results.append(result)
    except Exception as exc:  # noqa: BLE001 — rule boundary
        logger.exception("Tolerance rule failed: %s", exc)
    return results


def _partition_results(results: List[RuleResult]):
    errors: List[str] = []
    warnings: List[str] = []
    for r in results:
        if not r.passed:
            msg = f"[{r.rule}] {r.message}"
            if r.rule in ("negative_sales",) or getattr(r, "severity", "warning") == "error":
                errors.append(msg)
            else:
                warnings.append(msg)
    return errors, warnings


def _find_data(results: List[RuleResult], rule: str):
    for r in results:
        if r.rule == rule and r.data is not None:
            return r.data
    return None


def _build_summaries(aggregated: AggregatedDataset) -> dict:
    """Carry forward aggregated summary frames for the Reporting Stage.

    Reporting reads these frames from the ValidationDataset contract only —
    it never touches Aggregation internals directly.
    """
    return {
        "level": aggregated.level,
        "store": aggregated.store,
        "item": aggregated.item,
        "upc": aggregated.upc,
        "prod_store": aggregated.prod_store,
        "prod_item": aggregated.prod_item,
        "test_store": aggregated.test_store,
        "test_item": aggregated.test_item,
    }


def _build_metadata(ctx) -> dict:
    """Report-oriented metadata consumed by the Reporting Stage."""
    metrics = ctx.metrics
    return {
        "pipeline": ctx.pipeline_name,
        "file_paths": list(ctx.file_paths or []),
        "file_type": getattr(ctx.discovery, "file_type", None),
        "delimiter": getattr(ctx.discovery, "delimiter", None),
        "warnings": list(ctx.warnings),
        "errors": list(ctx.errors),
        "completed_stages": list(ctx.completed_stages),
        "metrics_snapshot": {
            "rows_processed": getattr(metrics, "rows_processed", 0),
            "total_execution_time": getattr(metrics, "total_execution_time", 0.0),
            "peak_memory": getattr(metrics, "peak_memory", 0.0),
            "peak_cpu": getattr(metrics, "peak_cpu", 0.0),
            "files_processed": getattr(metrics, "files_processed", 0),
        },
    }

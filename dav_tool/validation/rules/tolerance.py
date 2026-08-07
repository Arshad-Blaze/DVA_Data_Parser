"""Tolerance and custom rules.

Tolerance: threshold-based variance checks over the store-diff frame.
Custom: callable-based rules supplied at configuration time.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

import polars as pl

from dav_tool.pipeline.contracts import AggregatedDataset, RuleResult

from .registry import ValidationRule

logger = logging.getLogger(__name__)


class ToleranceRule(ValidationRule):
    """Flag stores/items whose variance exceeds a configured tolerance."""

    name = "tolerance"
    description = "Flag variance beyond the configured tolerance threshold."
    severity = "warning"

    def __init__(
        self,
        tolerance_pct: float = 5.0,
        columns: Optional[list] = None,
    ) -> None:
        super().__init__()
        self.tolerance_pct = tolerance_pct
        self.columns = columns or ["Units_Diff_%", "Sales_Diff_%"]

    def supports(self, dataset: AggregatedDataset) -> bool:
        return dataset.prod_store is not None and dataset.test_store is not None

    def evaluate(self, dataset: AggregatedDataset, store_difference=None, **kwargs) -> RuleResult:
        diff = store_difference
        if diff is None:
            return RuleResult(rule=self.name, passed=True)
        applicable = [c for c in self.columns if c in diff.columns]
        if not applicable:
            return RuleResult(rule=self.name, passed=True)

        over = diff.filter(
            pl.max_horizontal(
                *[pl.col(c).abs().fill_null(0.0) for c in applicable]
            )
            > self.tolerance_pct
        )
        if over.is_empty():
            return RuleResult(
                rule=self.name, passed=True,
                data=diff.select(["STORE_NUMBER", *applicable]),
            )
        return RuleResult(
            rule=self.name,
            passed=False,
            message=f"{over.height} store(s) exceed the {self.tolerance_pct}% tolerance.",
            data=over.select(["STORE_NUMBER", *applicable]),
        )


class CustomRule(ValidationRule):
    """User-supplied rule — a callable over an AggregatedDataset.

    The callable signature is ``fn(dataset) -> RuleResult``.
    """

    name = "custom"
    description = "Custom validation rule supplied at runtime."
    severity = "warning"

    def __init__(
        self,
        rule_name: str,
        fn: Callable[[AggregatedDataset], RuleResult],
        description: str = "",
        severity: str = "warning",
    ) -> None:
        super().__init__()
        self.rule_name = rule_name
        self._fn = fn
        self.description = description or self.description
        self.severity = severity

    @property
    def name(self) -> str:  # type: ignore[override]
        return self.rule_name

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        return self._fn(dataset)

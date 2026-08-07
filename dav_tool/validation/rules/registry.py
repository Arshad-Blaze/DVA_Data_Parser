"""Rule Registry — rule-driven validation.

Replaces the hard-coded validation dispatch with a registry of validation
rules.  Validation receives an AggregatedDataset, executes the enabled
rules, and produces a ValidationDataset.  Validation never calls Reporting.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import polars as pl

from dav_tool.pipeline.contracts import AggregatedDataset, RuleResult

logger = logging.getLogger(__name__)


class ValidationRule(ABC):
    """Base class for a validation rule.

    Subclasses implement :meth:`name`, :meth:`description`, and
    :meth:`evaluate`, returning a :class:`RuleResult`.
    """

    name: str = "base_rule"
    description: str = ""
    severity: str = "warning"  # "warning" | "error"

    @abstractmethod
    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        """Evaluate the rule against an AggregatedDataset."""
        raise NotImplementedError

    def supports(self, dataset: AggregatedDataset) -> bool:
        """Return True if this rule can evaluate the given dataset."""
        return True


class RuleRegistry:
    """Registry mapping rule names to rule instances."""

    def __init__(self) -> None:
        self._rules: Dict[str, ValidationRule] = {}

    def register(self, rule: ValidationRule) -> ValidationRule:
        if not rule.name:
            raise ValueError(f"Rule class {type(rule).__name__} has no name")
        self._rules[rule.name] = rule
        return rule

    def get(self, name: str) -> Optional[ValidationRule]:
        return self._rules.get(name)

    def names(self) -> List[str]:
        return sorted(self._rules.keys())

    def run(
        self,
        name: str,
        dataset: AggregatedDataset,
        **kwargs,
    ) -> Optional[RuleResult]:
        rule = self._rules.get(name)
        if rule is None:
            return None
        return rule.evaluate(dataset, **kwargs)

    def run_enabled(
        self,
        dataset: AggregatedDataset,
        enabled: Optional[List[str]] = None,
        **kwargs,
    ) -> List[RuleResult]:
        """Run every enabled rule and collect results.

        ``enabled`` defaults to all registered rules whose ``supports()``
        returns True for the dataset.
        """
        results: List[RuleResult] = []
        for name in self.names():
            rule = self._rules[name]
            if enabled is not None and name not in enabled:
                continue
            if not rule.supports(dataset):
                continue
            try:
                results.append(rule.evaluate(dataset, **kwargs))
            except Exception as exc:  # noqa: BLE001 — rule boundary
                logger.exception("Rule '%s' failed: %s", name, exc)
                results.append(
                    RuleResult(
                        rule=name,
                        passed=False,
                        message=f"Rule execution error: {exc}",
                    )
                )
        return results


#: Module-level shared registry (populated by bootstrap).
default_rule_registry = RuleRegistry()

"""Store / Item / UPC difference rules.

Compare the BAU (prod) and TEST (test) aggregations using the Calculation
Engine.  These rules produce the canonical store-diff and item-comparison
frames consumed by Reporting.
"""
from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from dav_tool.calculations import item_comparison, item_summary, store_diffs
from dav_tool.pipeline.contracts import AggregatedDataset, RuleResult

from .registry import ValidationRule

logger = logging.getLogger(__name__)


class StoreDifferenceRule(ValidationRule):
    """Compare BAU vs TEST store-level Units/Sales."""

    name = "store_difference"
    description = "Store-level Units/Sales difference between BAU and TEST."
    severity = "warning"

    def supports(self, dataset: AggregatedDataset) -> bool:
        return dataset.prod_store is not None and dataset.test_store is not None

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        prod = dataset.prod_store
        test = dataset.test_store
        if prod is None or test is None:
            return RuleResult(
                rule=self.name,
                passed=False,
                message="Store difference requires BAU and TEST store summaries.",
            )
        try:
            diff = store_diffs(prod, test)
        except Exception as exc:
            return RuleResult(rule=self.name, passed=False, message=f"Store diff failed: {exc}")
        return RuleResult(rule=self.name, passed=True, data=diff)


class ItemDifferenceRule(ValidationRule):
    """Compare BAU vs TEST UPC-level presence and sales."""

    name = "item_difference"
    description = "UPC-level presence and units/dollar comparison between BAU and TEST."
    severity = "warning"

    def supports(self, dataset: AggregatedDataset) -> bool:
        return dataset.prod_item is not None and dataset.test_item is not None

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        prod = dataset.prod_item
        test = dataset.test_item
        if prod is None or test is None:
            return RuleResult(
                rule=self.name,
                passed=False,
                message="Item difference requires BAU and TEST item summaries.",
            )
        try:
            comparison = item_comparison(prod, test)
        except Exception as exc:
            return RuleResult(rule=self.name, passed=False, message=f"Item comparison failed: {exc}")
        return RuleResult(rule=self.name, passed=True, data=comparison)


class UPCDifferenceRule(ValidationRule):
    """UPC summary presence + difference summary (aggregate of item comparison)."""

    name = "upc_difference"
    description = "UPC-level summary of the item comparison (presence counts, growth)."
    severity = "warning"

    def supports(self, dataset: AggregatedDataset) -> bool:
        return dataset.prod_item is not None and dataset.test_item is not None

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        prod = dataset.prod_item
        test = dataset.test_item
        if prod is None or test is None:
            return RuleResult(
                rule=self.name,
                passed=False,
                message="UPC difference requires BAU and TEST item summaries.",
            )
        comparison = item_comparison(prod, test)
        summary = item_summary(comparison)
        return RuleResult(rule=self.name, passed=True, data=summary)

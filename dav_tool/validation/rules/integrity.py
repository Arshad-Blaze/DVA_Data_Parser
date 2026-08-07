"""Integrity rules — duplicate UPC, missing store/UPC, negative sales, weight.

These rules operate on a single-side AggregatedDataset (canonical summaries)
and validate data integrity.  No parsing, no aggregation, no reporting.
"""
from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from dav_tool.pipeline.contracts import AggregatedDataset, RuleResult

from .registry import ValidationRule

logger = logging.getLogger(__name__)


class DuplicateUPCRule(ValidationRule):
    """Detect duplicate UPCs within an item-level aggregation."""

    name = "duplicate_upc"
    description = "Detect duplicate UPC codes in the item summary."
    severity = "warning"

    def supports(self, dataset: AggregatedDataset) -> bool:
        df = dataset.item if dataset.item is not None else dataset.upc
        return df is not None and "UPC_CODE" in df.columns

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        df = dataset.item if dataset.item is not None else dataset.upc
        if df is None or df.is_empty():
            return RuleResult(rule=self.name, passed=True)
        upc_col = "UPC_CODE" if "UPC_CODE" in df.columns else "UPC"
        counts = df.group_by(upc_col).agg(pl.len().alias("count"))
        dupes = counts.filter(pl.col("count") > 1)
        if dupes.is_empty():
            return RuleResult(
                rule=self.name,
                passed=True,
                data=pl.DataFrame({upc_col: [], "count": []}),
            )
        return RuleResult(
            rule=self.name,
            passed=False,
            message=f"{dupes.height} duplicate UPC(s) detected.",
            data=dupes,
        )


class MissingStoreRule(ValidationRule):
    """Detect missing store numbers in a store-level aggregation."""

    name = "missing_store"
    description = "Detect missing/null store numbers."
    severity = "warning"

    def supports(self, dataset: AggregatedDataset) -> bool:
        return dataset.store is not None and "STORE_NUMBER" in dataset.store.columns

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        df = dataset.store
        if df is None or df.is_empty():
            return RuleResult(rule=self.name, passed=True)
        missing = df.filter(
            pl.col("STORE_NUMBER").is_null()
            | (pl.col("STORE_NUMBER").cast(pl.Utf8).str.strip_chars() == "")
        )
        if missing.is_empty():
            return RuleResult(
                rule=self.name, passed=True,
                data=pl.DataFrame({"STORE_NUMBER": []}),
            )
        return RuleResult(
            rule=self.name,
            passed=False,
            message=f"{missing.height} store(s) have a missing store number.",
            data=missing.select("STORE_NUMBER"),
        )


class MissingUPCRule(ValidationRule):
    """Detect missing/null UPC codes in an item-level aggregation."""

    name = "missing_upc"
    description = "Detect missing/null UPC codes."
    severity = "warning"

    def supports(self, dataset: AggregatedDataset) -> bool:
        df = dataset.item if dataset.item is not None else dataset.upc
        return df is not None

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        df = dataset.item if dataset.item is not None else dataset.upc
        if df is None or df.is_empty():
            return RuleResult(rule=self.name, passed=True)
        upc_col = "UPC_CODE" if "UPC_CODE" in df.columns else "UPC"
        missing = df.filter(
            pl.col(upc_col).is_null()
            | (pl.col(upc_col).cast(pl.Utf8).str.strip_chars() == "")
        )
        if missing.is_empty():
            return RuleResult(
                rule=self.name, passed=True,
                data=pl.DataFrame({upc_col: []}),
            )
        return RuleResult(
            rule=self.name,
            passed=False,
            message=f"{missing.height} row(s) have a missing UPC.",
            data=missing.select(upc_col),
        )


class NegativeSalesRule(ValidationRule):
    """Detect negative units or dollar values in the aggregated data."""

    name = "negative_sales"
    description = "Detect negative units or dollar values."
    severity = "error"

    def supports(self, dataset: AggregatedDataset) -> bool:
        for df in (dataset.store, dataset.item, dataset.upc):
            if df is not None and not df.is_empty():
                return True
        return False

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        frames: list = []
        for df, label in (
            (dataset.store, "store"),
            (dataset.item, "item"),
            (dataset.upc, "upc"),
        ):
            if df is None or df.is_empty():
                continue
            negative = _negative_rows(df)
            if negative is not None and not negative.is_empty():
                frames.append(negative)
        if not frames:
            return RuleResult(rule=self.name, passed=True)
        combined = pl.concat(frames)
        return RuleResult(
            rule=self.name,
            passed=False,
            message=f"{combined.height} row(s) contain negative values.",
            data=combined,
        )


def _negative_rows(df: pl.DataFrame) -> Optional[pl.DataFrame]:
    exprs = []
    if "UNITS_SOLD" in df.columns:
        exprs.append(pl.col("UNITS_SOLD") < 0)
    elif "Units" in df.columns:
        exprs.append(pl.col("Units") < 0)
    if "TOTAL_DOLLARS" in df.columns:
        exprs.append(pl.col("TOTAL_DOLLARS") < 0)
    elif "Totalprice" in df.columns:
        exprs.append(pl.col("Totalprice") < 0)
    if not exprs:
        return None
    return df.filter(exprs[0] | exprs[1] if len(exprs) > 1 else exprs[0])


class WeightValidationRule(ValidationRule):
    """Validate that weight values are positive and within a sane range."""

    name = "weight_validation"
    description = "Validate weight values (positive, non-extreme)."
    severity = "warning"

    #: Reject weights above this threshold (lbs).
    max_weight_lb: float = 5000.0

    def supports(self, dataset: AggregatedDataset) -> bool:
        df = dataset.item if dataset.item is not None else dataset.upc
        return df is not None and any(
            c in df.columns for c in ("Weight", "WEIGHT", "weight")
        )

    def evaluate(self, dataset: AggregatedDataset, **kwargs) -> RuleResult:
        df = dataset.item if dataset.item is not None else dataset.upc
        if df is None:
            return RuleResult(rule=self.name, passed=True)
        weight_col = next(
            (c for c in ("Weight", "WEIGHT", "weight") if c in df.columns), None
        )
        if weight_col is None:
            return RuleResult(rule=self.name, passed=True)
        bad = df.filter(
            pl.col(weight_col).is_null()
            | (pl.col(weight_col) <= 0)
            | (pl.col(weight_col) > self.max_weight_lb)
        )
        if bad.is_empty():
            return RuleResult(
                rule=self.name, passed=True,
                data=pl.DataFrame({weight_col: []}),
            )
        return RuleResult(
            rule=self.name,
            passed=False,
            message=f"{bad.height} row(s) have invalid weight values.",
            data=bad.select(weight_col),
        )

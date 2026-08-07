"""Data Quality Stage — CanonicalDataset → DataQualityReport.

Responsibility: inspect the canonical dataset BEFORE aggregation and record
data-quality findings — duplicate keys, missing mandatory columns, missing
UPC/store, invalid dates, invalid quantities, negative sales, invalid UOM,
corrupted records, malformed rows, unsupported encodings and unexpected nulls.

Pure quality assurance: produces a :class:`DataQualityReport` and never
modifies data.  The pipeline proceeds to aggregation regardless; rejection is
a configurable policy, never a silent ``except``.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import polars as pl

from dav_tool.workflow.canonical import CanonicalDataset

from ..contracts import DataQualityCheck, DataQualityReport
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)

#: mandatory canonical columns per aggregation level
_REQUIRED_BY_LEVEL = {
    "store": ("STORE_NUMBER", "Units", "Totalprice"),
    "item": ("UPC_CODE", "PRODUCT_DESCRIPTION", "UNITS_SOLD", "TOTAL_DOLLARS"),
    "upc": ("UPC", "UNITS_SOLD", "TOTAL_DOLLARS"),
}

#: canonical key column(s) used for duplicate detection per level
_KEY_BY_LEVEL = {
    "store": ("STORE_NUMBER",),
    "item": ("UPC_CODE",),
    "upc": ("UPC",),
}

#: known weight/quantity units
KNOWN_UOMS = {
    "lb", "lbs", "pound", "pounds", "oz", "ounce", "ounces",
    "kg", "kilogram", "kilograms", "g", "gram", "grams",
    "each", "unit", "units", "ea", "pk", "pack", "ct", "count",
}

DEFAULT_SAMPLE_ROWS = 50_000

_VALID_QUANTITY_SOURCES = ("weight", "units", "none")


class DataQualityStage(BaseStage):
    """Runs quality checks on the canonical dataset pre-aggregation."""

    name = "data_quality"
    label = "Data Quality"

    def execute(self, ctx) -> StageResult:
        canonical: Optional[CanonicalDataset] = ctx.canonical
        if canonical is None:
            raise FatalStageError(
                "Data Quality requires a CanonicalDataset (run Canonical Dataset first).",
                user_message="No canonical dataset available.",
            )

        t0 = time.perf_counter()
        sample_rows = int(
            (ctx.user_config or {}).get("quality_sample_rows", DEFAULT_SAMPLE_ROWS)
        )
        report = build_quality_report(
            canonical,
            sample_rows=sample_rows,
            discovery=ctx.discovery,
            parsed_metadata=(ctx.parsed.metadata if ctx.parsed is not None else None),
        )
        elapsed = time.perf_counter() - t0
        report = DataQualityReport(
            checks=report.checks,
            warnings=report.warnings,
            errors=report.errors,
            rejected=bool((ctx.user_config or {}).get("reject_on_quality_errors"))
            and bool(report.errors),
            row_count=report.row_count,
            metadata={
                **report.metadata,
                "elapsed_seconds": round(elapsed, 4),
            },
        )
        ctx.metrics.record("quality", "data_quality_stage", elapsed)
        ctx.quality = report
        return StageResult(stage=self.name)


def build_quality_report(
    canonical: CanonicalDataset,
    sample_rows: int = DEFAULT_SAMPLE_ROWS,
    discovery: Any = None,
    parsed_metadata: Optional[Dict[str, Any]] = None,
) -> DataQualityReport:
    """Run quality checks over a sampled canonical stream."""
    checks: List[DataQualityCheck] = []
    warnings: List[str] = []
    errors: List[str] = []

    sample, inspected = _sample(canonical, sample_rows)
    checks.append(
        DataQualityCheck(
            check="row_inspection",
            passed=True,
            count=inspected,
            details=(f"inspected up to {sample_rows} rows",),
        )
    )

    columns: List[str] = list(sample.columns) if sample is not None else []
    if sample is not None and not sample.is_empty():
        checks.append(_check_required_columns(canonical, columns, errors))
        keys = _KEY_BY_LEVEL.get(canonical.level, ())
        checks.append(_check_duplicate_keys(sample, keys, warnings))
        checks.append(_check_missing_keys(sample, keys, warnings))
        checks.append(_check_quantity_values(sample, warnings))
        checks.append(_check_dollar_values(sample, warnings))
        checks.append(_check_date_values(sample, warnings))
        checks.append(_check_uom_values(sample, warnings))
        checks.append(_check_upc_format(sample, warnings))
        checks.append(_check_quantity_source(sample, warnings))
        checks.append(_check_nulls(sample, canonical.level, warnings))
    else:
        msg = "no canonical rows produced (empty dataset)"
        errors.append(msg)
        logger.error("Data quality [%s]: %s", canonical.level, msg)
        checks.append(DataQualityCheck(check="required_columns", passed=False,
                                       details=(msg,)))

    checks.append(_check_record_structure(
        parsed_metadata, discovery, warnings, errors,
    ))

    return DataQualityReport(
        checks=tuple(checks),
        warnings=tuple(warnings),
        errors=tuple(errors),
        rejected=False,
        row_count=inspected,
        metadata={
            "level": canonical.level,
            "schema": list(canonical.schema),
        },
    )


def _sample(canonical: CanonicalDataset, sample_rows: int) -> tuple:
    """Collect up to *sample_rows* rows from the canonical stream."""
    inspected = 0
    seen: Optional[pl.DataFrame] = None
    for chunk in canonical.iter_chunks():
        if chunk is None or chunk.is_empty():
            continue
        remaining = sample_rows - inspected
        if remaining <= 0:
            break
        piece = chunk.head(remaining)
        seen = piece if seen is None else pl.concat([seen, piece])
        inspected += piece.height
    return seen, inspected


def _check_required_columns(
    canonical: CanonicalDataset,
    columns: List[str],
    errors: List[str],
) -> DataQualityCheck:
    required = _REQUIRED_BY_LEVEL.get(canonical.level, ())
    missing = [c for c in required if c not in columns]
    if missing:
        msg = f"missing mandatory canonical column(s): {', '.join(missing)}"
        errors.append(msg)
        logger.error("Data quality [%s]: %s", canonical.level, msg)
        return DataQualityCheck(check="required_columns", passed=False,
                                details=(msg,))
    return DataQualityCheck(check="required_columns", passed=True,
                            count=len(required))


def _check_duplicate_keys(
    sample: pl.DataFrame,
    keys: tuple,
    warnings: List[str],
) -> DataQualityCheck:
    present = [k for k in keys if k in sample.columns]
    if not present:
        return DataQualityCheck(check="duplicate_keys", passed=True)
    dup = sample.select(present).is_duplicated()
    bad = int(dup.sum())
    details = ()
    if bad:
        detail = f"duplicate key(s) {present}: {bad} row(s)"
        warnings.append(detail)
        logger.warning("Data quality: %s", detail)
        details = (detail,)
    return DataQualityCheck(check="duplicate_keys", passed=bad == 0,
                            count=bad, details=details)


def _check_missing_keys(
    sample: pl.DataFrame,
    keys: tuple,
    warnings: List[str],
) -> DataQualityCheck:
    bad = 0
    details: List[str] = []
    for key in keys:
        if key not in sample.columns:
            continue
        nulls = int(sample[key].is_null().sum())
        if nulls:
            bad += nulls
            details.append(f"{key}: {nulls} missing value(s)")
    if details:
        warnings.append("missing keys: " + "; ".join(details[:4]))
        logger.warning("Data quality: %s", warnings[-1])
    return DataQualityCheck(check="missing_keys", passed=bad == 0,
                            count=bad, details=tuple(details))


def _numeric_columns(columns: List[str], defaults: List[str]) -> List[str]:
    return [c for c in defaults if c in columns]


def _check_quantity_values(sample: pl.DataFrame, warnings: List[str]) -> DataQualityCheck:
    bad = 0
    details: List[str] = []
    for col in _numeric_columns(list(sample.columns), ("UNITS_SOLD", "Units", "ResolvedQuantity")):
        vals = sample[col]
        if vals.null_count():
            details.append(f"{col}: {vals.null_count()} nulls")
        if vals.dtype in (pl.Float64, pl.Int64, pl.Float32, pl.Int32):
            negative = (vals < 0).sum()
            if negative:
                bad += int(negative)
                details.append(f"{col}: {negative} negative value(s)")
    if details:
        warnings.append("quantity values: " + "; ".join(details[:4]))
        logger.warning("Data quality: %s", warnings[-1])
    return DataQualityCheck(check="invalid_quantity", passed=bad == 0,
                            count=bad, details=tuple(details))


def _check_dollar_values(sample: pl.DataFrame, warnings: List[str]) -> DataQualityCheck:
    bad = 0
    details: List[str] = []
    for col in _numeric_columns(list(sample.columns), ("TOTAL_DOLLARS", "Totalprice")):
        vals = sample[col]
        if vals.null_count():
            details.append(f"{col}: {vals.null_count()} nulls")
        if vals.dtype in (pl.Float64, pl.Int64, pl.Float32, pl.Int32):
            negative = (vals < 0).sum()
            if negative:
                bad += int(negative)
                details.append(f"{col}: {negative} negative value(s)")
    if details:
        warnings.append("dollar values: " + "; ".join(details[:4]))
        logger.warning("Data quality: %s", warnings[-1])
    return DataQualityCheck(check="negative_sales", passed=bad == 0,
                            count=bad, details=tuple(details))


def _check_date_values(sample: pl.DataFrame, warnings: List[str]) -> DataQualityCheck:
    col = "TRANSACTION_DATE"
    if col not in sample.columns:
        return DataQualityCheck(check="invalid_dates", passed=True)
    vals = sample[col].cast(pl.String).str.strip_chars()
    valid = vals.str.to_datetime(strict=False).is_not_null()
    bad = int((~valid & ~vals.is_null() & (vals != "")).sum())
    details = ()
    if bad:
        detail = f"TRANSACTION_DATE: {bad} invalid date value(s)"
        warnings.append(detail)
        logger.warning("Data quality: %s", detail)
        details = (detail,)
    return DataQualityCheck(check="invalid_dates", passed=bad == 0,
                            count=bad, details=details)


def _check_uom_values(sample: pl.DataFrame, warnings: List[str]) -> DataQualityCheck:
    col = "WeightUOM" if "WeightUOM" in sample.columns else (
        "WEIGHT_UOM" if "WEIGHT_UOM" in sample.columns else None
    )
    if col is None:
        return DataQualityCheck(check="invalid_uom", passed=True)
    vals = sample[col].cast(pl.String).str.strip_chars().str.to_lowercase()
    bad = int((~vals.is_in(_normalize_uoms()) & ~vals.is_null() & (vals != "")).sum())
    details = ()
    if bad:
        detail = f"{col}: {bad} unknown UOM value(s)"
        warnings.append(detail)
        logger.warning("Data quality: %s", detail)
        details = (detail,)
    return DataQualityCheck(check="invalid_uom", passed=bad == 0,
                            count=bad, details=details)


def _normalize_uoms() -> List[str]:
    out = set(KNOWN_UOMS)
    for uom in list(KNOWN_UOMS):
        out.add(uom.upper())
    return sorted(out)


def _check_upc_format(sample: pl.DataFrame, warnings: List[str]) -> DataQualityCheck:
    col = "UPC_CODE" if "UPC_CODE" in sample.columns else (
        "UPC" if "UPC" in sample.columns else None
    )
    if col is None:
        return DataQualityCheck(check="upc_format", passed=True)
    vals = sample[col].cast(pl.String)
    digits = vals.str.replace_all(r"\D", "")
    valid_mask = digits.str.len_chars().is_in([8, 12, 13, 14])
    bad = int((~valid_mask & ~vals.is_null() & (vals != "")).sum())
    details = ()
    if bad:
        detail = f"{col}: {bad} malformed UPC value(s)"
        warnings.append(detail)
        logger.warning("Data quality: %s", detail)
        details = (detail,)
    return DataQualityCheck(check="missing_upc", passed=bad == 0,
                            count=bad, details=details)


def _check_quantity_source(sample: pl.DataFrame, warnings: List[str]) -> DataQualityCheck:
    if "QuantitySource" not in sample.columns:
        return DataQualityCheck(check="quantity_source", passed=True)
    vals = sample["QuantitySource"].cast(pl.String).str.strip_chars()
    bad = int((~vals.is_in(_VALID_QUANTITY_SOURCES)).sum())
    details = ()
    if bad:
        detail = f"QuantitySource: {bad} unexpected value(s)"
        warnings.append(detail)
        logger.warning("Data quality: %s", detail)
        details = (detail,)
    return DataQualityCheck(check="quantity_source", passed=bad == 0,
                            count=bad, details=details)


def _check_nulls(
    sample: pl.DataFrame,
    level: str,
    warnings: List[str],
) -> DataQualityCheck:
    """Flag unexpected nulls in canonical output columns only."""
    bad = 0
    details: List[str] = []
    target = _REQUIRED_BY_LEVEL.get(level, ()) + (
        "STORE_NUMBER", "UPC_CODE", "UNITS_SOLD", "TOTAL_DOLLARS",
    )
    for col in target:
        if col not in sample.columns:
            continue
        nulls = int(sample[col].is_null().sum())
        if nulls and nulls / max(sample.height, 1) > 0.05:
            bad += nulls
            details.append(f"{col}: {nulls} nulls")
    if details:
        warnings.append("unexpected nulls: " + "; ".join(details[:4]))
        logger.warning("Data quality: %s", warnings[-1])
    return DataQualityCheck(check="unexpected_nulls", passed=bad == 0,
                            count=bad, details=tuple(details))


def _check_record_structure(
    parsed_metadata: Optional[Dict[str, Any]],
    discovery: Any,
    warnings: List[str],
    errors: List[str],
) -> DataQualityCheck:
    """Report malformed/corrupted/encoding findings carried from parsing."""
    notes: List[str] = []
    if parsed_metadata:
        for key in ("warnings", "encoding_warnings", "malformed_rows"):
            value = parsed_metadata.get(key)
            if value:
                notes.append(f"{key}: {value}")
    if discovery is not None:
        disc_warnings = getattr(discovery, "warnings", None) or []
        for w in list(disc_warnings)[:3]:
            notes.append(f"discovery: {w}")
    if notes:
        warnings.append("record structure: " + "; ".join(notes[:4]))
        logger.warning("Data quality: %s", warnings[-1])
    return DataQualityCheck(
        check="record_structure",
        passed=True,
        count=len(notes),
        details=tuple(notes),
    )

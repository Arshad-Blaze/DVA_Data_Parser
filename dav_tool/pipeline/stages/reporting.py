"""Reporting Stage — ValidationDataset + InsightsDataset → ReportDataset.

Responsibility: render a ValidationDataset into downloadable CSV artifacts and
an InsightsDataset into summary analytics (KPIs) and worksheets.  Reporting
consumes ONLY the ValidationDataset and InsightsDataset contracts — it never
receives store/item aggregation objects, parser objects, or a CanonicalDataset.
Reporting performs no aggregation, no parsing, and no metric calculation; it
only formats frames produced upstream.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import polars as pl

from dav_tool._reports import generate_summary_analytics
from dav_tool.pipeline.contracts import (
    DownloadArtifact,
    InsightsDataset,
    ReportDataset,
    ValidationDataset,
)
from dav_tool.pipeline.stage import BaseStage, StageResult

logger = logging.getLogger(__name__)


class ReportingStage(BaseStage):
    """Renders the ValidationDataset + InsightsDataset into a ReportDataset."""

    name = "reporting"
    label = "Reporting"

    def execute(self, ctx) -> StageResult:
        validation = ctx.validation
        if validation is None:
            raise RuntimeError(
                "Reporting requires a ValidationDataset (run Validation first)."
            )

        t0 = time.perf_counter()
        artifacts = _build_artifacts(validation)
        insights = ctx.insights
        if insights is not None:
            kpis = insights.kpis
            sheets = dict(insights.frames)
        else:
            # Backward-compatible fallback: derive from the ValidationDataset.
            kpis = _build_kpis(validation)
            sheets = _build_sheets(validation)

        ctx.report = ReportDataset(
            artifacts=tuple(artifacts),
            summary_kpis=kpis,
            summary_sheets=sheets,
            metrics=_metrics_snapshot(ctx),
        )
        elapsed = time.perf_counter() - t0
        ctx.metrics.record("report", "reporting_stage", elapsed)
        return StageResult(stage=self.name)


def _build_artifacts(validation: ValidationDataset) -> List[DownloadArtifact]:
    artifacts: List[DownloadArtifact] = []

    store_diff = validation.store_difference
    if store_diff is not None and not store_diff.is_empty():
        artifacts.append(
            DownloadArtifact(
                filename="store_difference.csv",
                label="Store Difference",
                data=store_diff.write_csv(),
            )
        )

    item_diff = validation.item_difference
    if item_diff is not None and not item_diff.is_empty():
        artifacts.append(
            DownloadArtifact(
                filename="item_difference.csv",
                label="Item Difference",
                data=item_diff.write_csv(),
            )
        )

    item_summary = validation.item_summary
    if item_summary is not None and not item_summary.is_empty():
        artifacts.append(
            DownloadArtifact(
                filename="item_summary.csv",
                label="Item Summary",
                data=item_summary.write_csv(),
            )
        )

    upc_summary = validation.summaries.get("upc")
    if upc_summary is None:
        upc_summary = validation.summaries.get("item")
    if upc_summary is not None and not upc_summary.is_empty():
        artifacts.append(
            DownloadArtifact(
                filename="upc_summary.csv",
                label="UPC Summary",
                data=upc_summary.write_csv(),
            )
        )

    store_list = validation.store_list_result
    if store_list:
        rows = pl.DataFrame(
            [
                {"store": s, "status": "missing_in_test"}
                for s in _split_list(store_list.get("missing_in_test", ""))
            ]
            + [
                {"store": s, "status": "missing_in_prod"}
                for s in _split_list(store_list.get("missing_in_prod", ""))
            ]
        )
        if rows.is_empty():
            rows = pl.DataFrame({"store": [], "status": []})
        artifacts.append(
            DownloadArtifact(
                filename="store_list_compare.csv",
                label="Store List Compare",
                data=rows.write_csv(),
            )
        )

    return artifacts


def _build_kpis(validation: ValidationDataset) -> Optional[pl.DataFrame]:
    """Build the summary analytics KPIs from validation summaries only."""
    summaries = validation.summaries
    prod_store = summaries.get("prod_store")
    if prod_store is None:
        prod_store = summaries.get("store")
    test_store = summaries.get("test_store")
    prod_upc = summaries.get("prod_item")
    if prod_upc is None:
        prod_upc = summaries.get("item")
    test_upc = summaries.get("test_item")

    if prod_store is None and prod_upc is None:
        return None

    kpis = generate_summary_analytics(
        prod_store_agg=prod_store,
        test_store_agg=test_store,
        prod_upc_summary=prod_upc,
        test_upc_summary=test_upc,
        prod_item_comparison=validation.item_difference,
        store_diff=validation.store_difference,
        execution_metrics=validation.metadata.get("metrics_snapshot"),
        prod_label=validation.metadata.get("prod_label", "BAU"),
        test_label=validation.metadata.get("test_label", "TEST"),
    )
    return kpis if not kpis.is_empty() else None


def _build_sheets(validation: ValidationDataset) -> Dict[str, pl.DataFrame]:
    """Build named summary worksheets from validation data only."""
    sheets: Dict[str, pl.DataFrame] = {}

    summaries = validation.summaries
    store_summary = summaries.get("prod_store")
    if store_summary is None:
        store_summary = summaries.get("store")
    upc_summary = summaries.get("prod_item")
    if upc_summary is None:
        upc_summary = summaries.get("item")

    if store_summary is not None and not store_summary.is_empty():
        if "Units" in store_summary.columns and "Totalprice" in store_summary.columns:
            sf = store_summary.filter(pl.col("Units").is_not_null())
            try:
                sheets["top_stores"] = pl.concat([
                    sf.top_k(10, by="Totalprice").with_columns(pl.lit("Sales").alias("rank_by")),
                    sf.top_k(10, by="Units").with_columns(pl.lit("Quantity").alias("rank_by")),
                ])
                sheets["bottom_stores"] = pl.concat([
                    sf.bottom_k(10, by="Totalprice").with_columns(pl.lit("Sales").alias("rank_by")),
                    sf.bottom_k(10, by="Units").with_columns(pl.lit("Quantity").alias("rank_by")),
                ])
            except Exception as exc:  # noqa: BLE001 — report generation must not fail
                logger.warning("Could not build store ranking sheets: %s", exc)

    if upc_summary is not None and not upc_summary.is_empty():
        if "TOTAL_DOLLARS" in upc_summary.columns:
            try:
                sheets["top_upcs"] = upc_summary.top_k(10, by="TOTAL_DOLLARS").with_columns(
                    pl.lit("Top").alias("rank")
                )
                sheets["bottom_upcs"] = upc_summary.bottom_k(10, by="TOTAL_DOLLARS").with_columns(
                    pl.lit("Bottom").alias("rank")
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build UPC ranking sheets: %s", exc)
        if "UNITS_SOLD" in upc_summary.columns:
            try:
                sheets["top_upcs_by_qty"] = upc_summary.top_k(10, by="UNITS_SOLD").with_columns(
                    pl.lit("Top Qty").alias("rank")
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build UPC qty sheet: %s", exc)

    return sheets


def _split_list(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _metrics_snapshot(ctx) -> dict:
    metrics = ctx.metrics
    return {
        "rows_processed": getattr(metrics, "rows_processed", 0),
        "total_execution_time": getattr(metrics, "total_execution_time", 0.0),
        "peak_memory": getattr(metrics, "peak_memory", 0.0),
        "peak_cpu": getattr(metrics, "peak_cpu", 0.0),
        "files_processed": getattr(metrics, "files_processed", 0),
    }

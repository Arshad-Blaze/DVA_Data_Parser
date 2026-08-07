"""Insights Engine Stage — AggregatedDataset → InsightsDataset.

Responsibility: compute business insights (KPIs, top/bottom rankings) from
the AggregatedDataset and ValidationDataset.  Consumed exclusively by the
Reporting Stage, which only formats these frames and never recomputes metrics.

The Insights Engine performs no parsing and no file access.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import polars as pl

from dav_tool._reports import generate_summary_analytics

from ..contracts import AggregatedDataset, InsightsDataset, ValidationDataset
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class InsightsEngineStage(BaseStage):
    """Produces the InsightsDataset consumed by Reporting."""

    name = "insights"
    label = "Insights Engine"

    def execute(self, ctx) -> StageResult:
        aggregated: Optional[AggregatedDataset] = ctx.aggregated
        if aggregated is None:
            raise FatalStageError(
                "Insights Engine requires an AggregatedDataset (run Aggregation first).",
                user_message="No aggregated dataset available.",
            )

        t0 = time.perf_counter()
        insights = build_insights(aggregated, ctx.validation)
        elapsed = time.perf_counter() - t0
        ctx.metrics.record("insights", "insights_engine_stage", elapsed)
        ctx.insights = insights
        return StageResult(stage=self.name)


def build_insights(
    aggregated: AggregatedDataset,
    validation: Optional[ValidationDataset] = None,
) -> InsightsDataset:
    """Build KPIs and ranking frames from the aggregated dataset."""
    frames: Dict[str, pl.DataFrame] = {}
    kpis = _build_kpis(aggregated, validation)

    prod_store = _frame(aggregated, ("prod_store", "store"))
    prod_item = _frame(aggregated, ("prod_item", "item"))
    upc_summary = _frame(aggregated, ("upc",))
    if upc_summary is None:
        upc_summary = prod_item

    _build_store_rankings(frames, prod_store)
    _build_item_rankings(frames, prod_item)
    _build_upc_rankings(frames, upc_summary)
    _build_distributions(frames, upc_summary)
    _build_missing_store_stats(frames, validation, prod_store)

    return InsightsDataset(
        frames=frames,
        kpis=kpis,
        metadata={
            "level": aggregated.level,
            "has_prod_store": prod_store is not None,
            "has_upc_summary": upc_summary is not None,
        },
    )


def _frame(
    aggregated: AggregatedDataset,
    keys: tuple,
) -> Optional[pl.DataFrame]:
    for key in keys:
        frame = getattr(aggregated, key, None)
        if frame is not None and not frame.is_empty():
            return frame
    return None


def _build_kpis(
    aggregated: AggregatedDataset,
    validation: Optional[ValidationDataset],
) -> Optional[pl.DataFrame]:
    prod_store = _frame(aggregated, ("prod_store", "store"))
    test_store = _frame(aggregated, ("test_store",))
    prod_upc = _frame(aggregated, ("prod_item", "item"))
    test_upc = _frame(aggregated, ("test_item",))

    if prod_store is None and prod_upc is None:
        return None

    labels = {}
    if validation is not None:
        labels = {
            "prod_label": validation.metadata.get("prod_label", "BAU"),
            "test_label": validation.metadata.get("test_label", "TEST"),
            "execution_metrics": validation.metadata.get("metrics_snapshot"),
        }

    kpis = generate_summary_analytics(
        prod_store_agg=prod_store,
        test_store_agg=test_store,
        prod_upc_summary=prod_upc,
        test_upc_summary=test_upc,
        prod_item_comparison=(
            validation.item_difference if validation is not None else None
        ),
        store_diff=(
            validation.store_difference if validation is not None else None
        ),
        execution_metrics=labels.get("execution_metrics"),
        prod_label=labels.get("prod_label", "BAU"),
        test_label=labels.get("test_label", "TEST"),
    )
    return kpis if kpis is not None and not kpis.is_empty() else None


def _build_store_rankings(
    frames: Dict[str, pl.DataFrame],
    store_summary: Optional[pl.DataFrame],
) -> None:
    if store_summary is None:
        return
    if "Units" not in store_summary.columns or "Totalprice" not in store_summary.columns:
        return
    sf = store_summary.filter(pl.col("Units").is_not_null())
    try:
        frames["top_stores"] = pl.concat([
            sf.top_k(10, by="Totalprice").with_columns(pl.lit("Sales").alias("rank_by")),
            sf.top_k(10, by="Units").with_columns(pl.lit("Quantity").alias("rank_by")),
        ])
        frames["bottom_stores"] = pl.concat([
            sf.bottom_k(10, by="Totalprice").with_columns(pl.lit("Sales").alias("rank_by")),
            sf.bottom_k(10, by="Units").with_columns(pl.lit("Quantity").alias("rank_by")),
        ])
        frames["top5_stores_by_sales"] = sf.top_k(5, by="Totalprice").with_columns(
            pl.lit("Sales").alias("rank_by")
        )
        frames["top5_stores_by_qty"] = sf.top_k(5, by="Units").with_columns(
            pl.lit("Quantity").alias("rank_by")
        )
        frames["bottom5_stores"] = sf.bottom_k(5, by="Totalprice").with_columns(
            pl.lit("Sales").alias("rank_by")
        )
    except Exception as exc:  # noqa: BLE001 — insights must not fail the pipeline
        logger.warning("Could not build store ranking sheets: %s", exc)


def _build_item_rankings(
    frames: Dict[str, pl.DataFrame],
    item_summary: Optional[pl.DataFrame],
) -> None:
    if item_summary is None or item_summary.is_empty():
        return
    names = {
        "CATEGORY": "top_categories",
        "BRAND": "top_brands",
        "DEPARTMENT": "top_departments",
    }
    try:
        for attr, frame_name in names.items():
            if attr in item_summary.columns:
                grouped = (
                    item_summary
                    .group_by(attr)
                    .agg([
                        pl.sum("TOTAL_DOLLARS").alias("SALES"),
                        pl.sum("UNITS_SOLD").alias("QTY"),
                    ])
                    .sort("SALES", descending=True)
                )
                if not grouped.is_empty():
                    frames[frame_name] = grouped.head(10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not build item ranking sheets: %s", exc)


def _build_upc_rankings(
    frames: Dict[str, pl.DataFrame],
    upc_summary: Optional[pl.DataFrame],
) -> None:
    if upc_summary is None:
        return
    try:
        if "TOTAL_DOLLARS" in upc_summary.columns:
            frames["top_upcs"] = upc_summary.top_k(10, by="TOTAL_DOLLARS").with_columns(
                pl.lit("Top").alias("rank")
            )
            frames["bottom_upcs"] = upc_summary.bottom_k(10, by="TOTAL_DOLLARS").with_columns(
                pl.lit("Bottom").alias("rank")
            )
        if "UNITS_SOLD" in upc_summary.columns:
            frames["top_upcs_by_qty"] = upc_summary.top_k(10, by="UNITS_SOLD").with_columns(
                pl.lit("Top Qty").alias("rank")
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not build UPC ranking sheets: %s", exc)


def _build_distributions(
    frames: Dict[str, pl.DataFrame],
    upc_summary: Optional[pl.DataFrame],
) -> None:
    if upc_summary is None or upc_summary.is_empty():
        return
    try:
        if "TOTAL_DOLLARS" in upc_summary.columns:
            frames["sales_distribution"] = _quantile_distribution(
                upc_summary, "TOTAL_DOLLARS"
            )
        if "UNITS_SOLD" in upc_summary.columns:
            frames["quantity_distribution"] = _quantile_distribution(
                upc_summary, "UNITS_SOLD"
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not build distributions: %s", exc)


def _quantile_distribution(frame: pl.DataFrame, col: str) -> pl.DataFrame:
    probs = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0]
    rows = []
    for p in probs:
        value = frame[col].quantile(p)
        rows.append({"quantile": p, "value": value})
    return pl.DataFrame(rows).sort("quantile")


def _build_missing_store_stats(
    frames: Dict[str, pl.DataFrame],
    validation: Optional[ValidationDataset],
    store_summary: Optional[pl.DataFrame],
) -> None:
    missing_in_test = 0
    missing_in_prod = 0
    store_count = store_summary.height if store_summary is not None else 0
    if validation is not None and validation.store_list_result:
        missing_in_test = _count_list(validation.store_list_result.get("missing_in_test", ""))
        missing_in_prod = _count_list(validation.store_list_result.get("missing_in_prod", ""))
    frames["missing_store_stats"] = pl.DataFrame(
        [{
            "total_stores": store_count,
            "missing_in_test": missing_in_test,
            "missing_in_prod": missing_in_prod,
        }]
    )


def _count_list(value: str) -> int:
    if not value:
        return 0
    return len([v.strip() for v in value.split(",") if v.strip()])

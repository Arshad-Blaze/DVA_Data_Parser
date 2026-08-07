"""Aggregation Stage — CanonicalDataset → AggregatedDataset.

Responsibility: consume the immutable CanonicalDataset and produce an
AggregatedDataset (store/item/UPC summaries).  Aggregation must not know
about the UI, parser, or discovery.
"""
from __future__ import annotations

import logging
import time

import polars as pl

from dav_tool._aggregators import aggregate_dataset
from dav_tool.workflow.canonical import CanonicalDataset

from ..contracts import AggregatedDataset
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class AggregationStage(BaseStage):
    """Aggregates the canonical dataset to store/item/UPC level."""

    name = "aggregation"
    label = "Aggregation"

    def execute(self, ctx) -> StageResult:
        dataset = ctx.canonical
        if dataset is None:
            raise FatalStageError(
                "Aggregation requires a CanonicalDataset (run Canonical Dataset first).",
                user_message="No canonical dataset available.",
            )
        if not isinstance(dataset, CanonicalDataset):
            raise FatalStageError(
                "Aggregation received a non-CanonicalDataset object.",
                user_message="Invalid dataset for aggregation.",
            )

        t0 = time.perf_counter()
        store: Optional[pl.DataFrame] = None
        item: Optional[pl.DataFrame] = None
        upc: Optional[pl.DataFrame] = None

        capabilities = dataset.capabilities
        level = dataset.level

        # The canonical dataset is built for a specific level; aggregate the
        # requested level.  Fall back to a capable level when mismatched.
        try:
            if level == "store":
                store = aggregate_dataset(dataset)
            elif level == "upc":
                upc = aggregate_dataset(dataset)
            else:
                item = aggregate_dataset(dataset)
        except Exception as exc:  # noqa: BLE001 — surface as fatal
            logger.exception("Aggregation failed: %s", exc)
            raise FatalStageError(
                f"Aggregation failed: {exc}",
                user_message="Aggregation of the canonical dataset failed.",
            ) from exc

        elapsed = time.perf_counter() - t0
        ctx.metrics.record("aggregation", "aggregation_stage", elapsed)

        ctx.aggregated = AggregatedDataset(
            level=level,
            store=store,
            item=item,
            upc=upc,
            metrics={
                "elapsed_seconds": round(elapsed, 3),
                "rows": sum(
                    df.height for df in (store, item, upc) if df is not None
                ),
            },
        )
        return StageResult(stage=self.name)

"""Quantity Resolution Stage — CanonicalMapping → QuantityResolution.

Responsibility: decide how mixed units/weight retailers resolve quantity and
which provenance columns to preserve.  The actual per-row resolution is a pure
function of the quantity rule and is applied lazily by the Canonical Dataset
Stage; this stage makes the *policy* explicit and isolated.

No aggregation layer implements quantity rules.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..contracts import CanonicalMapping, QuantityResolution
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)

_DEFAULT_STRATEGY = "auto"


class QuantityResolutionStage(BaseStage):
    """Produces the QuantityResolution policy for the canonical dataset."""

    name = "quantity_resolution"
    label = "Quantity Resolution"

    def execute(self, ctx) -> StageResult:
        mapping: Optional[CanonicalMapping] = ctx.mapping
        if mapping is None:
            raise FatalStageError(
                "Quantity Resolution requires a CanonicalMapping (run Canonical Mapping first).",
                user_message="No canonical mapping available.",
            )

        t0 = time.perf_counter()
        resolution = build_quantity_resolution(mapping, ctx.user_config or {})
        elapsed = time.perf_counter() - t0
        ctx.metrics.record("quantity", "quantity_resolution_stage", elapsed)
        ctx.quantity_resolution = resolution
        return StageResult(stage=self.name)


def build_quantity_resolution(
    mapping: CanonicalMapping,
    user_config: Dict[str, Any],
) -> QuantityResolution:
    """Build the QuantityResolution policy from the mapping + user config."""
    strategy = (
        user_config.get("quantity_strategy")
        or _legacy_strategy(user_config.get("quantity_type"))
        or _DEFAULT_STRATEGY
    )
    weight_uom = user_config.get("weight_uom") or "lb"
    weight_uom_col = mapping.physical("WEIGHT_UOM")
    units_uom = user_config.get("units_uom")
    preserve = bool(user_config.get("preserve_quantity_provenance", True))

    has_weight = mapping.has("WEIGHT_QTY")
    if not has_weight and strategy in ("weight_only", "prefer_weight"):
        logger.warning(
            "Quantity strategy '%s' requested but no WEIGHT_QTY column is mapped; "
            "falling back to 'auto'.", strategy,
        )
        strategy = _DEFAULT_STRATEGY

    return QuantityResolution(
        strategy=strategy,
        weight_uom=weight_uom,
        weight_uom_col=weight_uom_col,
        units_uom=units_uom,
        preserve_provenance=preserve,
        metadata={
            "quantity_type": user_config.get("quantity_type") or "mixed" if has_weight else "units",
            "has_weight_qty": has_weight,
            "mapping_confidence": mapping.confidence,
        },
    )


def _legacy_strategy(quantity_type: Optional[str]) -> Optional[str]:
    if not quantity_type:
        return None
    return {
        "units": "units_only",
        "weight": "weight_only",
        "mixed": "auto",
    }.get(quantity_type)

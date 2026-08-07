"""Transformation Engine Stage — executes the TransformationPlan.

Responsibility: run the Transformation Engine against the DiscoveryResult and
TransformationPlan, producing a :class:`TransformedDataset` on the context.
No parsing occurs here — only record reshaping (header/trailer/metadata
removal, flattening, joins).
"""
from __future__ import annotations

import logging

from ..contracts import TransformedDataset
from ..stage import BaseStage, StageResult, FatalStageError
from ..transformation import TransformationEngine

logger = logging.getLogger(__name__)


class TransformationEngineStage(BaseStage):
    """Executes the plan's transformations into a TransformedDataset."""

    name = "transformation_engine"
    label = "Transformation"

    def __init__(self, engine: TransformationEngine = None) -> None:
        self._engine = engine or TransformationEngine()

    def execute(self, ctx) -> StageResult:
        if ctx.discovery is None:
            raise FatalStageError(
                "Transformation Engine requires a DiscoveryResult (run Discovery first).",
                user_message="Discovery has not completed.",
            )
        if ctx.plan is None:
            raise FatalStageError(
                "Transformation Engine requires a TransformationPlan (run Planning first).",
                user_message="Transformation planning has not completed.",
            )

        transformed = self._engine.execute(
            ctx.discovery,
            ctx.plan,
            source=ctx.source,
        )
        ctx.transformed = transformed
        return StageResult(stage=self.name)

"""Parser Pipeline Stage — executes the pipeline's parsing work.

Responsibility: produce exactly one ParsedDataset from a DiscoveryResult and
TransformationPlan.  The concrete parser is selected by the Parser Factory
(parsers registered in the Parser Registry).  The UI never selects parsers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import polars as pl

from dav_tool.parser import default_factory as parser_factory
from dav_tool.workflow.discovery import DiscoveryResult

from ..contracts import ParsedDataset, TransformationPlan
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class ParserPipelineStage(BaseStage):
    """Runs the selected parser against the DiscoveryResult."""

    name = "parser_pipeline"
    label = "Parsing"

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        """Delegate parser support to the Parser Registry."""
        from dav_tool.parser.factory import _REGISTRY

        recommended = discovery.recommended_parser
        if recommended and _REGISTRY.get(recommended) is not None:
            return True
        for name in _REGISTRY.names():
            parser_cls = _REGISTRY.get(name)
            if parser_cls is not None:
                try:
                    if parser_cls.supports(discovery):
                        return True
                except Exception:  # noqa: BLE001 — defensive
                    continue
        return False

    def execute(self, ctx) -> StageResult:
        discovery = ctx.discovery
        if discovery is None:
            raise FatalStageError(
                "Parser Pipeline requires a DiscoveryResult (run Discovery first).",
                user_message="Discovery has not completed.",
            )

        try:
            result = parser_factory.parse(
                discovery,
                source=ctx.source,
                transformed=ctx.transformed,
            )
        except Exception as exc:  # noqa: BLE001 — surface as fatal stage error
            logger.exception("Parsing failed: %s", exc)
            raise FatalStageError(
                f"Parsing failed: {exc}",
                user_message="The file could not be parsed with the selected pipeline.",
            ) from exc

        data = result.to_dataframe() if result is not None else pl.DataFrame()
        column_names = ctx.user_config.get("column_names") if ctx.user_config else None
        if data.height and column_names and len(column_names) == data.width:
            data = data.rename({
                col: name for col, name in zip(data.columns, column_names)
            })
        plan = ctx.plan

        parsed = ParsedDataset(
            data=data,
            schema=tuple(data.columns),
            parser_name=result.metadata.get("parser", "delimited")
            if result is not None else "delimited",
            discovery=discovery,
            row_count=data.height,
            metadata=dict(result.metadata) if result is not None else {},
            warnings=tuple(result.warnings) if result is not None else (),
        )
        if plan is not None:
            parsed = _apply_plan(parsed, plan)

        ctx.parsed = parsed
        return StageResult(stage=self.name)


def _apply_plan(parsed: ParsedDataset, plan: TransformationPlan) -> ParsedDataset:
    """Apply non-destructive plan hints to the parsed dataset.

    Flattening and header/trailer removal are already handled by the
    underlying parsers; this applies plan metadata so downstream stages
    can audit what transformations were intended.
    """
    metadata = dict(parsed.metadata)
    metadata["transformation_plan"] = {
        "flatten_operations": list(plan.flatten_operations),
        "join_operations": list(plan.join_operations),
        "header_removal": plan.header_removal,
        "trailer_removal": list(plan.trailer_removal),
        "parent_replication": list(plan.parent_replication),
        "child_expansion": list(plan.child_expansion),
    }
    return ParsedDataset(
        data=parsed.data,
        schema=parsed.schema,
        parser_name=parsed.parser_name,
        discovery=parsed.discovery,
        row_count=parsed.row_count,
        metadata=metadata,
        warnings=parsed.warnings,
    )

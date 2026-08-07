"""Pipeline Registry — composes reusable stages into complete pipelines.

A pipeline is an ordered collection of stages.  The registry maps a
pipeline name to a pipeline and selects a pipeline based on a
DiscoveryResult.  Every pipeline produces exactly one ParsedDataset.

Standard pipelines:
- ``standard_delimited``  — flat delimited (CSV/TSV)
- ``fixed_width``         — fixed-width records
- ``record_based``        — HEB / multiline record-tree files
- ``sales_product``       — delimited sales + optional product master join
- ``excel``               — Excel workbooks
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Type

from dav_tool.workflow.discovery import DiscoveryResult

from .stage import BaseStage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pipeline:
    """A named, ordered collection of stages."""

    name: str
    stages: Tuple[BaseStage, ...]
    description: str = ""

    def __post_init__(self) -> None:
        for stage in self.stages:
            if not isinstance(stage, BaseStage):
                raise TypeError(
                    f"Pipeline '{self.name}' contains non-stage object: {stage!r}"
                )
            if not stage.name:
                raise ValueError(f"Stage in pipeline '{self.name}' has no name")


class PipelineRegistry:
    """Registry mapping pipeline names to :class:`Pipeline` objects.

    Selection uses ``DiscoveryResult.recommended_parser`` when available,
    otherwise iterates registered pipelines asking each for ``supports()``.
    """

    def __init__(self) -> None:
        self._pipelines: Dict[str, Pipeline] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, pipeline: Pipeline) -> Pipeline:
        if pipeline.name in self._pipelines:
            logger.warning("Overwriting existing pipeline '%s'", pipeline.name)
        self._pipelines[pipeline.name] = pipeline
        return pipeline

    def register_alias(self, alias: str, target: str) -> None:
        self._aliases[alias] = target

    def get(self, name: str) -> Optional[Pipeline]:
        resolved = self._aliases.get(name, name)
        return self._pipelines.get(resolved)

    def names(self) -> List[str]:
        return sorted(self._pipelines.keys())

    def select(self, discovery: DiscoveryResult) -> Pipeline:
        """Select the best pipeline for *discovery*.

        Prefers ``discovery.recommended_parser``; falls back to asking every
        registered pipeline ``supports()`` in registration order.
        """
        recommended = discovery.recommended_parser
        if recommended:
            pipeline = self.get(recommended)
            if pipeline is not None:
                return pipeline

        for pipeline in self._pipelines.values():
            if _supports(pipeline, discovery):
                return pipeline

        return self.get("standard_delimited")


def _supports(pipeline: Pipeline, discovery: DiscoveryResult) -> bool:
    """Ask the pipeline's stages whether they can handle *discovery*.

    The first stage that owns parser selection implements ``supports()``.
    """
    for stage in pipeline.stages:
        supports = getattr(stage, "supports", None)
        if supports is None:
            continue
        try:
            if supports(discovery):
                return True
        except Exception as exc:  # defensive
            logger.warning("supports() raised for %s: %s", pipeline.name, exc)
    return False


#: Module-level shared registry (populated by bootstrap).
default_registry = PipelineRegistry()

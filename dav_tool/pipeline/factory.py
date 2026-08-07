"""PipelineFactory — selects complete processing pipelines.

Replaces ParserFactory as the entry point for pipeline selection.  Given a
DiscoveryResult, the factory asks the Pipeline Registry for the matching
pipeline and returns it.  The Parser Pipeline Stage then executes the
pipeline's parsing stages to produce exactly one ParsedDataset.
"""
from __future__ import annotations

import logging
from typing import Optional

from dav_tool.workflow.discovery import DiscoveryResult

from .contracts import ParsedDataset
from .registry import Pipeline, PipelineRegistry, default_registry

logger = logging.getLogger(__name__)


class PipelineFactory:
    """Selects a complete pipeline for a DiscoveryResult."""

    def __init__(self, registry: Optional[PipelineRegistry] = None) -> None:
        self._registry = registry or default_registry

    def available_pipelines(self):
        return self._registry.names()

    def select(self, discovery: DiscoveryResult) -> Pipeline:
        return self._registry.select(discovery)

    def run(self, discovery: DiscoveryResult, source=None, **kwargs) -> ParsedDataset:
        """Convenience: select the pipeline and parse via the Parser Pipeline Stage."""
        from .stages.parser_pipeline import ParserPipelineStage

        pipeline = self.select(discovery)
        # Build a minimal context and run only the parsing stages.
        from .context import PipelineContext
        from .stage import FatalStageError

        ctx = PipelineContext(pipeline_name=pipeline.name, source=source)
        ctx.discovery = discovery
        ctx.file_paths = list(discovery.file_paths or [])

        parser_stage = ParserPipelineStage()
        parser_stage.supports = lambda d: True  # pipeline already selected
        result = parser_stage.run(ctx)
        if not result.success:
            raise FatalStageError(result.errors[0] if result.errors else "Parsing failed.")
        parsed = ctx.parsed
        if parsed is None:
            raise FatalStageError("Parser stage produced no ParsedDataset.")
        return parsed


#: Convenience singleton.
default_factory = PipelineFactory()

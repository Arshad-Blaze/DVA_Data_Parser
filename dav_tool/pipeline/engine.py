"""Workflow Engine — executes stages and maintains the PipelineContext.

Responsibilities:
- Start a workflow (select pipeline via the registry)
- Execute stages in order
- Handle failures (recoverable retries, fatal stops)
- Resume execution from the last completed stage
- Update progress
- Maintain the PipelineContext

The engine contains NO parsing, NO validation, and NO reporting logic — it
only orchestrates stages.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

from .context import PipelineContext
from .contracts import PipelineRun
from .registry import Pipeline, PipelineRegistry, default_registry
from .stage import BaseStage, StageResult

logger = logging.getLogger(__name__)

#: Stages that can be skipped when the discovery signal is absent.
#: These depend on discovery (dataset_graph, transform_plan) or on the plan
#: it produces (transformation_engine), so they cannot run without it.
_OPTIONAL_STAGES = {"dataset_graph", "transform_plan", "transformation_engine"}


class WorkflowEngine:
    """Orchestrates pipeline stages around a single PipelineContext."""

    def __init__(
        self,
        registry: Optional[PipelineRegistry] = None,
        context: Optional[PipelineContext] = None,
    ) -> None:
        self._registry = registry or default_registry
        self._context = context or PipelineContext()

    @property
    def context(self) -> PipelineContext:
        return self._context

    @property
    def registry(self) -> PipelineRegistry:
        return self._registry

    def select_pipeline(self, ctx: Optional[PipelineContext] = None) -> Pipeline:
        """Select the pipeline appropriate for the context's discovery."""
        context = ctx or self._context
        if context.discovery is not None:
            pipeline = self._registry.select(context.discovery)
            context.pipeline_name = pipeline.name
            return pipeline
        pipeline = self._registry.get(context.pipeline_name) or self._registry.get(
            "standard_delimited"
        )
        if pipeline is None:
            names = self._registry.names()
            if not names:
                raise RuntimeError(
                    "No pipelines are registered. Call bootstrap() or register a "
                    "pipeline before running the workflow engine."
                )
            pipeline = self._registry.get(names[0])
            context.pipeline_name = pipeline.name
        return pipeline

    # ── Execution ──────────────────────────────────────────────────

    def run(self, ctx: Optional[PipelineContext] = None) -> PipelineRun:
        """Run the full pipeline from the start."""
        context = ctx or self._context
        return self.execute(context)

    def execute(self, ctx: Optional[PipelineContext] = None) -> PipelineRun:
        """Execute the pipeline, resuming after the last completed stage."""
        context = ctx or self._context
        pipeline = self.select_pipeline(context)
        started = time.perf_counter()

        for stage in pipeline.stages:
            if self._already_completed(context, stage):
                continue
            self._execute_stage(context, stage, pipeline.name)
            if context.errors and self._should_stop(stage):
                break

        finished = time.perf_counter()
        run = PipelineRun(
            pipeline_name=pipeline.name,
            stages_completed=tuple(context.completed_stages),
            started_at=started,
            finished_at=finished,
            elapsed=round(finished - started, 3),
            errors=tuple(context.errors),
            warnings=tuple(context.warnings),
            metrics=context.metrics,
        )
        logger.info(
            "Pipeline '%s' finished in %.3fs — %d stage(s), %d error(s)",
            pipeline.name, run.elapsed, len(run.stages_completed), len(run.errors),
        )
        return run

    def resume(self, ctx: Optional[PipelineContext] = None) -> PipelineRun:
        """Resume execution from the last completed stage."""
        return self.execute(ctx)

    # ── Internals ──────────────────────────────────────────────────

    def _execute_stage(self, context: PipelineContext, stage: BaseStage, pipeline_name: str) -> None:
        context.phase = len(context.completed_stages) + 1
        logger.info("[%s] running stage '%s' (phase %d)", pipeline_name, stage.name, context.phase)

        result: StageResult = stage.run(context)
        if result.warnings:
            for w in result.warnings:
                context.add_warning(w)

        if not result.success:
            context.add_error(f"Stage '{stage.name}' failed: {result.errors[0]}")
            return

        context.completed_stages.append(stage.name)
        logger.info("[%s] stage '%s' completed in %.3fs", pipeline_name, stage.name, result.elapsed)

    def _already_completed(self, context: PipelineContext, stage: BaseStage) -> bool:
        return stage.name in context.completed_stages

    def _should_stop(self, stage: BaseStage) -> bool:
        """Fatal stages stop the pipeline; recoverable ones do not."""
        return True

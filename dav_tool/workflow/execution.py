"""Execution Engine — determines which operations to run and in what order.

Between Workflow and Operation Layer. The Workflow calls only ``run()``.
The Engine checks cached results, skips completed work, and dispatches
operations through the Operation Layer.

Architecture::

    Workflow (orchestration.py)
      ↓
    ExecutionEngine.run()
      ↓
    Operation Layer (OperationExecutor)
      ↓
    Processing Layer
"""
import logging
from typing import Optional

from dav_tool._observability import ProcessingMetrics

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Executes the correct operations based on context state.

    The engine never decides *what* to compute — it only checks what has
    already been computed (via cached results on the context) and skips
    completed work.  New operation types can be added without changing
    the Workflow layer.
    """

    def __init__(self):
        self._onboarding_ops = ["aggregate"]
        self._existing_ops = ["format_change"]

    def run(self, ctx, source=None) -> None:
        """Run all pending operations for *ctx*.

        Pipeline: Connection → Detection → Canonical → Requirement
                  → Operation → Processing → Validation → Output → Flush

        The Requirement step validates that configuration is complete
        before proceeding to operations.
        """
        self._validate_requirements(ctx)

        if hasattr(ctx, "prod") and hasattr(ctx, "test"):
            self._run_existing_workflow(ctx, source)
        else:
            self._run_onboarding_workflow(ctx, source)

    def _validate_requirements(self, ctx) -> None:
        """Validate that configuration requirements are met before execution.

        Checks that detection and canonical mapping have completed.
        Sets ``_requirements_ok`` on context; non-fatal warnings are stored
        in ``ctx.warnings``.
        """
        errors = []
        if not getattr(ctx, "file_type", None):
            errors.append("File type not detected — run Detection phase first")
        if not getattr(ctx, "columns", None) and not getattr(ctx, "schema", None):
            errors.append("No schema detected — run Canonical phase first")
        if getattr(ctx, "file_type", "") == "fixed":
            layout = getattr(ctx, "layout", None)
            if not layout:
                errors.append("Fixed-width files require a layout definition")
        if errors:
            ctx._requirement_errors = errors
            logger.error("Requirement validation failed: %s", "; ".join(errors))
        else:
            ctx._requirements_ok = True

    # ── Onboarding ──────────────────────────────────────────────────

    def _run_onboarding_workflow(self, ctx, source):
        """Execute pending onboarding operations."""
        needs_aggregate = ctx.store_agg is None or ctx.item_agg is None
        if needs_aggregate:
            self._execute_operation("aggregate", ctx, source)

    # ── Existing / Format Change ────────────────────────────────────

    def _run_existing_workflow(self, ctx, source):
        """Execute pending existing (two-sided) operations."""
        needs_aggregate = (
            ctx.prod.store_agg is None
            or ctx.test.store_agg is None
            or ctx.prod.item_agg is None
            or ctx.test.item_agg is None
        )
        if needs_aggregate:
            self._execute_operation("format_change", ctx, source)

    # ── Dispatch ────────────────────────────────────────────────────

    def _execute_operation(self, operation_type: str, ctx, source) -> None:
        """Dispatch an operation through the Operation Layer."""
        from dav_tool.operations.orchestration import OperationContext, OperationExecutor

        op_ctx = OperationContext(operation_type=operation_type, ctx=ctx, source=source)
        OperationExecutor().execute(op_ctx)

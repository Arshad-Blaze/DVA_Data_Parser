"""Workflow-level operation orchestration.

Bridges the Operation Layer (IDataOperation) with the Processing Layer.
Introduces OperationContext and OperationExecutor to make the Operation Layer
mandatory before Processing.

RC2: ``OperationExecutor`` dispatches via the workflow operation registry —
no hard-coded branching.  New operations require only registration.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from dav_tool.operations.registry import get_workflow_op

logger = logging.getLogger(__name__)


@dataclass
class OperationContext:
    """Contract passed from the Operation Layer to the Processing Layer.

    Tells the Processing Layer what business operation to execute and
    which context to use.  Processing never decides what operation is running.
    """
    operation_type: str
    """One of: 'aggregate', 'format_change'."""

    ctx: Optional[object] = None
    """ProcessingContext (onboarding) or ExistingContext (format_change)."""

    source: Optional[object] = None
    """IDataSource for file access."""


class OperationExecutor:
    """Executes a workflow-level operation by dispatching to the right processing logic.

    The executor translates the abstract ``OperationContext`` into concrete
    calls to the Processing Layer (aggregators, validators, etc.).

    Dispatching uses the ``WorkflowOperation`` registry — no hard-coded
    if/elif chain.  New operations are added by registering them.
    """

    def execute(self, op_ctx: OperationContext) -> None:
        """Run the operation.  Results are stored on the context.

        Raises RuntimeError for unknown operation types.
        """
        operation = get_workflow_op(op_ctx.operation_type)
        if operation is None:
            raise RuntimeError(
                f"Unknown operation type: {op_ctx.operation_type}. "
                f"Registered: {list_workflow_op_types()}"
            )
        operation.execute(op_ctx)


def list_workflow_op_types() -> list:
    """Return list of registered workflow operation type strings."""
    from dav_tool.operations.registry import list_workflow_ops
    return list_workflow_ops()

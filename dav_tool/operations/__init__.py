"""Data Operations Framework — reusable, config-driven operations on canonical data.

Every operation:
- Accepts a ``pl.DataFrame`` (canonical dataset)
- Returns an ``OperationResult``
- Knows nothing about retailer-specific columns
- Is fully configuration driven
"""

from dav_tool.operations.base import IDataOperation, OperationResult, OperationOptions
from dav_tool.operations.registry import (
    register, get, list_operations,
    register_workflow_op, get_workflow_op, list_workflow_ops,
)
from dav_tool.operations.aggregate import AggregateOperation, AggregateOptions

# ── Register Data Operations ──────────────────────────────────────

register(AggregateOperation())

# ── Register Workflow Operations ───────────────────────────────────

from dav_tool.operations.workflow_ops import AggregateWorkflowOp, FormatChangeWorkflowOp

register_workflow_op(AggregateWorkflowOp())
register_workflow_op(FormatChangeWorkflowOp())

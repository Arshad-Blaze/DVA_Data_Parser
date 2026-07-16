from typing import Any, Dict, Optional

from dav_tool.operations.base import IDataOperation


# ── Data Operation Registry ────────────────────────────────────────

_DATA_REGISTRY: Dict[str, IDataOperation] = {}


def register(operation: IDataOperation) -> None:
    _DATA_REGISTRY[operation.name] = operation


def get(name: str) -> Optional[IDataOperation]:
    return _DATA_REGISTRY.get(name)


def list_operations() -> list:
    return list(_DATA_REGISTRY.keys())


# ── Workflow Operation Registry ────────────────────────────────────

_WORKFLOW_REGISTRY: Dict[str, Any] = {}


def register_workflow_op(operation: Any) -> None:
    """Register a workflow-level operation (implements ``WorkflowOperation``)."""
    _WORKFLOW_REGISTRY[operation.operation_type] = operation


def get_workflow_op(operation_type: str) -> Optional[Any]:
    """Look up a workflow operation by type string."""
    return _WORKFLOW_REGISTRY.get(operation_type)


def list_workflow_ops() -> list:
    """List registered workflow operation type strings."""
    return list(_WORKFLOW_REGISTRY.keys())

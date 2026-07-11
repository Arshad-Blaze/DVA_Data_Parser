"""Operation registry — name-based lookup for all registered operations."""

from typing import Dict, Optional, Type

from dav_tool.operations.base import IDataOperation


_REGISTRY: Dict[str, IDataOperation] = {}


def register(operation: IDataOperation) -> None:
    """Register a singleton operation instance."""
    _REGISTRY[operation.name] = operation


def get(name: str) -> Optional[IDataOperation]:
    """Retrieve an operation by name."""
    return _REGISTRY.get(name)


def list_operations() -> list:
    """Return all registered operation names."""
    return list(_REGISTRY.keys())

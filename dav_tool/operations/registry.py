from typing import Dict, Optional

from dav_tool.operations.base import IDataOperation


_REGISTRY: Dict[str, IDataOperation] = {}


def register(operation: IDataOperation) -> None:
    _REGISTRY[operation.name] = operation


def get(name: str) -> Optional[IDataOperation]:
    return _REGISTRY.get(name)


def list_operations() -> list:
    return list(_REGISTRY.keys())

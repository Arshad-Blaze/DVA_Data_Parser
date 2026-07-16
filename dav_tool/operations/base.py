from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

import polars as pl


@dataclass
class OperationResult:
    df: pl.DataFrame
    operation: str = ""
    row_count: int = 0
    column_count: int = 0
    elapsed_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @classmethod
    def from_df(cls, df: pl.DataFrame, operation: str = "",
                elapsed_seconds: float = 0.0,
                metadata: Optional[Dict[str, Any]] = None,
                errors: Optional[List[str]] = None) -> "OperationResult":
        return cls(
            df=df,
            operation=operation,
            row_count=df.height,
            column_count=df.width,
            elapsed_seconds=elapsed_seconds,
            metadata=metadata or {},
            errors=errors or [],
        )

    @classmethod
    def error(cls, operation: str, message: str) -> "OperationResult":
        return cls(
            df=pl.DataFrame(),
            operation=operation,
            errors=[message],
        )


@dataclass(frozen=True)
class OperationOptions:
    pass


class IDataOperation(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def execute(self, df: pl.DataFrame, options: OperationOptions) -> OperationResult:
        ...

    def validate(self, df: pl.DataFrame, options: OperationOptions) -> List[str]:
        return []


class WorkflowOperation(Protocol):
    """Protocol for workflow-level operations.

    Unlike ``IDataOperation`` (which operates on DataFrames),
    ``WorkflowOperation`` operates on an ``OperationContext`` and
    orchestrates calls to the Processing Layer.

    Register instances via ``register_workflow_op()``.
    Future operations require zero ``OperationExecutor`` changes.
    """

    operation_type: str

    def execute(self, op_ctx: Any) -> None:
        ...

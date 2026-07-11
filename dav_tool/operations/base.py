"""Core interfaces for the Data Operations Framework.

Every operation implements ``IDataOperation`` and returns an
``OperationResult``.  Option objects are frozen dataclasses that
bundle operation-specific parameters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import polars as pl


# ── Result ──────────────────────────────────────────────────────────

@dataclass
class OperationResult:
    """Standardised return type for every data operation."""

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


# ── Options ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OperationOptions:
    """Base for all operation option objects."""
    pass


# ── Interface ───────────────────────────────────────────────────────

class IDataOperation(ABC):
    """Contract that every data operation must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable operation name (e.g. ``"Aggregate"``)."""

    @abstractmethod
    def execute(self, df: pl.DataFrame, options: OperationOptions) -> OperationResult:
        """Run the operation on *df* and return a result."""

    def validate(self, df: pl.DataFrame, options: OperationOptions) -> List[str]:
        """Pre-flight checks.  Return empty list when valid."""
        return []

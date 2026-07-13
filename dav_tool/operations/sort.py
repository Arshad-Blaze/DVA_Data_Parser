import time
from dataclasses import dataclass, field
from typing import List

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


@dataclass(frozen=True)
class SortColumn:
    column: str
    ascending: bool = True


@dataclass(frozen=True)
class SortOptions(OperationOptions):
    columns: List[SortColumn] = field(default_factory=list)


class SortOperation(IDataOperation):
    @property
    def name(self) -> str:
        return "Sort"

    def execute(self, df: pl.DataFrame, options: SortOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        by = [sc.column for sc in options.columns]
        descending = [not sc.ascending for sc in options.columns]
        result = df.sort(by=by, descending=descending, maintain_order=True)
        elapsed = time.perf_counter() - t0
        return OperationResult.from_df(result, self.name, elapsed)

    def validate(self, df: pl.DataFrame, options: SortOptions) -> List[str]:
        errors: List[str] = []
        if not options.columns:
            errors.append("At least one sort column is required.")
        for sc in options.columns:
            if sc.column not in df.columns:
                errors.append(f"Sort column '{sc.column}' not found in DataFrame.")
        return errors

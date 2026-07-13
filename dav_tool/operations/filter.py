import time
from dataclasses import dataclass, field
from typing import Any, List

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


@dataclass(frozen=True)
class FilterCondition:
    column: str
    operator: str
    value: Any = None


@dataclass(frozen=True)
class FilterOptions(OperationOptions):
    conditions: List[FilterCondition] = field(default_factory=list)
    mode: str = "and"


class FilterOperation(IDataOperation):
    @property
    def name(self) -> str:
        return "Filter"

    def execute(self, df: pl.DataFrame, options: FilterOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        predicates = []
        for cond in options.conditions:
            col = pl.col(cond.column)
            if cond.operator == "eq":
                predicates.append(col == cond.value)
            elif cond.operator == "contains":
                predicates.append(col.cast(pl.Utf8).str.contains(str(cond.value)))
            elif cond.operator == "startswith":
                predicates.append(col.cast(pl.Utf8).str.starts_with(str(cond.value)))
            elif cond.operator == "endswith":
                predicates.append(col.cast(pl.Utf8).str.ends_with(str(cond.value)))
            elif cond.operator == "gt":
                predicates.append(col > cond.value)
            elif cond.operator == "lt":
                predicates.append(col < cond.value)
            elif cond.operator == "gte":
                predicates.append(col >= cond.value)
            elif cond.operator == "lte":
                predicates.append(col <= cond.value)
            elif cond.operator == "in_list":
                predicates.append(col.is_in(cond.value))
            elif cond.operator == "null":
                predicates.append(col.is_null())
            elif cond.operator == "not_null":
                predicates.append(col.is_not_null())

        combined = predicates[0]
        for p in predicates[1:]:
            if options.mode == "or":
                combined = combined | p
            else:
                combined = combined & p

        result = df.filter(combined)
        elapsed = time.perf_counter() - t0
        return OperationResult.from_df(result, self.name, elapsed)

    def validate(self, df: pl.DataFrame, options: FilterOptions) -> List[str]:
        errors: List[str] = []
        if not options.conditions:
            errors.append("At least one filter condition is required.")
        valid_ops = {"eq", "contains", "startswith", "endswith",
                     "gt", "lt", "gte", "lte", "in_list", "null", "not_null"}
        for cond in options.conditions:
            if cond.column not in df.columns:
                errors.append(f"Column '{cond.column}' not found in DataFrame.")
            if cond.operator not in valid_ops:
                errors.append(f"Unknown operator '{cond.operator}'. Supported: {', '.join(sorted(valid_ops))}")
        return errors

import time
from dataclasses import dataclass, field
from typing import Dict, List

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


AGG_FUNCTIONS = {
    "sum": pl.sum,
    "count": pl.count,
    "avg": pl.mean,
    "min": pl.min,
    "max": pl.max,
    "first": pl.first,
    "last": pl.last,
}


@dataclass(frozen=True)
class AggregateOptions(OperationOptions):
    group_by: List[str] = field(default_factory=list)
    aggregations: Dict[str, str] = field(default_factory=dict)


class AggregateOperation(IDataOperation):
    @property
    def name(self) -> str:
        return "Aggregate"

    def validate(self, df: pl.DataFrame, options: AggregateOptions) -> List[str]:
        errors: List[str] = []
        if not options.group_by:
            errors.append("At least one group_by column is required.")
        missing = set(options.group_by) - set(df.columns)
        if missing:
            errors.append(f"Group-by columns not found in DataFrame: {', '.join(sorted(missing))}")
        for col, func in options.aggregations.items():
            if col not in df.columns:
                errors.append(f"Aggregation column '{col}' not found in DataFrame.")
            if func not in AGG_FUNCTIONS:
                errors.append(f"Unknown aggregation function '{func}'. Supported: {', '.join(AGG_FUNCTIONS)}")
        return errors

    def execute(self, df: pl.DataFrame, options: AggregateOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        aggs = []
        for col, func in options.aggregations.items():
            expr = AGG_FUNCTIONS[func](col)
            alias = f"{col}_{func}" if func != "sum" else col
            aggs.append(expr.alias(alias))

        result = df.group_by(options.group_by).agg(aggs)
        elapsed = time.perf_counter() - t0
        return OperationResult.from_df(result, self.name, elapsed)

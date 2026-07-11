"""Statistics Operation — compute descriptive statistics on canonical data.

Generates row count, column count, null counts, distinct counts,
min, max, mean, median, std dev, top values, and memory usage.
Configuration driven.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


@dataclass(frozen=True)
class StatisticsOptions(OperationOptions):
    """Configuration for a statistics operation."""
    columns: Optional[List[str]] = None  # None = all columns
    top_n: int = 5  # number of top values per column
    include_memory: bool = True


class StatisticsOperation(IDataOperation):
    """Compute descriptive statistics on a DataFrame."""

    @property
    def name(self) -> str:
        return "Statistics"

    def validate(self, df: pl.DataFrame, options: StatisticsOptions) -> list:
        errors: list = []
        if options.columns:
            missing = set(options.columns) - set(df.columns)
            if missing:
                errors.append(f"Columns not found in DataFrame: {', '.join(sorted(missing))}")
        return errors

    def execute(self, df: pl.DataFrame, options: StatisticsOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        cols = options.columns or df.columns
        stats: Dict[str, Dict] = {}

        for col in cols:
            series = df[col]
            col_stats: Dict = {
                "dtype": str(series.dtype),
                "null_count": int(series.null_count()),
                "unique_count": int(series.n_unique()),
            }

            if series.dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.Int16, pl.Int8):
                desc = series.describe()
                for row in desc.iter_rows(named=True):
                    stat_name = row["statistic"]
                    stat_val = row["value"]
                    if stat_name in ("min", "max", "mean", "median", "std"):
                        col_stats[stat_name] = float(stat_val) if stat_val is not None else None

            # Top values — use top_k to avoid materializing all unique values
            vc = series.value_counts()
            top_vals = vc.top_k(options.top_n, by="count", reverse=True)
            top_vals = top_vals.rename({top_vals.columns[0]: "value"})
            col_stats["top_values"] = [
                {"value": row["value"], "count": row["count"]}
                for row in top_vals.iter_rows(named=True)
            ]

            stats[col] = col_stats

        metadata = {
            "row_count": df.height,
            "column_count": df.width,
            "columns": cols,
            "statistics": stats,
        }

        if options.include_memory:
            metadata["memory_bytes"] = df.estimated_size("bytes")
            metadata["memory_mb"] = round(df.estimated_size("mb"), 2)

        # Build a summary DataFrame
        rows = []
        for col_name, col_stats in stats.items():
            rows.append({
                "column": col_name,
                "dtype": col_stats["dtype"],
                "null_count": col_stats["null_count"],
                "unique_count": col_stats["unique_count"],
                "min": col_stats.get("min"),
                "max": col_stats.get("max"),
                "mean": col_stats.get("mean"),
                "median": col_stats.get("median"),
                "std": col_stats.get("std"),
            })
        result_df = pl.DataFrame(rows) if rows else pl.DataFrame()

        elapsed = time.perf_counter() - t0
        return OperationResult.from_df(result_df, self.name, elapsed, metadata=metadata)

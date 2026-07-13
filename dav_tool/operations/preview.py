import time
from dataclasses import dataclass

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


@dataclass(frozen=True)
class PreviewOptions(OperationOptions):
    mode: str = "head"
    n_rows: int = 10
    columns: list = None
    seed: int = 42

    def __post_init__(self):
        if self.columns is None:
            object.__setattr__(self, "columns", [])


class PreviewOperation(IDataOperation):
    @property
    def name(self) -> str:
        return "Preview"

    def execute(self, df: pl.DataFrame, options: PreviewOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        if options.columns:
            df = df.select(options.columns)

        if options.mode == "head":
            result = df.head(options.n_rows)
        elif options.mode == "tail":
            result = df.tail(options.n_rows)
        elif options.mode == "random":
            n = min(options.n_rows, df.height)
            result = df.sample(n=n, seed=options.seed)
        else:
            result = df.head(options.n_rows)

        elapsed = time.perf_counter() - t0
        metadata = {"total_rows": df.height, "preview_rows": result.height}
        return OperationResult.from_df(result, self.name, elapsed, metadata=metadata)

    def validate(self, df: pl.DataFrame, options: PreviewOptions) -> list:
        errors = []
        if options.columns:
            missing = set(options.columns) - set(df.columns)
            if missing:
                errors.append(f"Columns not found: {', '.join(sorted(missing))}")
        return errors

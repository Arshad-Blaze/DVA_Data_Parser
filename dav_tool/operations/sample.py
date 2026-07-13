import time
from dataclasses import dataclass
from typing import Optional

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


@dataclass(frozen=True)
class SampleOptions(OperationOptions):
    mode: str = "head"
    n: Optional[int] = None
    pct: Optional[float] = None
    seed: Optional[int] = None


class SampleOperation(IDataOperation):
    @property
    def name(self) -> str:
        return "Sample"

    def execute(self, df: pl.DataFrame, options: SampleOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        if options.mode == "head":
            result = df.head(options.n)
        elif options.mode == "tail":
            result = df.tail(options.n)
        elif options.mode == "random":
            n = min(options.n, df.height)
            result = df.sample(n=n, seed=options.seed)
        elif options.mode == "percentage":
            n = max(1, int(df.height * options.pct))
            result = df.head(n)
        else:
            result = df

        elapsed = time.perf_counter() - t0
        return OperationResult.from_df(result, self.name, elapsed)

    def validate(self, df: pl.DataFrame, options: SampleOptions) -> list:
        errors = []
        valid_modes = {"head", "tail", "random", "percentage"}
        if options.mode not in valid_modes:
            errors.append(f"Unknown sample mode '{options.mode}'. Supported: {', '.join(sorted(valid_modes))}")
        if options.mode in ("head", "tail", "random") and (options.n is None or options.n < 0):
            errors.append(f"Mode '{options.mode}' requires a non-negative n value.")
        if options.mode == "percentage" and (options.pct is None or not 0.0 <= options.pct <= 1.0):
            errors.append("Mode 'percentage' requires pct between 0.0 and 1.0.")
        return errors

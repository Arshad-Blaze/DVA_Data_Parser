import os
import time
from dataclasses import dataclass

import polars as pl

from dav_tool.operations.base import IDataOperation, OperationOptions, OperationResult


@dataclass(frozen=True)
class ExportOptions(OperationOptions):
    path: str = ""
    format: str = "csv"
    include_header: bool = True
    separator: str = ","


class ExportOperation(IDataOperation):
    @property
    def name(self) -> str:
        return "Export"

    def execute(self, df: pl.DataFrame, options: ExportOptions) -> OperationResult:
        t0 = time.perf_counter()
        errors = self.validate(df, options)
        if errors:
            return OperationResult.error(self.name, "; ".join(errors))

        try:
            if options.format == "csv":
                df.write_csv(options.path, separator=options.separator,
                             include_header=options.include_header)
            elif options.format == "parquet":
                df.write_parquet(options.path)
            elif options.format == "excel":
                df.write_excel(options.path)
        except Exception as e:
            return OperationResult.error(self.name, f"Export failed: {e}")

        elapsed = time.perf_counter() - t0
        metadata = {
            "path": options.path,
            "format": options.format,
            "file_size_bytes": os.path.getsize(options.path) if os.path.exists(options.path) else 0,
        }
        return OperationResult.from_df(pl.DataFrame(), self.name, elapsed, metadata=metadata)

    def validate(self, df: pl.DataFrame, options: ExportOptions) -> list:
        errors = []
        valid_formats = {"csv", "parquet", "excel"}
        if options.format not in valid_formats:
            errors.append(f"Unknown format '{options.format}'. Supported: {', '.join(sorted(valid_formats))}")
        if not options.path:
            errors.append("Export path is required.")
        return errors

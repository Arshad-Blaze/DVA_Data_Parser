"""Requirement (Operation Selection) Layer.

Responsibility:
- Define the available operations for a workflow execution
- Wire registered DataOperations into the processing pipeline
- Support future operations without architectural changes

Supported operations:
    Raw Data Review     — preview raw data without aggregation
    Aggregate Only      — run store + item aggregation
    Aggregate + Calculate — aggregation + statistics + calculations
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import polars as pl

from dav_tool.operations import (
    IDataOperation, OperationResult, OperationOptions,
    get, list_operations, register,
    PreviewOperation, PreviewOptions,
    AggregateOperation, AggregateOptions,
    StatisticsOperation, StatisticsOptions,
)

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """The three supported operation types.

    Future operations can be added here without changing the architecture.
    """
    RAW_DATA_REVIEW = "raw_data_review"
    AGGREGATE_ONLY = "aggregate_only"
    AGGREGATE_CALCULATE = "aggregate_calculate"


OPERATION_LABELS = {
    OperationType.RAW_DATA_REVIEW: "Raw Data Review",
    OperationType.AGGREGATE_ONLY: "Aggregate Only",
    OperationType.AGGREGATE_CALCULATE: "Aggregate + Calculate",
}

OPERATION_DESCRIPTIONS = {
    OperationType.RAW_DATA_REVIEW: "Preview data without aggregation",
    OperationType.AGGREGATE_ONLY: "Run store and item aggregation",
    OperationType.AGGREGATE_CALCULATE: "Aggregation with statistics and calculations",
}


@dataclass
class RequirementConfig:
    """Configuration for the Requirement (Operation Selection) Layer.

    Stores the selected operation and any operation-specific options.
    """
    operation: OperationType = OperationType.AGGREGATE_CALCULATE
    preview_n_rows: int = 100
    aggregate_group_by: List[str] = field(default_factory=lambda: ["STORE_NUMBER"])
    aggregate_columns: List[str] = field(default_factory=lambda: ["Units", "Totalprice"])
    include_statistics: bool = True


def get_operation_type(label: str) -> OperationType:
    """Convert a UI label back to an OperationType."""
    for op_type, op_label in OPERATION_LABELS.items():
        if op_label == label:
            return op_type
    return OperationType.AGGREGATE_CALCULATE


def execute_requirement(
    df: pl.DataFrame,
    config: RequirementConfig,
) -> List[OperationResult]:
    """Execute the selected operation(s) on the canonical DataFrame.

    Returns a list of OperationResults (one per sub-operation).
    """
    results: List[OperationResult] = []

    if config.operation == OperationType.RAW_DATA_REVIEW:
        preview_op = PreviewOperation()
        preview_opts = PreviewOptions(
            mode="head",
            n_rows=config.preview_n_rows,
        )
        results.append(preview_op.execute(df, preview_opts))

    elif config.operation == OperationType.AGGREGATE_ONLY:
        agg_op = AggregateOperation()
        agg_opts = AggregateOptions(
            group_by=config.aggregate_group_by,
            aggregations={col: "sum" for col in config.aggregate_columns},
        )
        results.append(agg_op.execute(df, agg_opts))

    elif config.operation == OperationType.AGGREGATE_CALCULATE:
        agg_op = AggregateOperation()
        agg_opts = AggregateOptions(
            group_by=config.aggregate_group_by,
            aggregations={col: "sum" for col in config.aggregate_columns},
        )
        results.append(agg_op.execute(df, agg_opts))

        if config.include_statistics:
            stat_op = StatisticsOperation()
            stat_opts = StatisticsOptions(
                columns=config.aggregate_columns,
                top_n=5,
                include_memory=True,
            )
            results.append(stat_op.execute(df, stat_opts))

    return results


def list_available_operations() -> List[str]:
    """List all registered operations from the operations framework."""
    return list_operations()


def get_operation(name: str) -> Optional[IDataOperation]:
    """Get a registered operation by name."""
    return get(name)

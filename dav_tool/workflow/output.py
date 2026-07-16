"""Output Layer — standalone output generation service.

Produces OutputResult from context data.
UI receives OutputResult and renders it — no report logic in the UI.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import polars as pl


@dataclass
class OutputResult:
    """Contract produced by the Output Layer, consumed by the UI for rendering.

    Every field is pre-computed (DataFrames, CSV bytes, metrics, etc.)
    so the UI only needs to call ``st.dataframe()`` / ``st.download_button()``.
    """

    # ── Common ──
    metrics: Optional[Any] = None

    # ── Onboarding Validation Results ──
    compare_result: Optional[Dict[str, str]] = None
    upc_summary_df: Optional[pl.DataFrame] = None
    upc_summary_csv: Optional[str] = None
    file_review_df: Optional[pl.DataFrame] = None
    file_review_csv: Optional[str] = None

    # ── Existing Validation Results ──
    store_df: Optional[pl.DataFrame] = None
    store_df_csv: Optional[str] = None
    comparison_df: Optional[pl.DataFrame] = None
    comparison_df_csv: Optional[str] = None
    summary_df: Optional[pl.DataFrame] = None
    fr_prod: Optional[pl.DataFrame] = None
    fr_prod_csv: Optional[str] = None
    fr_test: Optional[pl.DataFrame] = None
    fr_test_csv: Optional[str] = None

    # ── Migration Report ──
    migration_metrics: Dict[str, Any] = field(default_factory=dict)
    schema_diff: Optional[Any] = None
    operation_compare: Optional[Any] = None
    migration_report_json: Optional[str] = None
    migration_recommendations: List[str] = field(default_factory=list)


def generate_onboarding_output(ctx) -> OutputResult:
    """Build OutputResult from an onboarding ProcessingContext."""
    result = OutputResult(metrics=ctx.metrics)

    if ctx.compare_result is not None:
        result.compare_result = ctx.compare_result

    if ctx.upc_summary is not None:
        result.upc_summary_df = ctx.upc_summary
        result.upc_summary_csv = ctx.upc_summary.write_csv()

    if ctx.file_review is not None and not ctx.file_review.is_empty():
        result.file_review_df = ctx.file_review
        result.file_review_csv = ctx.file_review.write_csv()

    return result


def generate_existing_output(ctx) -> OutputResult:
    """Build OutputResult from an existing-flow ExistingContext."""
    result = OutputResult(metrics=ctx.metrics)

    if ctx.store_df is not None and not ctx.store_df.is_empty():
        result.store_df = ctx.store_df
        result.store_df_csv = ctx.store_df.write_csv()

    if ctx.comparison_df is not None and not ctx.comparison_df.is_empty():
        result.comparison_df = ctx.comparison_df
        result.comparison_df_csv = ctx.comparison_df.write_csv()

    if ctx.summary_df is not None:
        result.summary_df = ctx.summary_df

    if ctx.compare_result is not None:
        result.compare_result = ctx.compare_result

    if ctx.fr_prod is not None and not ctx.fr_prod.is_empty():
        result.fr_prod = ctx.fr_prod
        result.fr_prod_csv = ctx.fr_prod.write_csv()

    if ctx.fr_test is not None and not ctx.fr_test.is_empty():
        result.fr_test = ctx.fr_test
        result.fr_test_csv = ctx.fr_test.write_csv()

    return result


def generate_migration_report(ctx) -> OutputResult:
    """Build OutputResult for the migration report phase."""
    from dav_tool.workflow.schema_comparison import compare_schemas
    from dav_tool.workflow.operation_comparison import compare_operations
    from dav_tool.workflow.migration_report import generate_report

    prod_cols = ctx.prod.schema or ctx.prod.columns or []
    test_cols = ctx.test.schema or ctx.test.columns or []
    sd = compare_schemas(prod_cols, test_cols)
    oc = compare_operations(
        ctx.prod.store_agg, ctx.test.store_agg,
        ctx.prod.item_agg, ctx.test.item_agg,
    )

    report = generate_report(
        prod_file_type=ctx.prod.file_type,
        test_file_type=ctx.test.file_type,
        prod_delimiter=ctx.prod.delimiter,
        test_delimiter=ctx.test.delimiter,
        prod_columns=prod_cols,
        test_columns=test_cols,
        store_missing_in_test=(ctx.compare_result or {}).get("missing_in_test", ""),
        store_missing_in_prod=(ctx.compare_result or {}).get("missing_in_prod", ""),
        errors=ctx.metrics.errors,
        warnings=ctx.metrics.warnings,
        rows_processed=ctx.metrics.rows_processed,
        total_execution_time=ctx.metrics.total_execution_time,
        peak_memory=ctx.metrics.peak_memory,
        operation_compare=oc,
        schema_diff=sd,
    )

    result = OutputResult(
        metrics=ctx.metrics,
        compare_result=ctx.compare_result,
        migration_metrics={
            "prod_columns": sd.prod_count,
            "test_columns": sd.test_count,
            "common_columns": len(sd.common),
            "new_in_test": len(sd.only_test),
            "prod_store_count": oc.prod_store_count,
            "test_store_count": oc.test_store_count,
            "prod_item_count": oc.prod_item_count,
            "test_item_count": oc.test_item_count,
        },
        schema_diff=sd,
        operation_compare=oc,
        migration_report_json=report.to_json(),
        migration_recommendations=report.recommendations,
    )

    return result

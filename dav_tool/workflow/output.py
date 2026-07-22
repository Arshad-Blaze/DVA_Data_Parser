"""Output Layer — standalone output generation service.

Produces OutputResult from context data.
UI receives OutputResult and renders it — no report logic in the UI.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import polars as pl

from dav_tool._observability import log_phase, print_memory_snapshot
from dav_tool._reports import generate_summary_analytics

logger = logging.getLogger(__name__)


def _metrics_dict(metrics) -> Optional[Dict[str, Any]]:
    """Convert a metrics object to a plain dict if it exists."""
    if metrics is None:
        return None
    return {
        "rows_processed": getattr(metrics, "rows_processed", 0),
        "total_execution_time": getattr(metrics, "total_execution_time", 0.0),
        "peak_memory": getattr(metrics, "peak_memory", 0.0),
        "peak_cpu": getattr(metrics, "peak_cpu", 0.0),
        "files_processed": getattr(metrics, "files_processed", 0),
    }


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

    # ── Summary Worksheets ──
    summary_kpis: Optional[pl.DataFrame] = None
    top_stores: Optional[pl.DataFrame] = None
    bottom_stores: Optional[pl.DataFrame] = None
    top_upcs: Optional[pl.DataFrame] = None
    bottom_upcs: Optional[pl.DataFrame] = None
    top_upcs_by_qty: Optional[pl.DataFrame] = None
    top_brands: Optional[pl.DataFrame] = None
    category_summary: Optional[pl.DataFrame] = None
    store_validation_summary: Optional[pl.DataFrame] = None

    # ── Migration Report ──
    migration_metrics: Dict[str, Any] = field(default_factory=dict)
    schema_diff: Optional[Any] = None
    operation_compare: Optional[Any] = None
    migration_report_json: Optional[str] = None
    migration_recommendations: List[str] = field(default_factory=list)


def generate_onboarding_output(ctx) -> OutputResult:
    """Build OutputResult from an onboarding ProcessingContext."""
    log_phase("Output (Onboarding) — STARTED")
    t0 = time.time()
    result = OutputResult(metrics=ctx.metrics)

    if ctx.compare_result is not None:
        result.compare_result = ctx.compare_result

    if ctx.upc_summary is not None:
        result.upc_summary_df = ctx.upc_summary
        result.upc_summary_csv = ctx.upc_summary.write_csv()

    if ctx.file_review is not None and not ctx.file_review.is_empty():
        result.file_review_df = ctx.file_review
        result.file_review_csv = ctx.file_review.write_csv()

    # Summary worksheets
    sheets = generate_summary_sheets(
        store_agg=ctx.store_agg,
        upc_summary=ctx.item_agg,
        item_comparison=None,
        store_diff=None,
        execution_metrics=_metrics_dict(ctx.metrics),
        prod_label="Retailer",
        test_label="Storelist",
    )
    if sheets:
        result.summary_kpis = sheets.get("summary_kpis")
        result.top_stores = sheets.get("top_stores")
        result.bottom_stores = sheets.get("bottom_stores")
        result.top_upcs = sheets.get("top_upcs")
        result.bottom_upcs = sheets.get("bottom_upcs")
        result.top_upcs_by_qty = sheets.get("top_upcs_by_qty")
        result.top_brands = sheets.get("top_brands")
        result.category_summary = sheets.get("category_summary")
        result.store_validation_summary = sheets.get("store_validation_summary")

    elapsed = time.time() - t0
    log_phase(f"Output (Onboarding) — COMPLETED in {elapsed:.2f}s")
    logger.info(
        "Output: upc_summary=%s file_review=%s sheets=%s",
        result.upc_summary_df is not None,
        result.file_review_df is not None,
        sheets is not None,
    )
    return result


def generate_existing_output(ctx) -> OutputResult:
    """Build OutputResult from an existing-flow ExistingContext."""
    log_phase("Output (Existing) — STARTED")
    t0 = time.time()
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

    # Summary worksheets
    sheets = generate_summary_sheets(
        store_agg=ctx.prod.store_agg,
        upc_summary=ctx.prod.item_agg,
        item_comparison=ctx.comparison_df,
        store_diff=ctx.store_df,
        execution_metrics=_metrics_dict(ctx.metrics),
        prod_label="BAU",
        test_label="TEST",
    )
    if sheets:
        result.summary_kpis = sheets.get("summary_kpis")
        result.top_stores = sheets.get("top_stores")
        result.bottom_stores = sheets.get("bottom_stores")
        result.top_upcs = sheets.get("top_upcs")
        result.bottom_upcs = sheets.get("bottom_upcs")
        result.top_upcs_by_qty = sheets.get("top_upcs_by_qty")
        result.top_brands = sheets.get("top_brands")
        result.category_summary = sheets.get("category_summary")
        result.store_validation_summary = sheets.get("store_validation_summary")

    elapsed = time.time() - t0
    log_phase(f"Output (Existing) — COMPLETED in {elapsed:.2f}s")
    logger.info(
        "Output: store_diff=%s comparison=%s sheets=%s",
        result.store_df is not None,
        result.comparison_df is not None,
        sheets is not None,
    )
    return result


def generate_summary_sheets(
    store_agg: Optional[pl.DataFrame] = None,
    upc_summary: Optional[pl.DataFrame] = None,
    item_comparison: Optional[pl.DataFrame] = None,
    store_diff: Optional[pl.DataFrame] = None,
    execution_metrics: Optional[Dict[str, Any]] = None,
    prod_label: str = "BAU",
    test_label: str = "TEST",
) -> Optional[Dict[str, pl.DataFrame]]:
    """Generate summary worksheets from pre-computed aggregation results.

    Returns a dict with keys ``summary_kpis``, ``top_stores``, ``bottom_stores``,
    ``top_upcs``, ``bottom_upcs``, ``top_brands``, ``category_summary``,
    ``    store_validation_summary``, or None if no data.
    """
    kpis = generate_summary_analytics(
        prod_store_agg=store_agg,
        test_store_agg=None,
        prod_upc_summary=upc_summary,
        test_upc_summary=None,
        prod_item_comparison=item_comparison,
        store_diff=store_diff,
        execution_metrics=execution_metrics,
        prod_label=prod_label,
        test_label=test_label,
    )
    if kpis.is_empty():
        return None

    sheets: Dict[str, pl.DataFrame] = {"summary_kpis": kpis}

    # Top/bottom stores
    if store_agg is not None and not store_agg.is_empty():
        sf = store_agg.filter(pl.col("Units").is_not_null())
        if "Totalprice" in sf.columns and "Units" in sf.columns:
            sheets["top_stores"] = pl.concat([
                sf.top_k(10, by="Totalprice").with_columns(pl.lit("Sales").alias("rank_by")),
                sf.top_k(10, by="Units").with_columns(pl.lit("Quantity").alias("rank_by")),
            ])
            sheets["bottom_stores"] = pl.concat([
                sf.bottom_k(10, by="Totalprice").with_columns(pl.lit("Sales").alias("rank_by")),
                sf.bottom_k(10, by="Units").with_columns(pl.lit("Quantity").alias("rank_by")),
            ])

    # Top/bottom UPCs
    if upc_summary is not None and not upc_summary.is_empty():
        if "TOTAL_DOLLARS" in upc_summary.columns:
            sheets["top_upcs"] = upc_summary.top_k(10, by="TOTAL_DOLLARS").with_columns(
                pl.lit("Top").alias("rank")
            )
            sheets["bottom_upcs"] = upc_summary.bottom_k(10, by="TOTAL_DOLLARS").with_columns(
                pl.lit("Bottom").alias("rank")
            )
        if "UNITS_SOLD" in upc_summary.columns:
            sheets["top_upcs_by_qty"] = upc_summary.top_k(10, by="UNITS_SOLD").with_columns(
                pl.lit("Top Qty").alias("rank")
            )

    # Top brands (when enriched schema provides Brand column)
    if upc_summary is not None and not upc_summary.is_empty():
        if "Brand" in upc_summary.columns:
            brands = upc_summary.group_by("Brand").agg([
                pl.sum("UNITS_SOLD").alias("Total Units"),
                pl.sum("TOTAL_DOLLARS").alias("Total Sales"),
                pl.count().alias("UPC Count"),
            ]).sort("Total Sales", descending=True)
            sheets["top_brands"] = brands

    # Category summary (grouped by description)
    if upc_summary is not None and not upc_summary.is_empty():
        if "PRODUCT_DESCRIPTION" in upc_summary.columns:
            cat = upc_summary.group_by("PRODUCT_DESCRIPTION").agg([
                pl.sum("UNITS_SOLD").alias("Total Units"),
                pl.sum("TOTAL_DOLLARS").alias("Total Sales"),
                pl.count().alias("UPC Count"),
            ]).sort("Total Sales", descending=True)
            sheets["category_summary"] = cat

    # Store validation summary
    if store_diff is not None and not store_diff.is_empty():
        if "Units_Diff_%" in store_diff.columns and "Sales_Diff_%" in store_diff.columns:
            summary_df = store_diff.select([
                pl.col("STORE_NUMBER"),
                pl.col("Units_Diff_%").alias("Units Variance %"),
                pl.col("Sales_Diff_%").alias("Sales Variance %"),
            ])
        else:
            summary_df = store_diff.select([
                pl.col(c) for c in store_diff.columns if c != "STORE_NUMBER"
            ])
        sheets["store_validation_summary"] = summary_df

    return sheets


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

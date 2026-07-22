"""Validation Service — validation orchestration.

Moved from UI layer (onboarding.py:738-820, existing.py:1145-1265).
No Streamlit imports. No rendering. Pure validation logic.
"""
import logging
import os
import time
from typing import Optional, Dict, List

import polars as pl

from dav_tool.datasource.manager import get_active_source
from dav_tool.io import safe_read_csv
from dav_tool.options import ParseOptions, ColumnMapping, ValidationOptions
from dav_tool.validation.store import compare_files, storelevelvalidation
from dav_tool.validation.item import run_item_validation
from dav_tool._reports import generate_file_review
from dav_tool._observability import ProcessingMetrics
from dav_tool.datasource.base import IDataSource
from dav_tool.workflow.data_access import wrap_source

logger = logging.getLogger(__name__)


def _wrap_validation_source(source, *path_lists):
    """Wrap source in DataAccessor for validation functions."""
    if source is None:
        return None
    all_paths = []
    for paths in path_lists:
        if paths:
            all_paths.extend(p for p in paths if p not in all_paths)
    if not all_paths:
        return source
    accessor, _ = wrap_source(source, all_paths)
    return accessor


class ValidationResult:
    """Container for all validation results."""

    def __init__(self):
        self.store_comparison: Optional[pl.DataFrame] = None
        self.item_comparison: Optional[pl.DataFrame] = None
        self.item_summary: Optional[pl.DataFrame] = None
        self.store_list_result: Optional[Dict[str, str]] = None
        self.file_review: Optional[pl.DataFrame] = None
        self.file_review_test: Optional[pl.DataFrame] = None
        self.upc_summary: Optional[pl.DataFrame] = None
        self.errors: list = []
        self.warnings: list = []


def run_onboarding_validation(
    file_paths,
    parse_opts: ParseOptions,
    mapping: ColumnMapping,
    store_agg: Optional[pl.DataFrame],
    item_agg: Optional[pl.DataFrame],
    validation_opts: ValidationOptions,
    metrics: ProcessingMetrics,
    source: Optional[IDataSource] = None,
) -> ValidationResult:
    """Run onboarding validations. Pure logic, no UI."""
    source = _wrap_validation_source(source, file_paths)
    result = ValidationResult()

    if validation_opts.run_compare_store_list:
        result.store_list_result = _run_store_list_compare(
            store_agg, validation_opts, source=source,
        )

    if validation_opts.run_item_validation and item_agg is not None:
        result.upc_summary = item_agg

    if validation_opts.run_file_review:
        try:
            fr, elapsed = _generate_single_file_review(
                file_paths, parse_opts, mapping,
                precomputed_store_agg=store_agg,
                precomputed_upc_summary=item_agg,
                source=source,
            )
            result.file_review = fr
            metrics.record("report", "generate_file_review", elapsed)
        except Exception as e:
            result.errors.append(f"File review failed: {e}")
            logger.error("File review failed: %s", str(e), exc_info=True)

    return result


def run_existing_validation(
    prod_paths, test_paths,
    prod_parse: ParseOptions, test_parse: ParseOptions,
    prod_mapping: ColumnMapping, test_mapping: ColumnMapping,
    prod_store_agg: Optional[pl.DataFrame],
    test_store_agg: Optional[pl.DataFrame],
    prod_item_agg: Optional[pl.DataFrame],
    test_item_agg: Optional[pl.DataFrame],
    validation_opts: ValidationOptions,
    metrics: ProcessingMetrics,
    source: Optional[IDataSource] = None,
) -> ValidationResult:
    """Run existing (two-sided) validations. Pure logic, no UI."""
    source = _wrap_validation_source(source, prod_paths, test_paths)
    result = ValidationResult()

    if validation_opts.run_store_validation:
        try:
            store_df, elapsed = _run_store_validation(
                prod_paths, test_paths, prod_parse, test_parse,
                prod_mapping, test_mapping,
                prod_store_agg, test_store_agg,
                source=source,
            )
            result.store_comparison = store_df
            metrics.record("validation", "storelevelvalidation", elapsed)
        except Exception as e:
            result.errors.append(f"Store validation failed: {e}")
            logger.error("Store validation failed: %s", str(e), exc_info=True)

    if validation_opts.run_item_validation:
        try:
            comparison_df, summary_df, elapsed = _run_item_validation(
                prod_paths, test_paths, prod_parse, test_parse,
                prod_mapping, test_mapping,
                prod_item_agg, test_item_agg,
                source=source,
            )
            result.item_comparison = comparison_df
            result.item_summary = summary_df
            metrics.record("validation", "run_item_validation", elapsed)
        except Exception as e:
            result.errors.append(f"Item validation failed: {e}")
            logger.error("Item validation failed: %s", str(e), exc_info=True)

    if validation_opts.run_compare_store_list:
        result.store_list_result = _run_store_list_compare_both(
            prod_store_agg, test_store_agg,
        )

    if validation_opts.run_file_review:
        try:
            fr_prod, fr_test, elapsed = _generate_both_file_reviews(
                prod_paths, test_paths, prod_parse, test_parse,
                prod_mapping, test_mapping,
                prod_store_agg, prod_item_agg,
                test_store_agg, test_item_agg,
                source=source,
            )
            result.file_review = fr_prod
            result.file_review_test = fr_test
            metrics.record("report", "generate_file_reviews", elapsed)
        except Exception as e:
            result.errors.append(f"File review failed: {e}")
            logger.error("File review failed: %s", str(e), exc_info=True)

    return result


def _run_store_list_compare(store_agg, validation_opts, source=None):
    """Compare store list against aggregated stores."""
    if store_agg is None or store_agg.is_empty():
        return {"missing_in_test": "", "missing_in_prod": ""}
    if not validation_opts.store_list_path:
        return {"missing_in_test": "", "missing_in_prod": ""}

    _source = source or get_active_source()
    local_path = validation_opts.store_list_path
    if _source is not None:
        try:
            local_path = _source.download_if_required(validation_opts.store_list_path)
        except Exception as e:
            logger.warning("Failed to download storelist via source for %s: %s",
                           validation_opts.store_list_path, e)
    ext = os.path.splitext(local_path)[-1].lower()
    if ext in [".xlsx", ".xls"]:
        storelist_df = pl.read_excel(local_path)
    else:
        storelist_df = safe_read_csv(
            local_path, separator=validation_opts.store_list_delimiter,
        )
    prod_series = store_agg.select(["STORE_NUMBER"])
    return compare_files(
        prod_series.to_series().to_frame("store"),
        storelist_df.select([pl.col(validation_opts.store_list_store_col).alias("store")]),
        "store", "store",
    )


def _run_store_list_compare_both(prod_store_agg, test_store_agg, store_col: str = "STORE_NUMBER"):
    """Compare store lists between BAU and Test.

    *store_col* is the canonical column name in aggregated DataFrames
    (default matches the normalizer output).
    """
    if prod_store_agg is None or test_store_agg is None:
        return {"missing_in_test": "", "missing_in_prod": ""}

    prod_series = prod_store_agg.select([store_col])
    test_series = test_store_agg.select([store_col])

    if not prod_series.is_empty() and not test_series.is_empty():
        return compare_files(
            prod_series.to_series().to_frame("store"),
            test_series.to_series().to_frame("store"),
            "store", "store",
        )
    return {"missing_in_test": "", "missing_in_prod": ""}


def _run_store_validation(
    prod_paths, test_paths, prod_parse, test_parse,
    prod_mapping, test_mapping,
    prod_store_agg, test_store_agg,
    source=None,
):
    """Run store-level validation between BAU and Test."""
    t0 = time.perf_counter()
    store_df = storelevelvalidation(
        prod_paths, test_paths,
        prod_parse.file_type, test_parse.file_type,
        prod_parse.delimiter, test_parse.delimiter,
        prod_parse.layout, test_parse.layout,
        prod_mapping.store, prod_mapping.units, prod_mapping.price,
        test_mapping.store, test_mapping.units, test_mapping.price,
        prod_mapping.price_type, test_mapping.price_type,
        prod_mapping.implied_dollars, prod_mapping.implied_units,
        test_mapping.implied_dollars, test_mapping.implied_units,
        start_line=prod_parse.start_line, record_type=prod_parse.record_type,
        multiline_record_types=prod_parse.multiline_record_types,
        multiline_delimiter=prod_parse.multiline_delimiter,
        column_names=prod_parse.column_names,
        header_prefix=prod_parse.header_prefix,
        header_layout=prod_parse.header_layout,
        trailer_prefix=prod_parse.trailer_prefix,
        trailer_layout=prod_parse.trailer_layout,
        prod_summary=prod_store_agg,
        test_summary=test_store_agg,
        aggregation_source=source,
    )
    elapsed = time.perf_counter() - t0
    return store_df, elapsed


def _run_item_validation(
    prod_paths, test_paths, prod_parse, test_parse,
    prod_mapping, test_mapping,
    prod_item_agg, test_item_agg,
    source=None,
):
    """Run item-level validation between BAU and Test."""
    t0 = time.perf_counter()
    comparison_df, summary_df = run_item_validation(
        prod_paths, test_paths,
        prod_parse.file_type, test_parse.file_type,
        prod_parse.delimiter, test_parse.delimiter,
        prod_parse.layout, test_parse.layout,
        prod_mapping.upc, prod_mapping.description,
        prod_mapping.units, prod_mapping.price,
        implied_units_bau=prod_mapping.implied_units,
        implied_dollars_bau=prod_mapping.implied_dollars,
        implied_units_test=test_mapping.implied_units,
        implied_dollars_test=test_mapping.implied_dollars,
        start_line=prod_parse.start_line, record_type=prod_parse.record_type,
        multiline_record_types=prod_parse.multiline_record_types,
        multiline_delimiter=prod_parse.multiline_delimiter,
        column_names=prod_parse.column_names,
        header_prefix=prod_parse.header_prefix,
        header_layout=prod_parse.header_layout,
        trailer_prefix=prod_parse.trailer_prefix,
        trailer_layout=prod_parse.trailer_layout,
        bau_summary=prod_item_agg,
        test_summary=test_item_agg,
        aggregation_source=source,
    )
    elapsed = time.perf_counter() - t0
    return comparison_df, summary_df, elapsed


def _generate_single_file_review(
    file_paths, parse_opts, mapping, source=None,
    precomputed_store_agg=None, precomputed_upc_summary=None,
):
    """Generate file review for a single side.

    Accepts pre-computed summaries to avoid layer bypass (re-parsing at
    the report layer).  The caller (``run_onboarding_validation``) already
    has these from the Operation Layer.
    """
    t0 = time.perf_counter()
    fr = generate_file_review(
        file_paths, parse_opts.file_type,
        mapping.store, mapping.upc, mapping.units, mapping.price,
        delimiter=parse_opts.delimiter,
        layout=parse_opts.layout,
        price_type=mapping.price_type,
        implied_dollars=mapping.implied_dollars,
        implied_units=mapping.implied_units,
        start_line=parse_opts.start_line,
        record_type=parse_opts.record_type,
        multiline_record_types=parse_opts.multiline_record_types,
        multiline_delimiter=parse_opts.multiline_delimiter,
        column_names=parse_opts.column_names,
        header_prefix=parse_opts.header_prefix,
        header_layout=parse_opts.header_layout,
        trailer_prefix=parse_opts.trailer_prefix,
        trailer_layout=parse_opts.trailer_layout,
        precomputed_store_agg=precomputed_store_agg,
        precomputed_upc_summary=precomputed_upc_summary,
        source=source,
        quantity_type=mapping.quantity_type,
        weight_col=mapping.weight_col,
        weight_uom=mapping.weight_uom,
        weight_uom_col=mapping.weight_uom_col,
    )
    elapsed = time.perf_counter() - t0
    return fr, elapsed


def _generate_both_file_reviews(
    prod_paths, test_paths, prod_parse, test_parse,
    prod_mapping, test_mapping,
    prod_store_agg, prod_item_agg,
    test_store_agg, test_item_agg,
    source=None,
):
    """Generate file reviews for both sides."""
    t0 = time.perf_counter()
    fr_prod = generate_file_review(
        prod_paths, prod_parse.file_type,
        prod_mapping.store, prod_mapping.upc,
        prod_mapping.units, prod_mapping.price,
        delimiter=prod_parse.delimiter,
        layout=prod_parse.layout,
        price_type=prod_mapping.price_type,
        implied_dollars=prod_mapping.implied_dollars,
        implied_units=prod_mapping.implied_units,
        start_line=prod_parse.start_line,
        record_type=prod_parse.record_type,
        multiline_record_types=prod_parse.multiline_record_types,
        multiline_delimiter=prod_parse.multiline_delimiter,
        column_names=prod_parse.column_names,
        header_prefix=prod_parse.header_prefix,
        header_layout=prod_parse.header_layout,
        trailer_prefix=prod_parse.trailer_prefix,
        trailer_layout=prod_parse.trailer_layout,
        precomputed_store_agg=prod_store_agg,
        precomputed_upc_summary=prod_item_agg,
        source=source,
        quantity_type=prod_mapping.quantity_type,
        weight_col=prod_mapping.weight_col,
        weight_uom=prod_mapping.weight_uom,
        weight_uom_col=prod_mapping.weight_uom_col,
    )
    fr_test = generate_file_review(
        test_paths, test_parse.file_type,
        test_mapping.store, test_mapping.upc,
        test_mapping.units, test_mapping.price,
        delimiter=test_parse.delimiter,
        layout=test_parse.layout,
        price_type=test_mapping.price_type,
        implied_dollars=test_mapping.implied_dollars,
        implied_units=test_mapping.implied_units,
        start_line=test_parse.start_line,
        record_type=test_parse.record_type,
        multiline_record_types=test_parse.multiline_record_types,
        multiline_delimiter=test_parse.multiline_delimiter,
        column_names=test_parse.column_names,
        header_prefix=test_parse.header_prefix,
        header_layout=test_parse.header_layout,
        trailer_prefix=test_parse.trailer_prefix,
        trailer_layout=test_parse.trailer_layout,
        precomputed_store_agg=test_store_agg,
        precomputed_upc_summary=test_item_agg,
        source=source,
        quantity_type=test_mapping.quantity_type,
        weight_col=test_mapping.weight_col,
        weight_uom=test_mapping.weight_uom,
        weight_uom_col=test_mapping.weight_uom_col,
    )
    elapsed = time.perf_counter() - t0
    return fr_prod, fr_test, elapsed

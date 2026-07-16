"""Workflow orchestration — moves business orchestration out of UI.

Sprint 1-2 of the Architecture Recovery Sprint.
Every processing path passes through the Operation Layer.
UI responsibilities: display controls, collect input, show progress, render OutputResult.
Workflow responsibilities: build contracts, call layers, manage execution, handle transitions.

RC2: ExecutionEngine wraps all operation dispatch.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ENGINE: Optional["ExecutionEngine"] = None


def _get_engine():
    """Lazy singleton for the ExecutionEngine."""
    global _ENGINE
    if _ENGINE is None:
        from dav_tool.workflow.execution import ExecutionEngine
        _ENGINE = ExecutionEngine()
    return _ENGINE


def run_onboarding_processing(ctx, source=None):
    """Run the 'aggregate' operation via the ExecutionEngine."""
    _get_engine().run(ctx, source=source)


def run_existing_processing(ctx, source=None):
    """Run the 'format_change' operation via the ExecutionEngine."""
    _get_engine().run(ctx, source=source)


def run_onboarding_validation(
    ctx,
    file_paths, file_type, prod_delim, layout_list, start_line, record_type,
    prod_store_col, prod_upc_col, prod_desc_col, prod_units_col, prod_price_col,
    storelist_path, storelist_delim, storelist_store_col,
    run_onb_compare, run_upc_summary, run_onb_file_review,
    header_prefix=None, header_layout=None,
    trailer_prefix=None, trailer_layout=None,
    source=None,
):
    """Build contracts, run validation, store results on ctx."""
    from dav_tool.options import ParseOptions, ColumnMapping, ValidationOptions
    from dav_tool.workflow.validation import run_onboarding_validation as _run_validation

    parse_opts = ParseOptions(
        file_type=file_type, delimiter=prod_delim,
        start_line=start_line, record_type=record_type,
        layout=layout_list, column_names=ctx.schema,
        header_prefix=header_prefix, header_layout=header_layout,
        trailer_prefix=trailer_prefix, trailer_layout=trailer_layout,
        multiline_record_types=ctx.ml_record_types,
        multiline_delimiter=ctx.ml_delimiter,
    )
    mapping = ColumnMapping(
        store=prod_store_col, upc=prod_upc_col, description=prod_desc_col,
        units=prod_units_col, price=prod_price_col,
    )
    val_opts = ValidationOptions(
        run_store_validation=False,
        run_item_validation=False,
        run_compare_store_list=run_onb_compare,
        run_summary=False,
        run_file_review=run_onb_file_review,
        store_list_path=storelist_path,
        store_list_delimiter=storelist_delim,
        store_list_store_col=storelist_store_col,
    )

    val_result = _run_validation(
        file_paths, parse_opts, mapping,
        store_agg=ctx.store_agg,
        item_agg=ctx.item_agg,
        validation_opts=val_opts,
        metrics=ctx.metrics,
        source=source,
    )

    if run_onb_compare:
        ctx.compare_result = val_result.store_list_result
    if run_upc_summary and ctx.item_agg is not None:
        ctx.upc_summary = ctx.item_agg
    if run_onb_file_review:
        ctx.file_review = val_result.file_review


def run_existing_validation(
    ctx,
    prod_paths, test_paths,
    prod_type, test_type,
    prod_delim, test_delim,
    prod_layout_list, test_layout_list,
    prod_start_line, test_start_line,
    prod_record_type, test_record_type,
    prod_store_col, prod_units_col, prod_price_col, prod_upc_col, prod_desc_col,
    test_store_col, test_units_col, test_price_col, test_upc_col, test_desc_col,
    price_type_bau, price_type_test,
    isimplied_dollars_prod, isimplied_units_prod,
    isimplied_dollars_test, isimplied_units_test,
    run_store, run_item, run_compare_existing, run_summary, run_file_review_existing,
    trailer_prefix_prod=None, trailer_layout_prod=None,
    trailer_prefix_test=None, trailer_layout_test=None,
    source=None,
):
    """Build contracts, run validation, store results on ctx."""
    from dav_tool.options import ParseOptions, ColumnMapping, ValidationOptions
    from dav_tool.workflow.validation import run_existing_validation as _run_validation

    prod_parse = ParseOptions(
        file_type=prod_type, delimiter=prod_delim,
        start_line=prod_start_line, record_type=prod_record_type,
        layout=ctx.prod.eff_layout or prod_layout_list, column_names=ctx.prod.schema,
        header_prefix=ctx.prod.header_prefix, header_layout=ctx.prod.header_layout,
        detail_layout=ctx.prod.detail_layout,
        trailer_prefix=trailer_prefix_prod, trailer_layout=trailer_layout_prod,
        multiline_record_types=(
            ctx.prod.ml_record_types
            if prod_type == "multiline" and not ctx.prod.header_prefix
            else None
        ),
        multiline_delimiter=ctx.ml_delimiter,
    )
    test_parse = ParseOptions(
        file_type=test_type, delimiter=test_delim,
        start_line=test_start_line, record_type=test_record_type,
        layout=ctx.test.eff_layout or test_layout_list, column_names=ctx.test.schema,
        header_prefix=ctx.test.header_prefix, header_layout=ctx.test.header_layout,
        detail_layout=ctx.test.detail_layout,
        trailer_prefix=trailer_prefix_test, trailer_layout=trailer_layout_test,
        multiline_record_types=(
            ctx.test.ml_record_types
            if test_type == "multiline" and not ctx.test.header_prefix
            else None
        ),
        multiline_delimiter=ctx.ml_delimiter,
    )
    prod_mapping = ColumnMapping(
        store=prod_store_col, upc=prod_upc_col, description=prod_desc_col,
        units=prod_units_col, price=prod_price_col,
        price_type=price_type_bau,
        implied_dollars=isimplied_dollars_prod, implied_units=isimplied_units_prod,
    )
    test_mapping = ColumnMapping(
        store=test_store_col, upc=test_upc_col, description=test_desc_col,
        units=test_units_col, price=test_price_col,
        price_type=price_type_test,
        implied_dollars=isimplied_dollars_test, implied_units=isimplied_units_test,
    )
    val_opts = ValidationOptions(
        run_store_validation=run_store,
        run_item_validation=run_item,
        run_compare_store_list=run_compare_existing,
        run_summary=run_summary,
        run_file_review=run_file_review_existing,
    )

    ctx.compare_result = None
    ctx.store_df = None
    ctx.comparison_df = None
    ctx.summary_df = None

    val_result = _run_validation(
        prod_paths, test_paths,
        prod_parse, test_parse,
        prod_mapping, test_mapping,
        prod_store_agg=ctx.prod.store_agg, test_store_agg=ctx.test.store_agg,
        prod_item_agg=ctx.prod.item_agg, test_item_agg=ctx.test.item_agg,
        validation_opts=val_opts,
        metrics=ctx.metrics,
        source=source,
    )

    if val_result.store_comparison is not None:
        ctx.store_df = val_result.store_comparison
    if val_result.item_comparison is not None:
        ctx.comparison_df = val_result.item_comparison
    if val_result.item_summary is not None:
        ctx.summary_df = val_result.item_summary
    if val_result.store_list_result is not None:
        ctx.compare_result = val_result.store_list_result
    if val_result.file_review is not None:
        ctx.fr_prod = val_result.file_review
    if val_result.file_review_test is not None:
        ctx.fr_test = val_result.file_review_test

    for err in val_result.errors:
        ctx.metrics.errors.append(err)

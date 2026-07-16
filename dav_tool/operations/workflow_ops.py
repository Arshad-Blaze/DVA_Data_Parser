"""Workflow-level operations — registered implementations of ``WorkflowOperation``.

Each operation encapsulates a complete workflow phase (aggregation, validation, etc.)
and implements the ``WorkflowOperation`` protocol.  The ``OperationExecutor``
dispatches via the registry — no hard-coded branching.

Adding a new workflow operation:
    1. Create a class implementing ``WorkflowOperation``
    2. Register it via ``register_workflow_op()``
    3. No ``OperationExecutor`` changes needed
"""
import concurrent.futures
import logging

from dav_tool.operations.base import WorkflowOperation

logger = logging.getLogger(__name__)


class AggregateWorkflowOp:
    """Single-side store + item aggregation (onboarding)."""

    operation_type = "aggregate"

    def execute(self, op_ctx) -> None:
        from dav_tool.options import ParseOptions, ColumnMapping
        from dav_tool.workflow.processing import run_store_aggregation, run_item_aggregation

        ctx = op_ctx.ctx
        parse_opts = ParseOptions.from_context(ctx)
        mapping = ColumnMapping.from_context(ctx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            futs = [
                ex.submit(run_store_aggregation, ctx.file_paths, parse_opts, mapping, source=op_ctx.source),
                ex.submit(run_item_aggregation, ctx.file_paths, parse_opts, mapping, source=op_ctx.source),
            ]
            names = ["stream_store_aggregate", "stream_item_aggregate"]
            results = []
            for i, future in enumerate(futs):
                result, elapsed = future.result(timeout=600)
                ctx.metrics.record("aggregation", names[i], elapsed)
                results.append(result)

        ctx.store_agg, ctx.item_agg = results


class FormatChangeWorkflowOp:
    """Two-sided store + item aggregation (existing / format change).
    
    Runs 4 parallel aggregations: BAU store, Test store, BAU item, Test item.
    """

    operation_type = "format_change"

    def execute(self, op_ctx) -> None:
        from dav_tool.options import ParseOptions, ColumnMapping
        from dav_tool.workflow.processing import run_store_aggregation, run_item_aggregation

        ctx = op_ctx.ctx
        ml_delim_val = ctx.ml_delimiter
        prod_type = ctx.prod.file_type
        test_type = ctx.test.file_type

        prod_parse = ParseOptions(
            file_type=prod_type, delimiter=ctx.prod.delimiter,
            start_line=ctx.prod.start_line, record_type=ctx.prod.record_type,
            layout=ctx.prod.layout, column_names=ctx.prod.schema,
            header_prefix=ctx.prod.header_prefix, header_layout=ctx.prod.header_layout,
            detail_layout=ctx.prod.detail_layout,
            trailer_prefix=ctx.prod.trailer_prefix, trailer_layout=ctx.prod.trailer_layout,
            multiline_record_types=(
                ctx.prod.ml_record_types
                if prod_type == "multiline" and not ctx.prod.header_prefix
                else None
            ),
            multiline_delimiter=ml_delim_val,
        )
        prod_mapping = ColumnMapping.from_context(ctx.prod)

        test_parse = ParseOptions(
            file_type=test_type, delimiter=ctx.test.delimiter,
            start_line=ctx.test.start_line, record_type=ctx.test.record_type,
            layout=ctx.test.layout, column_names=ctx.test.schema,
            header_prefix=ctx.test.header_prefix, header_layout=ctx.test.header_layout,
            detail_layout=ctx.test.detail_layout,
            trailer_prefix=ctx.test.trailer_prefix, trailer_layout=ctx.test.trailer_layout,
            multiline_record_types=(
                ctx.test.ml_record_types
                if test_type == "multiline" and not ctx.test.header_prefix
                else None
            ),
            multiline_delimiter=ml_delim_val,
        )
        test_mapping = ColumnMapping.from_context(ctx.test)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = [
                ex.submit(run_store_aggregation, ctx.prod.file_paths, prod_parse, prod_mapping, source=op_ctx.source),
                ex.submit(run_store_aggregation, ctx.test.file_paths, test_parse, test_mapping, source=op_ctx.source),
                ex.submit(run_item_aggregation, ctx.prod.file_paths, prod_parse, prod_mapping, source=op_ctx.source),
                ex.submit(run_item_aggregation, ctx.test.file_paths, test_parse, test_mapping, source=op_ctx.source),
            ]
            names = [
                "BAU stream_store_aggregate", "Test stream_store_aggregate",
                "BAU stream_item_aggregate", "Test stream_item_aggregate",
            ]
            results = []
            for i, future in enumerate(futs):
                try:
                    result, elapsed = future.result(timeout=600)
                    ctx.metrics.record("aggregation", names[i], elapsed)
                    results.append(result)
                except Exception as e:
                    logger.error("%s failed: %s", names[i], str(e), exc_info=True)
                    raise

            prod_store_agg, test_store_agg, prod_item_agg, test_item_agg = results

        ctx.prod.store_agg = prod_store_agg
        ctx.test.store_agg = test_store_agg
        ctx.prod.item_agg = prod_item_agg
        ctx.test.item_agg = test_item_agg

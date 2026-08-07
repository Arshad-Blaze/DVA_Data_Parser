"""Transformation Engine — executes a TransformationPlan against raw records.

The Transformation Engine sits between the Transformation Planner and the
Parser Pipeline:

    Discovery → DatasetGraph → TransformationPlan → TransformationEngine →
    TransformedDataset → Parser Pipeline → ParsedDataset

It owns ALL record reshaping: header removal, trailer removal, metadata
removal, flattening (parent replication + child expansion), record selection,
and relationship joins.  Parsers consume the resulting
:class:`TransformedDataset` and never see raw file structure.

The engine performs NO parsing — it only transforms records.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import polars as pl

from dav_tool.workflow.discovery import DiscoveryResult

from .contracts import TransformedDataset, TransformationPlan

logger = logging.getLogger(__name__)


class TransformationEngine:
    """Executes a TransformationPlan to produce a TransformedDataset."""

    name = "transformation_engine"

    def execute(
        self,
        discovery: DiscoveryResult,
        plan: TransformationPlan,
        source=None,
    ) -> TransformedDataset:
        """Execute *plan* against the files described by *discovery*."""
        if plan is None:
            raise ValueError("A TransformationPlan is required.")

        warnings: List[str] = []
        operations: List[str] = []

        records = _flatten_records(discovery, plan, source, operations, warnings)
        records = _apply_joins(records, discovery, plan, source, operations, warnings)

        return TransformedDataset(
            records=records,
            record_types=tuple(_surviving_record_types(discovery, plan)),
            layout=_layout(discovery),
            operations=tuple(operations),
            join_operations=tuple(plan.join_operations),
            metadata={
                "file_type": discovery.file_type,
                "delimiter": discovery.delimiter,
                "header_removal": plan.header_removal,
                "trailer_removal": list(plan.trailer_removal),
                "metadata_removal": list(plan.metadata_removal),
            },
            warnings=tuple(warnings),
            discovery=discovery,
        )


# ── Flattening ────────────────────────────────────────────────────────


def _flatten_records(
    discovery: DiscoveryResult,
    plan: TransformationPlan,
    source,
    operations: List[str],
    warnings: List[str],
) -> pl.DataFrame:
    """Produce the primary record frame.

    For multiline/record-based files the plan's flatten operations are
    executed (parent replication + child expansion).  Flat delimited files
    require no flattening.
    """
    from dav_tool._parsers import (
        flatten_multiline_chunks,
        flatten_multiline_fixed_width,
    )

    file_paths = list(discovery.file_paths or [])
    if not file_paths:
        warnings.append("No input files to transform.")
        return pl.DataFrame()

    file_type = discovery.file_type or "delimited"

    if file_type == "multiline" and plan.flatten_operations:
        operations.append("flatten_hierarchy")
        op = plan.flatten_operations[0]
        parent = op.get("parent")
        children = op.get("children") or []
        record_types = ([parent] if parent else []) + list(children)
        if not record_types:
            record_types = list(op.get("hierarchy", {}).keys()) or discovery.ml_record_types or ["H", "D"]
        delimiter = discovery.delimiter or "|"
        if _uses_fixed_layout(discovery):
            return _flatten_fixed(discovery, plan, source, operations, warnings)
        try:
            chunks = list(flatten_multiline_chunks(
                file_paths, record_types, delimiter=delimiter, source=source,
            ))
            return pl.concat(chunks) if chunks else pl.DataFrame()
        except Exception as exc:  # noqa: BLE001 — surface as warning, keep pipeline alive
            logger.warning("Multiline flatten failed: %s", exc)
            warnings.append(f"Multiline flatten failed: {exc}")
            return pl.DataFrame()

    if file_type in ("fixed", "multiline") and (plan.child_expansion or discovery.header_prefix):
        if plan.flatten_operations or plan.child_expansion:
            operations.append("flatten_fixed_width")
            return _flatten_fixed(discovery, plan, source, operations, warnings)

    if plan.header_removal:
        operations.append("header_removal")

    # Flat delimited: strip leading header/metadata lines, parse the rest.
    # parse_delimited_chunks treats the first remaining line as the schema.
    from dav_tool._parsers import _rows_to_df

    delimiter = discovery.delimiter or ","
    skip = plan.header_removal or 0
    from dav_tool._parsers import _open_text_stream

    all_chunks: List[pl.DataFrame] = []
    for file_path in file_paths:
        with _open_text_stream(file_path, source) as f:
            lines = [ln.rstrip("\n\r") for ln in f]
        lines = [ln for ln in lines if ln]
        if skip:
            lines = lines[skip:]
        if not lines:
            continue
        header = lines[0].split(delimiter)
        rows = [ln.split(delimiter) for ln in lines[1:]]
        all_chunks.append(_rows_to_df(rows, header))
    return pl.concat(all_chunks) if all_chunks else pl.DataFrame()


def _flatten_fixed(
    discovery: DiscoveryResult,
    plan: TransformationPlan,
    source,
    operations: List[str],
    warnings: List[str],
) -> pl.DataFrame:
    from dav_tool._parsers import flatten_multiline_fixed_width

    file_paths = list(discovery.file_paths or [])
    header = discovery.header_prefix
    detail_layout = discovery.detail_layout or discovery.candidate_layout
    header_layout = plan.metadata.get("header_layout") if hasattr(plan, "metadata") else None
    try:
        chunks = list(flatten_multiline_fixed_width(
            file_paths,
            header or plan.parent_replication[0] if plan.parent_replication else "",
            header_layout or detail_layout or [],
            detail_layout or [],
            trailer_prefix=discovery.trailer_prefix or (
                plan.trailer_removal[0] if plan.trailer_removal else None
            ),
            source=source,
        ))
        return pl.concat(chunks) if chunks else pl.DataFrame()
    except Exception as exc:  # noqa: BLE001 — recover gracefully
        logger.warning("Fixed-width flatten failed: %s", exc)
        warnings.append(f"Fixed-width flatten failed: {exc}")
        return pl.DataFrame()


def _uses_fixed_layout(discovery: DiscoveryResult) -> bool:
    return bool(
        (discovery.detail_layout or discovery.candidate_layout)
        and not discovery.delimiter
    )


# ── Joins ─────────────────────────────────────────────────────────────


def _apply_joins(
    records: pl.DataFrame,
    discovery: DiscoveryResult,
    plan: TransformationPlan,
    source,
    operations: List[str],
    warnings: List[str],
) -> pl.DataFrame:
    """Execute the plan's relationship joins (sales + product master)."""
    if not plan.join_operations:
        return records
    if records.is_empty():
        return records

    from dav_tool.io import safe_read_csv

    product_path = getattr(discovery, "product_master_path", None)
    if not product_path:
        warnings.append("Join requested but no product master path was detected.")
        return records

    try:
        product_df = safe_read_csv(product_path, separator=discovery.delimiter or ",", source=source)
    except Exception as exc:  # noqa: BLE001 — recover gracefully
        logger.warning("Product master load failed: %s", exc)
        warnings.append(f"Product master load failed: {exc}")
        return records

    for op in plan.join_operations:
        operations.append(op.get("operation", "left_join"))
        source_col = op.get("source")
        target_col = op.get("target")
        records = _left_join(records, product_df, source_col, target_col, warnings)
    return records


def _left_join(
    sales_df: pl.DataFrame,
    product_df: pl.DataFrame,
    source_col: Optional[str],
    target_col: Optional[str],
    warnings: List[str],
) -> pl.DataFrame:
    """Left-join product attributes onto sales rows on the given key."""
    if sales_df.is_empty() or product_df.is_empty():
        return sales_df
    link = source_col or "UPC"
    prod_key = target_col or link
    if link not in sales_df.columns:
        warnings.append(f"Join key {link!r} not present in sales — skipped.")
        return sales_df
    if prod_key not in product_df.columns:
        warnings.append(f"Join key {prod_key!r} not present in product — skipped.")
        return sales_df
    try:
        sales_df = sales_df.with_columns(pl.col(link).cast(pl.Utf8, strict=False))
        product_df = product_df.with_columns(pl.col(prod_key).cast(pl.Utf8, strict=False))
        extra = [c for c in product_df.columns if c != prod_key]
        return sales_df.join(product_df.select([prod_key] + extra), on=link, how="left")
    except Exception as exc:  # noqa: BLE001 — recover gracefully
        warnings.append(f"Join failed: {exc}")
        return sales_df


# ── Helpers ───────────────────────────────────────────────────────────


def _surviving_record_types(discovery: DiscoveryResult, plan: TransformationPlan) -> List[str]:
    """Record types that survive transformation (detail types, not trailers)."""
    trailer = set(plan.trailer_removal or [])
    rtypes = list(discovery.ml_record_types or [])
    if plan.child_expansion:
        rtypes = list(plan.child_expansion)
    return [r for r in rtypes if r not in trailer]


def _layout(discovery: DiscoveryResult) -> Optional[List[Dict[str, Any]]]:
    return discovery.detail_layout or discovery.candidate_layout or None

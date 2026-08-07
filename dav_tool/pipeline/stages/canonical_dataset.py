"""Canonical Dataset Stage — produces an immutable CanonicalDataset.

Responsibility: convert a ParsedDataset into a CanonicalDataset (the single
contract consumed by Aggregation).  The CanonicalDataset is immutable after
creation; no later stage may modify it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dav_tool._parsers import canonical_chunk_stream
from dav_tool.workflow.canonical import CANONICAL_SCHEMA_TEMPLATES, CanonicalDataset
from dav_tool.workflow.discovery import DiscoveryResult

from ..contracts import CanonicalMapping, ParsedDataset, QuantityResolution
from ..stage import BaseStage, StageResult, FatalStageError
from .canonical_mapping import build_canonical_mapping
from .quantity_resolution import build_quantity_resolution

logger = logging.getLogger(__name__)

PROVENANCE_COLUMNS = (
    "OriginalUnits", "OriginalWeight", "ResolvedQuantity",
    "QuantitySource", "WeightUOM",
)


class CanonicalDatasetStage(BaseStage):
    """Builds an immutable CanonicalDataset from the ParsedDataset."""

    name = "canonical_dataset"
    label = "Canonical Dataset"

    def execute(self, ctx) -> StageResult:
        parsed = ctx.parsed
        if parsed is None:
            raise FatalStageError(
                "Canonical Dataset requires a ParsedDataset (run Parser Pipeline first).",
                user_message="No parsed dataset available.",
            )

        discovery = ctx.discovery
        user_config = ctx.user_config or {}

        if discovery is not None and discovery.recommended_parser in (
            "record_based", "parent_child",
        ):
            # Parser-driven canonicalization preserves the flattening done by
            # the record-based / parent-child parsers.
            dataset = _canonical_from_parsed(parsed, discovery, ctx, user_config)
        else:
            dataset = _canonical_from_parse_options(parsed, discovery, ctx, user_config)

        ctx.canonical = dataset
        return StageResult(stage=self.name)


def _canonical_from_parsed(
    parsed: ParsedDataset,
    discovery: DiscoveryResult,
    ctx,
    user_config: Dict[str, Any],
) -> CanonicalDataset:
    """Build a CanonicalDataset that streams the already-parsed data.

    The record-based parser yields physical ``Column_N`` columns; the explicit
    CanonicalMapping renames them to canonical fields.  No downstream layer
    ever reads the raw physical names.
    """
    import polars as pl

    from ..contracts import CanonicalMapping

    data = parsed.data
    column_names = user_config.get("column_names")

    if data is not None and column_names and len(column_names) == data.width:
        data = data.rename({
            col: name for col, name in zip(data.columns, column_names)
        })

    physical = list(data.columns) if data is not None else list(parsed.schema)
    mapping = _canonical_mapping(ctx, discovery, user_config, physical=physical)
    level = user_config.get("level", "item")
    file_paths = list(discovery.file_paths or [])

    def _stream():
        if data is not None and not data.is_empty():
            yield _canonical_select(data, mapping, level)

    schema = _parsed_canonical_schema(data, mapping, level)
    return CanonicalDataset(
        schema=schema,
        level=level,
        stream_factory=_stream,
        file_paths=file_paths,
        metadata={
            "parser": parsed.parser_name,
            "file_type": discovery.file_type,
            "record_types": parsed.metadata.get("record_types", []),
            "file_count": len(file_paths) if file_paths else 0,
            "detail_row_count": parsed.row_count,
            "mapping_confidence": mapping.confidence,
        },
    )


def _canonical_select(data, mapping: CanonicalMapping, level: str):
    """Select and rename mapped physical columns to canonical fields."""
    import polars as pl

    from dav_tool._numeric import numeric_parse_expr

    wanted = ("STORE_NUMBER", "UPC_CODE", "PRODUCT_DESCRIPTION",
              "TRANSACTION_DATE", "UNITS_SOLD", "WEIGHT_QTY",
              "WEIGHT_UOM", "TOTAL_DOLLARS")
    numeric = {"UNITS_SOLD", "WEIGHT_QTY", "TOTAL_DOLLARS"}
    exprs = []
    for canonical in wanted:
        phys = mapping.physical(canonical)
        if phys and phys in data.columns:
            if canonical in numeric:
                exprs.append(numeric_parse_expr(phys).alias(canonical))
            else:
                exprs.append(pl.col(phys).alias(canonical))
    return data.select(exprs) if exprs else data.limit(0)


def _parsed_canonical_schema(data, mapping: CanonicalMapping, level: str) -> List[str]:
    if data is None or data.is_empty():
        return list(CANONICAL_SCHEMA_TEMPLATES.get("minimal", {}).get(level, []))
    out = []
    for canonical in ("STORE_NUMBER", "UPC_CODE", "PRODUCT_DESCRIPTION",
                      "TRANSACTION_DATE", "UNITS_SOLD", "WEIGHT_QTY",
                      "WEIGHT_UOM", "TOTAL_DOLLARS"):
        if mapping.physical(canonical) and mapping.physical(canonical) in data.columns:
            out.append(canonical)
    return out or list(data.columns)


def _canonical_from_parse_options(
    parsed: ParsedDataset,
    discovery: DiscoveryResult,
    ctx,
    user_config: Dict[str, Any],
) -> CanonicalDataset:
    """Build a CanonicalDataset via the canonical chunk stream (delimited/fixed)."""
    from dav_tool.options import ParseOptions

    parse_opts = _build_parse_options(discovery, user_config)
    mapping = _canonical_mapping(ctx, discovery, user_config)
    resolution = _quantity_resolution(ctx, mapping, user_config)

    level = user_config.get("level", "item")
    template = user_config.get("schema_template", "minimal")
    file_paths = list(discovery.file_paths or [])

    extra_cols = _plain_field_cols(mapping)

    col_args = {}
    if level == "store":
        col_args = {
            "store_col": mapping.physical("STORE_NUMBER"),
            "units_col": mapping.physical("UNITS_SOLD"),
            "price_col": mapping.physical("TOTAL_DOLLARS"),
        }
    elif level == "item":
        col_args = {
            "upc_col": mapping.physical("UPC_CODE"),
            "desc_col": mapping.physical("PRODUCT_DESCRIPTION"),
            "units_col": mapping.physical("UNITS_SOLD"),
            "price_col": mapping.physical("TOTAL_DOLLARS"),
        }
    elif level == "upc":
        col_args = {
            "upc_col": mapping.physical("UPC_CODE"),
            "units_col": mapping.physical("UNITS_SOLD"),
            "price_col": mapping.physical("TOTAL_DOLLARS"),
        }
    else:
        raise ValueError(f"Unknown aggregation level: {level}")

    def _build_stream():
        return canonical_chunk_stream(
            file_paths,
            parse_opts.file_type,
            parse_opts.layout,
            start_line=parse_opts.start_line,
            record_type=parse_opts.record_type,
            multiline_record_types=parse_opts.multiline_record_types,
            multiline_delimiter=parse_opts.multiline_delimiter,
            header_prefix=parse_opts.header_prefix,
            header_layout=parse_opts.header_layout,
            detail_layout=parse_opts.detail_layout,
            trailer_prefix=parse_opts.trailer_prefix,
            trailer_layout=parse_opts.trailer_layout,
            source=ctx.source,
            delimiter=parse_opts.delimiter,
            column_names=parse_opts.column_names,
            level=level,
            price_type=user_config.get("price_type") or "Total Price",
            implied_units=bool(user_config.get("implied_units")),
            implied_dollars=bool(user_config.get("implied_dollars")),
            quantity_type=resolution.strategy,
            weight_col=mapping.physical("WEIGHT_QTY"),
            weight_uom=resolution.weight_uom,
            weight_uom_col=mapping.physical("WEIGHT_UOM"),
            numeric_config=getattr(parse_opts, "numeric_config", None),
            date_col=mapping.physical("TRANSACTION_DATE"),
            weight_qty_col=mapping.physical("WEIGHT_QTY"),
            quantity_strategy=resolution.strategy,
            units_uom=resolution.units_uom,
            schema_template=template,
            quantity_provenance=resolution.preserve_provenance,
            extra_cols=extra_cols or None,
            **col_args,
        )

    schema = _schema_for(level, template, resolution)
    return CanonicalDataset(
        schema=schema,
        level=level,
        stream_factory=_build_stream,
        file_paths=file_paths,
        metadata={
            "file_type": parse_opts.file_type,
            "delimiter": parse_opts.delimiter,
            "file_count": len(file_paths) if file_paths else 0,
            "mapping_confidence": mapping.confidence,
            "quantity_strategy": resolution.strategy,
            "preserve_provenance": resolution.preserve_provenance,
        },
    )


def _canonical_mapping(
    ctx,
    discovery: DiscoveryResult,
    user_config: Dict[str, Any],
    physical: Optional[List[str]] = None,
) -> CanonicalMapping:
    if ctx.mapping is not None:
        return ctx.mapping
    return build_canonical_mapping(
        ctx.parsed, discovery, user_config, physical=physical,
    )


def _quantity_resolution(
    ctx,
    mapping: CanonicalMapping,
    user_config: Dict[str, Any],
) -> QuantityResolution:
    if ctx.quantity_resolution is not None:
        return ctx.quantity_resolution
    return build_quantity_resolution(mapping, user_config)


def _schema_for(
    level: str,
    template: str,
    resolution: QuantityResolution,
) -> List[str]:
    schema = list(CANONICAL_SCHEMA_TEMPLATES.get(template, {}).get(level, []))
    if resolution.preserve_provenance:
        for col in PROVENANCE_COLUMNS:
            if col not in schema:
                schema.append(col)
    return schema


def _plain_field_cols(mapping: CanonicalMapping) -> Dict[str, str]:
    """Map physical columns for canonical plain fields (CATEGORY, BRAND, ...)."""
    out: Dict[str, str] = {}
    for canonical in (
        "CATEGORY", "BRAND", "DEPARTMENT", "STORE_NAME", "ITEM_SIZE", "ITEM_UOM",
    ):
        phys = mapping.physical(canonical)
        if phys:
            out[canonical] = phys
    return out


def _build_parse_options(discovery: DiscoveryResult, user_config: Dict[str, Any]):
    from dav_tool.options import ParseOptions

    return ParseOptions(
        file_type=user_config.get("file_type") or discovery.file_type or "delimited",
        delimiter=user_config.get("delimiter") or discovery.delimiter,
        start_line=user_config.get("start_line") or discovery.start_line or 0,
        record_type=user_config.get("record_type") or discovery.record_type,
        layout=user_config.get("layout") or discovery.layout,
        column_names=user_config.get("column_names") or discovery.columns or discovery.schema,
        header_prefix=user_config.get("header_prefix") or discovery.header_prefix,
        header_layout=user_config.get("header_layout") or discovery.header_layout,
        detail_layout=user_config.get("detail_layout") or discovery.detail_layout,
        trailer_prefix=user_config.get("trailer_prefix") or discovery.trailer_prefix,
        trailer_layout=user_config.get("trailer_layout") or discovery.trailer_layout,
        multiline_record_types=user_config.get("multiline_record_types")
        or discovery.ml_record_types,
        multiline_delimiter=user_config.get("multiline_delimiter")
        or discovery.ml_delimiter
        or "|",
    )

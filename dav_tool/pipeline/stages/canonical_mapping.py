"""Canonical Mapping Stage — ParsedDataset → CanonicalMapping.

Responsibility: map retailer-specific physical columns into the platform
canonical fields.  Supports detection suggestions, alias matching, confidence
scoring, and user overrides.  Produces the explicit :class:`CanonicalMapping`
contract consumed by the Quantity Resolution and Canonical Dataset stages.

No downstream layer reads retailer column names — they read canonical fields
through the mapping.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from dav_tool.workflow.discovery import DiscoveryResult

from ..canonical_schema import (
    CANONICAL_FIELDS,
    ROLE_BY_CANONICAL,
    best_match,
)
from ..contracts import CanonicalMapping, ColumnAssignment, ParsedDataset
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)

#: canonical field → discovery suggestion role
_SUGGESTION_ROLE = {
    "STORE_NUMBER": "store",
    "UPC_CODE": "upc",
    "PRODUCT_DESCRIPTION": "description",
    "UNITS_SOLD": "units",
    "WEIGHT_QTY": "weight_qty",
    "WEIGHT_UOM": "weight_uom",
    "TOTAL_DOLLARS": "price",
}

#: canonical field → user_config override key(s)
_OVERRIDE_KEYS = {
    "STORE_NUMBER": ("store_col",),
    "UPC_CODE": ("upc_col",),
    "PRODUCT_DESCRIPTION": ("desc_col",),
    "TRANSACTION_DATE": ("date_col",),
    "UNITS_SOLD": ("units_col",),
    "WEIGHT_QTY": ("weight_qty_col", "weight_col"),
    "WEIGHT_UOM": ("weight_uom_col",),
    "TOTAL_DOLLARS": ("price_col",),
    "CATEGORY": ("category_col",),
    "BRAND": ("brand_col",),
    "DEPARTMENT": ("department_col",),
    "STORE_NAME": ("store_name_col",),
    "ITEM_SIZE": ("item_size_col",),
    "ITEM_UOM": ("item_uom_col",),
}


class CanonicalMappingStage(BaseStage):
    """Builds the explicit physical → canonical mapping."""

    name = "canonical_mapping"
    label = "Canonical Mapping"

    def execute(self, ctx) -> StageResult:
        parsed: Optional[ParsedDataset] = ctx.parsed
        if parsed is None:
            raise FatalStageError(
                "Canonical Mapping requires a ParsedDataset (run Parser Pipeline first).",
                user_message="No parsed dataset available.",
            )

        t0 = time.perf_counter()
        mapping = build_canonical_mapping(
            parsed,
            ctx.discovery,
            ctx.user_config or {},
        )
        elapsed = time.perf_counter() - t0
        ctx.metrics.record("mapping", "canonical_mapping_stage", elapsed)
        ctx.mapping = mapping
        return StageResult(stage=self.name)


def build_canonical_mapping(
    parsed: ParsedDataset,
    discovery: Optional[DiscoveryResult],
    user_config: Dict[str, Any],
    physical: Optional[List[str]] = None,
) -> CanonicalMapping:
    """Build the CanonicalMapping for a parsed dataset."""
    physical = physical if physical is not None else _physical_columns(parsed, discovery)
    suggestions = _suggestions(discovery)
    level = user_config.get("level") or _level(discovery) or "item"

    assignments: List[ColumnAssignment] = []
    for canonical in CANONICAL_FIELDS:
        assignments.append(_assign(canonical, physical, suggestions, user_config))

    mapped = [a for a in assignments if a.physical]
    confidence = (
        sum(a.confidence for a in mapped) / len(mapped)
        if mapped else 0.0
    )

    return CanonicalMapping(
        assignments=tuple(assignments),
        level=level,
        suggestions=dict(suggestions),
        overrides=_overrides(user_config),
        confidence=round(confidence, 3),
        metadata={
            "physical_columns": physical,
            "mapped_roles": _mapped_roles(assignments),
        },
    )


def _physical_columns(
    parsed: Optional[ParsedDataset],
    discovery: Optional[DiscoveryResult],
) -> List[str]:
    if parsed is not None and parsed.schema:
        return list(parsed.schema)
    if discovery is not None and (discovery.columns or discovery.schema):
        return list(discovery.columns or discovery.schema)
    return []


def _suggestions(discovery: Optional[DiscoveryResult]) -> Dict[str, str]:
    if discovery is None:
        return {}
    return {k: v for k, v in (discovery.candidate_columns or {}).items() if v}


def _level(discovery: Optional[DiscoveryResult]) -> Optional[str]:
    if discovery is None:
        return None
    return getattr(discovery, "aggregation_level", None)


def _assign(
    canonical: str,
    physical: List[str],
    suggestions: Dict[str, str],
    user_config: Dict[str, Any],
) -> ColumnAssignment:
    override = _find_override(canonical, user_config)
    if override:
        if override in physical:
            return ColumnAssignment(
                canonical=canonical, physical=override,
                confidence=1.0, source="override",
            )
        logger.warning(
            "Canonical override for %s=%r is not a physical column; ignored.",
            canonical, override,
        )
        return ColumnAssignment(canonical=canonical)

    role = _SUGGESTION_ROLE.get(canonical)
    if role:
        sug = suggestions.get(role)
        if sug and sug in physical:
            return ColumnAssignment(
                canonical=canonical, physical=sug,
                confidence=1.0, source="suggestion",
            )

    phys, conf = best_match(physical, canonical, suggestions)
    if phys and conf >= 0.85:
        source = "suggestion" if conf >= 1.0 else "alias"
        return ColumnAssignment(
            canonical=canonical, physical=phys,
            confidence=round(conf, 3), source=source,
            aliases=_matched_aliases(canonical, phys),
        )
    return ColumnAssignment(canonical=canonical)


def _find_override(canonical: str, user_config: Dict[str, Any]) -> Optional[str]:
    for key in _OVERRIDE_KEYS.get(canonical, ()):
        value = user_config.get(key)
        if value:
            return value
    return None


def _overrides(user_config: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for canonical, keys in _OVERRIDE_KEYS.items():
        for key in keys:
            if user_config.get(key):
                out[canonical] = user_config[key]
                break
    return out


def _matched_aliases(canonical: str, physical: str) -> tuple:
    from ..canonical_schema import CANONICAL_ALIASES

    if physical.upper() in CANONICAL_ALIASES.get(canonical, []):
        return (physical.upper(),)
    return ()


def _mapped_roles(assignments: List[ColumnAssignment]) -> Dict[str, str]:
    return {
        a.canonical: a.physical
        for a in assignments
        if a.physical
    }

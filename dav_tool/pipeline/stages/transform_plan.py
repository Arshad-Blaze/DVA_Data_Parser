"""Transformation Planning Stage — DatasetGraph → TransformationPlan.

Responsibility: convert a DatasetGraph into a TransformationPlan containing
flatten operations, join operations, header/trailer/metadata removal,
parent replication, child expansion, and column normalization.

No parsing occurs here — only planning.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..contracts import DatasetGraph, TransformationPlan
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class TransformationPlanningStage(BaseStage):
    """Produces a TransformationPlan from the context's DatasetGraph."""

    name = "transform_plan"
    label = "Transformation Planning"

    def execute(self, ctx) -> StageResult:
        graph = ctx.graph
        if graph is None:
            raise FatalStageError(
                "Transformation Planning requires a DatasetGraph (run Dataset Graph first).",
                user_message="Dataset graph has not been built.",
            )

        ctx.plan = _plan_from_graph(graph, ctx)
        return StageResult(stage=self.name)


def _plan_from_graph(graph: DatasetGraph, ctx) -> TransformationPlan:
    """Derive a TransformationPlan from a DatasetGraph."""
    discovery = ctx.discovery
    flatten_ops: List[Dict[str, Any]] = []
    join_ops: List[Dict[str, Any]] = []
    header_removal = discovery.start_line if discovery is not None else 0
    trailer_removal: List[str] = []
    metadata_removal: List[str] = []
    parent_replication: List[str] = []
    child_expansion: List[str] = []

    if graph.hierarchy:
        flatten_ops.append(
            {
                "operation": "flatten_hierarchy",
                "hierarchy": dict(graph.hierarchy),
                "parent": list(graph.hierarchy.keys())[0] if graph.hierarchy else None,
                "children": list(graph.hierarchy.values()),
            }
        )

    if discovery is not None:
        if (
            discovery.header_prefix
            and (discovery.detail_layout or discovery.candidate_layout)
            and not graph.hierarchy
        ):
            # Header + detail/trailer layouts describe a fixed-width style
            # parent/child file; ensure the Transformation Engine flattens it.
            flatten_ops.append(
                {
                    "operation": "flatten_fixed_width",
                    "parent": discovery.header_prefix,
                    "children": list(discovery.ml_record_types or []),
                }
            )

    if discovery is not None:
        if discovery.trailer_prefix:
            trailer_removal.append(discovery.trailer_prefix)
        if discovery.header_prefix:
            parent_replication.append(discovery.header_prefix)
        if discovery.fixed_width_detail_prefixes:
            child_expansion.extend(discovery.fixed_width_detail_prefixes)

        # Trailer/meta records explicitly dropped during flatten.
        for rt in discovery.ml_record_types or []:
            if rt == discovery.trailer_prefix or rt in ("T", "TRL"):
                trailer_removal.append(rt)

    for rel in graph.relationships:
        join_ops.append(
            {
                "operation": "left_join",
                "source": rel.get("source"),
                "target": rel.get("target"),
                "target_role": "product",
            }
        )

    normalization = _build_normalization(graph)
    return TransformationPlan(
        flatten_operations=tuple(flatten_ops),
        join_operations=tuple(join_ops),
        header_removal=header_removal,
        trailer_removal=tuple(dict.fromkeys(trailer_removal)),
        metadata_removal=tuple(dict.fromkeys(metadata_removal)),
        parent_replication=tuple(dict.fromkeys(parent_replication)),
        child_expansion=tuple(dict.fromkeys(child_expansion)),
        column_normalization=normalization,
    )


def _build_normalization(graph: DatasetGraph) -> Dict[str, str]:
    """Build physical → canonical normalization hints from detection data.

    The actual rename is applied by the Canonical Dataset Stage via the
    canonical normalizer.  This plan captures the *intent* (declared
    physical → canonical mapping) for auditability.
    """
    normalization: Dict[str, str] = {}
    primary = graph.primary
    if primary is None:
        return normalization

    lowered = {c.lower(): c for c in primary.columns}
    role_map = {
        "store": "STORE_NUMBER",
        "upc": "UPC_CODE",
        "upc2": "UPC",
        "description": "PRODUCT_DESCRIPTION",
        "desc": "PRODUCT_DESCRIPTION",
        "units": "UNITS_SOLD",
        "quantity": "UNITS_SOLD",
        "qty": "UNITS_SOLD",
        "price": "TOTAL_DOLLARS",
        "dollars": "TOTAL_DOLLARS",
        "sales": "TOTAL_DOLLARS",
        "store number": "STORE_NUMBER",
        "store_num": "STORE_NUMBER",
    }
    for raw, canonical in role_map.items():
        for col in primary.columns:
            if col.lower() == raw:
                normalization[col] = canonical
                break
    return normalization

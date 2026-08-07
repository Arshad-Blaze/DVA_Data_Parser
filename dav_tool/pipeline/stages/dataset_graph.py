"""Dataset Graph Stage — describes datasets and their relationships.

Responsibility: convert a DiscoveryResult into a DatasetGraph.  The graph
captures input datasets, candidate join keys, hierarchy, file roles, and
the parser recommendation.  No parsing or flattening occurs here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from dav_tool.workflow.discovery import DiscoveryResult

from ..contracts import DatasetGraph, DatasetNode
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class DatasetGraphStage(BaseStage):
    """Builds a DatasetGraph from the context's DiscoveryResult."""

    name = "dataset_graph"
    label = "Dataset Graph"

    def execute(self, ctx) -> StageResult:
        discovery = ctx.discovery
        if discovery is None:
            raise FatalStageError(
                "Dataset Graph requires a DiscoveryResult (run Discovery first).",
                user_message="Discovery has not completed.",
            )

        nodes = _build_nodes(discovery)
        relationships = _build_relationships(discovery)
        hierarchy = _build_hierarchy(discovery)
        file_roles = _build_file_roles(discovery)

        record_types = _build_record_types(discovery)
        layout = _build_layout(discovery)

        ctx.graph = DatasetGraph(
            datasets=tuple(nodes),
            relationships=tuple(relationships),
            hierarchy=hierarchy,
            join_keys=tuple(discovery.candidate_keys or []),
            file_roles=file_roles,
            parser_recommendation=discovery.recommended_parser or "delimited",
            confidence=discovery.confidence or 0.0,
            metadata={
                "file_type": discovery.file_type,
                "delimiter": discovery.delimiter,
                "encoding": None,
                "file_architecture": getattr(discovery, "file_architecture", None),
                "record_types": record_types,
                "layout": layout,
            },
        )
        return StageResult(stage=self.name)


def _build_nodes(discovery: DiscoveryResult) -> List[DatasetNode]:
    """Build dataset nodes from a discovery result."""
    nodes: List[DatasetNode] = []

    # Primary (sales) dataset — always present.
    nodes.append(
        DatasetNode(
            role="sales",
            file_paths=tuple(discovery.file_paths or []),
            columns=tuple(discovery.columns or []),
            file_type=discovery.file_type or "delimited",
            delimiter=discovery.delimiter,
        )
    )

    # Product master dataset, when detected.
    if getattr(discovery, "product_master_path", None):
        nodes.append(
            DatasetNode(
                role="product",
                file_paths=(discovery.product_master_path,),
                columns=(),
                file_type="delimited",
            )
        )

    return nodes


def _build_relationships(discovery: DiscoveryResult) -> List[Dict[str, str]]:
    """Build relationship candidates from suggested joins."""
    rels: List[Dict[str, str]] = []
    for join in discovery.suggested_joins or []:
        rels.append(
            {
                "source": join.get("source_column") or join.get("left", ""),
                "target": join.get("target_column") or join.get("right", ""),
            }
        )
    # Candidate keys provide additional relationship signals.
    for key in discovery.candidate_keys or []:
        src = key.get("column") or key.get("source") or ""
        tgt = key.get("target_column") or ""
        if src and tgt and {"source": src, "target": tgt} not in rels:
            rels.append({"source": src, "target": tgt})
    return rels


def _build_hierarchy(discovery: DiscoveryResult) -> Dict[str, str]:
    """Build the record hierarchy for multiline files."""
    hierarchy: Dict[str, str] = {}
    record_types = discovery.ml_record_types or []
    if discovery.file_type == "multiline" and record_types:
        # Parent (header) is the first type, details follow, trailer last.
        parent = discovery.record_prefix[0] if discovery.record_prefix else (record_types[0] if record_types else "")
        trailer = discovery.trailer_prefix
        if parent:
            for rt in record_types:
                if rt != parent and rt != trailer:
                    hierarchy[parent] = rt
    elif discovery.header_prefix:
        parent = discovery.header_prefix
        details = discovery.fixed_width_detail_prefixes or []
        if details:
            hierarchy[parent] = details[0]
    return hierarchy


def _build_file_roles(discovery: DiscoveryResult) -> Dict[str, str]:
    """Map each file path to its semantic role."""
    roles: Dict[str, str] = {}
    for fp in discovery.file_paths or []:
        roles[fp] = "sales"
    if getattr(discovery, "product_master_path", None):
        roles[discovery.product_master_path] = "product"
    return roles


def _build_record_types(discovery: DiscoveryResult) -> List[str]:
    """Record type prefixes that structure the file (parent/child/trailer).

    For multiline/record-based files this is the ``ml_record_types`` list
    (e.g. ``["H", "D", "T"]``); for fixed-width files it is the header prefix
    plus detail prefixes.  Flat delimited files have no record types.
    """
    record_types: List[str] = []
    if discovery.file_type == "multiline":
        record_types.extend(discovery.ml_record_types or [])
    elif discovery.header_prefix:
        record_types.append(discovery.header_prefix)
        record_types.extend(discovery.fixed_width_detail_prefixes or [])
    if discovery.trailer_prefix and discovery.trailer_prefix not in record_types:
        record_types.append(discovery.trailer_prefix)
    return record_types


def _build_layout(discovery: DiscoveryResult) -> Dict[str, Any]:
    """Fixed-width layout metadata, when present.

    The detail layout (or the candidate layout fallback) describes the
    physical column boundaries of detail records.  Also surfaced: the record
    prefix each layout applies to (header vs detail).
    """
    layout: Dict[str, Any] = {}
    if discovery.detail_layout:
        layout["detail"] = discovery.detail_layout
    elif discovery.candidate_layout:
        layout["detail"] = discovery.candidate_layout
    if discovery.header_prefix:
        layout["header_prefix"] = discovery.header_prefix
    if discovery.fixed_width_detail_prefixes:
        layout["detail_prefixes"] = list(discovery.fixed_width_detail_prefixes)
    return layout

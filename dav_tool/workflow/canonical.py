"""Canonical Layer — formal pipeline stage for schema transformation.

Responsibility:
- Build Canonical Schema from Physical Schema (DiscoveryResult)
- Handle user edits to Canonical Schema
- Propagate Canonical Schema to all downstream consumers
- Never reference Physical Schema after creation

This is the single source of truth for column names after the Detection layer.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


@dataclass
class CanonicalSchema:
    """The formal canonical schema — the single source of truth for column names.

    Once built, this is consumed by Processing, Validation, and Reports.
    No downstream component should reference the physical schema.

    Attributes:
        physical_schema: Original column names from detection (immutable reference).
        canonical_names: Business-friendly column names (editable by user).
        column_mapping: Maps canonical column names to normalized canonical names
                       (e.g., 'STORE_NUMBER', 'UPC_CODE', etc.).
    """
    physical_schema: List[str] = field(default_factory=list)
    canonical_names: List[str] = field(default_factory=list)
    column_mapping: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_discovery(cls, discovery: DiscoveryResult) -> "CanonicalSchema":
        """Build a CanonicalSchema from a DiscoveryResult.

        Canonical names default to physical names until the user edits them.
        """
        physical = discovery.columns or discovery.schema or []
        return cls(
            physical_schema=list(physical),
            canonical_names=list(physical),
            column_mapping={},
        )

    @classmethod
    def from_physical(cls, physical_columns: List[str]) -> "CanonicalSchema":
        """Build from a list of physical column names."""
        return cls(
            physical_schema=list(physical_columns),
            canonical_names=list(physical_columns),
            column_mapping={},
        )

    def get_rename_mapping(self) -> Dict[str, str]:
        """Get a dict mapping physical names to canonical names.

        Only includes names that differ.
        """
        mapping = {}
        for phys, canon in zip(self.physical_schema, self.canonical_names):
            if phys != canon:
                mapping[phys] = canon
        return mapping

    @property
    def columns(self) -> List[str]:
        """Canonical column names for display and selection."""
        return self.canonical_names

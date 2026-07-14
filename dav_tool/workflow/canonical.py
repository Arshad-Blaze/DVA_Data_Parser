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
from typing import Dict, List, Optional, Tuple

import polars as pl

from dav_tool._normalizer import (
    apply_column_names, store_normalize_exprs, item_normalize_exprs,
)
from dav_tool.options import ColumnMapping
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

    def update_canonical_names(self, names: List[str]) -> bool:
        """Update canonical names. Returns True if changed."""
        if names != self.canonical_names and len(names) == len(self.physical_schema):
            self.canonical_names = list(names)
            return True
        return False

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
    def is_edited(self) -> bool:
        """True if the user has edited canonical names."""
        return self.canonical_names != self.physical_schema

    @property
    def columns(self) -> List[str]:
        """Canonical column names for display and selection."""
        return self.canonical_names


def build_canonical_schema(
    discovery: Optional[DiscoveryResult] = None,
    physical_columns: Optional[List[str]] = None,
    config_canonical: Optional[List[str]] = None,
) -> CanonicalSchema:
    """Build the canonical schema from available sources.

    Priority:
    1. DiscoveryResult (for fresh detection)
    2. physical_columns (fallback list)
    3. config_canonical (pre-existing canonical names from loaded config)
    """
    if config_canonical:
        physical = physical_columns or config_canonical
        return CanonicalSchema(
            physical_schema=list(physical),
            canonical_names=list(config_canonical),
        )
    if discovery:
        return CanonicalSchema.from_discovery(discovery)
    if physical_columns:
        return CanonicalSchema.from_physical(physical_columns)
    return CanonicalSchema()


def apply_canonical_to_df(
    df: pl.DataFrame,
    canonical: CanonicalSchema,
) -> pl.DataFrame:
    """Rename DataFrame columns to canonical names, preserving order."""
    mapping = canonical.get_rename_mapping()
    if mapping:
        return df.rename(mapping)
    return df


def normalize_to_canonical_columns(
    df: pl.DataFrame,
    mapping: ColumnMapping,
    price_type: str = "Total Price",
) -> pl.DataFrame:
    """Normalize a parsed DataFrame to the canonical column set.

    Produces the standard canonical columns:
        STORE_NUMBER, UPC_CODE, PRODUCT_DESCRIPTION, Units, Totalprice

    This is the bridge between raw data and the canonical representation.
    """
    store_exprs = store_normalize_exprs(
        mapping.store, mapping.units, mapping.price,
        implied_units=mapping.implied_units,
        implied_dollars=mapping.implied_dollars,
        price_type=price_type,
    )
    item_exprs = item_normalize_exprs(
        mapping.upc, mapping.description, mapping.units, mapping.price,
        implied_units=mapping.implied_units,
        implied_dollars=mapping.implied_dollars,
    )

    df = df.with_columns(store_exprs + item_exprs)
    return df

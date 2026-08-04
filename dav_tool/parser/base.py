"""Base parser contract for the parser-driven pipeline.

Every concrete parser returns a :class:`ParsedResult` carrying the same
contract: a canonical DataFrame, canonical metadata, the DiscoveryResult
that drove parsing, and (where applicable) an internal record tree.

Downstream phases (Column Mapping → Validation → Reports) consume ONLY
``canonical_data`` and ``metadata``.  No retailer-specific schema is
exposed beyond this point.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import polars as pl

from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Raised when a parser cannot produce a valid result."""


@dataclass
class ParsedResult:
    """The uniform output of every parser.

    Attributes:
        canonical_data: Canonically-named DataFrame (streamed or collected).
        metadata: Canonical metadata describing the parse.
        discovery: The DiscoveryResult that drove this parse.
        record_tree: Internal record hierarchy (only for record-based parsers).
        schema: Canonical column names (defaults to canonical_data.columns).
        warnings: Parsing warnings collected during the run.
    """
    canonical_data: Optional[pl.DataFrame] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovery: Optional[DiscoveryResult] = None
    record_tree: Optional[Any] = None
    schema: Optional[List[str]] = None
    warnings: List[str] = field(default_factory=list)
    _parsed_data: Optional[pl.DataFrame] = None

    @property
    def columns(self) -> List[str]:
        """Canonical column names available for Column Mapping."""
        if self.schema:
            return list(self.schema)
        if self.canonical_data is not None and not self.canonical_data.is_empty():
            return list(self.canonical_data.columns)
        return []

    @property
    def is_empty(self) -> bool:
        return (
            self.canonical_data is None
            or self.canonical_data.is_empty()
        )

    def to_dataframe(self) -> pl.DataFrame:
        if self.canonical_data is None:
            return pl.DataFrame()
        return self.canonical_data

    def expose_parsed_preview(self) -> pl.DataFrame:
        """Return the parsed (pre-canonical) detail rows for UI preview.

        For record-based parses this is the flattened detail DataFrame; for
        simpler parses it equals the canonical data.  The UI may display this
        only — it never drives parser decisions from it.
        """
        if hasattr(self, "_parsed_data") and getattr(self, "_parsed_data") is not None:
            return self._parsed_data
        return self.to_dataframe()


class BaseParser:
    """Abstract base for all concrete parsers.

    Subclasses implement :meth:`parse`, which must return a
    :class:`ParsedResult`.  ``supports()`` is used by the
    :class:`~dav_tool.parser.factory.ParserFactory` to pick the right parser.
    """

    #: Unique parser name (used in DiscoveryResult.recommended_parser).
    name: str = "base"
    #: Human-readable description.
    description: str = ""
    #: Lower value = higher precedence in the factory fallback.
    priority: int = 100

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        """Return True if this parser can handle the given discovery."""
        return False

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        """Parse the files described by *discovery* into a ParsedResult."""
        raise NotImplementedError

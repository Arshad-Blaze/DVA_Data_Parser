"""Canonical Layer — formal pipeline stage for schema transformation.

Responsibility:
- Build Canonical Schema from Physical Schema (DiscoveryResult)
- Handle user edits to Canonical Schema
- Propagate Canonical Schema to all downstream consumers
- Never reference Physical Schema after creation

This is the single source of truth for column names after the Detection layer.

RC2: Introduces ``CanonicalDataset`` — the single contract consumed by
Processing.  All file-format details are hidden behind a streaming iterator.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

import polars as pl

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


class CanonicalDataset:
    """Self-contained canonical data stream — the single contract for Processing.

    Hides all file-format details (delimiter, encoding, fixed-width, multiline,
    HDR, record types) behind a uniform streaming iterator of canonically-named
    DataFrames.

    Processing only sees:
    - ``schema`` — canonical column names
    - ``iter_chunks()`` — streaming iterator yielding ``pl.DataFrame``
    - ``level`` — the aggregation level (``"store"``, ``"item"``, ``"upc"``)

    Construction requires ``ParseOptions`` + ``ColumnMapping`` (CanonicalContext),
    but those are internal — downsteam layers never reference them.
    """

    def __init__(
        self,
        schema: List[str],
        level: str,
        stream_factory: Callable[[], Iterator[pl.DataFrame]],
        file_paths: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Set[str]] = None,
    ):
        self._schema = list(schema)
        self._level = level
        self._stream_factory = stream_factory
        self._file_paths = list(file_paths) if file_paths else []
        self._metadata = dict(metadata) if metadata else {}
        self._capabilities = capabilities or {"store", "item"}
        self._statistics: Optional[Dict[str, Any]] = None

    # ── Public API ──────────────────────────────────────────────────

    @property
    def schema(self) -> List[str]:
        """Canonical column names in the yielded chunks."""
        return list(self._schema)

    @property
    def level(self) -> str:
        """Aggregation level: ``"store"``, ``"item"``, or ``"upc"``."""
        return self._level

    @property
    def metadata(self) -> Dict[str, Any]:
        """Read-only metadata dict."""
        return dict(self._metadata)

    @property
    def file_paths(self) -> List[str]:
        """Source file paths."""
        return list(self._file_paths)

    @property
    def capabilities(self) -> Set[str]:
        """Set of supported operations (e.g. ``{"store", "item"}``)."""
        return set(self._capabilities)

    @property
    def statistics(self) -> Optional[Dict[str, Any]]:
        """Computed statistics (populated after iteration if collected)."""
        return self._statistics

    def iter_chunks(self) -> Iterator[pl.DataFrame]:
        """Yield canonically-normalized DataFrames.

        Each chunk has columns matching ``schema``.  Chunks are
        pre-normalized to canonical names — no further renaming needed.
        """
        yield from self._stream_factory()

    # ── Factories ───────────────────────────────────────────────────

    @classmethod
    def from_parse_options(
        cls,
        file_paths: List[str],
        parse_opts: "ParseOptions",
        mapping: "ColumnMapping",
        level: str,
        source: Optional[Any] = None,
    ) -> "CanonicalDataset":
        """Build a dataset from ``ParseOptions`` + ``ColumnMapping``.

        This is the standard construction path — the Operation Layer
        creates ``CanonicalContext`` (parse + mapping) first, then uses
        this factory.
        """
        from dav_tool._parsers import canonical_chunk_stream

        if level == "store":
            col_args = dict(
                store_col=mapping.store,
                units_col=mapping.units,
                price_col=mapping.price,
            )
        elif level == "item":
            col_args = dict(
                upc_col=mapping.upc,
                desc_col=mapping.description,
                units_col=mapping.units,
                price_col=mapping.price,
            )
        elif level == "upc":
            col_args = dict(
                upc_col=mapping.upc,
                units_col=mapping.units,
                price_col=mapping.price,
            )
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
                source=source,
                delimiter=parse_opts.delimiter,
                column_names=parse_opts.column_names,
                level=level,
                price_type=mapping.price_type,
                implied_units=mapping.implied_units,
                implied_dollars=mapping.implied_dollars,
                quantity_type=mapping.quantity_type,
                weight_col=mapping.weight_col,
                weight_uom=mapping.weight_uom,
                weight_uom_col=mapping.weight_uom_col,
                numeric_config=getattr(parse_opts, "numeric_config", None),
                **col_args,
            )

        schema = _build_schema_for_level(level)
        return cls(
            schema=schema,
            level=level,
            stream_factory=_build_stream,
            file_paths=file_paths,
            metadata={
                "file_type": parse_opts.file_type,
                "delimiter": parse_opts.delimiter,
                "file_count": len(file_paths) if file_paths else 0,
            },
        )

    @classmethod
    def from_context(
        cls,
        ctx: Any,
        level: str,
        source: Optional[Any] = None,
    ) -> "CanonicalDataset":
        """Build from a ``ProcessingContext`` using ``ParseOptions.from_context``."""
        from dav_tool.options import ParseOptions, ColumnMapping

        parse_opts = ParseOptions.from_context(ctx)
        mapping = ColumnMapping.from_context(ctx)
        file_paths = list(ctx.file_paths or [])
        return cls.from_parse_options(file_paths, parse_opts, mapping, level, source=source)


def _build_schema_for_level(level: str) -> List[str]:
    """Return the expected canonical column names for *level*."""
    if level == "store":
        return ["STORE_NUMBER", "Units", "Totalprice"]
    if level == "item":
        return ["UPC_CODE", "PRODUCT_DESCRIPTION", "UNITS_SOLD", "TOTAL_DOLLARS"]
    if level == "upc":
        return ["UPC", "UNITS_SOLD", "TOTAL_DOLLARS"]
    return []

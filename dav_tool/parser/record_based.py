"""Record-based parser (HEB) — builds an internal record tree from a file.

A record-based file is a sequence of typed records (HDR/S/U/T, HDR/D/TRL,
or arbitrary prefixes).  This parser:
  1. Reads lines and classifies each by record type (prefix).
  2. Builds a :class:`~dav_tool.parser.record_tree.RecordTree`: parent
     records (header/store) own child records (detail/UPC), trailer records
     act as transaction boundaries.
  3. Flattens the tree into leaf detail rows, carrying parent context forward.

The record tree is strictly internal; the UI only receives the flattened
canonical DataFrame and metadata.
"""
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.factory import register_parser
from dav_tool.parser.record_tree import RecordNode, RecordTree
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)

TRAILER = "trailer"
PARENT = "header"
DETAIL = "detail"


@register_parser
class RecordBasedParser(BaseParser):
    name = "record_based"
    description = "Builds an internal record tree for multi-record (HEB) files."
    priority = 10

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        return discovery.file_type == "multiline"

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        transformed = kwargs.get("transformed")
        if transformed is not None and transformed.records is not None:
            return self._parse_transformed(discovery, transformed, kwargs.get("column_names"))

        tree = self._build_tree(discovery, kwargs.get("source"))
        rows = tree.flatten_details()
        data = pl.DataFrame(rows) if rows else pl.DataFrame()

        column_names = kwargs.get("column_names")
        if column_names and not data.is_empty():
            data = _rename_columns(data, column_names)

        return ParsedResult(
            canonical_data=data,
            metadata={
                "parser": self.name,
                "file_type": discovery.file_type,
                "record_types": tree.record_types,
                "parent_type": tree.parent_type,
                "detail_type": tree.detail_type,
                "detail_row_count": len(rows),
                "header_count": len(tree.find_all(PARENT)),
            },
            discovery=discovery,
            record_tree=tree,
            schema=list(data.columns),
            _parsed_data=data,
        )

    def _parse_transformed(self, discovery, transformed, column_names):
        """Parse pre-transformed records (Transformation Engine output).

        The Transformation Engine has already flattened, removed headers/
        trailers/metadata, and applied joins.  This parser only interprets
        fields and produces the ParsedDataset — it never reshapes records.
        """
        data = transformed.records
        if column_names and not data.is_empty():
            data = _rename_columns(data, column_names)

        return ParsedResult(
            canonical_data=data,
            metadata={
                "parser": self.name,
                "file_type": discovery.file_type,
                "transformed": True,
                "operations": list(transformed.operations),
                "detail_row_count": data.height,
                "header_count": 0,
            },
            discovery=discovery,
            record_tree=None,
            schema=list(data.columns),
            _parsed_data=data,
        )

    # ------------------------------------------------------------------
    def _classify_prefixes(
        self, discovery: DiscoveryResult,
    ) -> Tuple[List[str], List[str], List[str]]:
        """Return (parent_prefixes, detail_prefixes, trailer_prefixes).

        Parent detection: the parent (header/store) record type is the one
        that appears LEAST often (once per transaction) and carries the fewest
        layout fields — mirroring the delimited ``parent/child`` heuristic so
        the parser understands the input automatically, without the UI.
        Trailer prefixes come from ``record_prefix`` when known.
        """
        rtypes = list(discovery.ml_record_types or [])
        trailer_prefixes = list(discovery.record_prefix or [])
        if discovery.trailer_prefix and discovery.trailer_prefix not in trailer_prefixes:
            trailer_prefixes.append(discovery.trailer_prefix)

        # When discovery did not supply record types, sample the file to
        # discover leading alphabetic prefixes (HDR, S, U, T, D, ...).
        if not rtypes:
            rtypes = _discover_record_prefixes(discovery)

        if discovery.header_prefix:
            header = discovery.header_prefix
        else:
            header = None

        potential = [r for r in rtypes if r not in trailer_prefixes]

        if header and header in potential:
            parents, details = [header], [r for r in potential if r != header]
        else:
            parents, details = _autodetect_parent(
                self, discovery, potential, trailer_prefixes,
            )

        if not details:
            details = list(discovery.fixed_width_detail_prefixes or ["D"])
        if not parents:
            parents = [parents[0]] if parents else (rtypes or ["HDR"])

        return parents, details, trailer_prefixes

    def _build_tree(self, discovery: DiscoveryResult, source=None) -> RecordTree:
        tree = RecordTree()
        file_path = (discovery.file_paths or [None])[0]
        if not file_path:
            return tree

        parents, details, trailers = self._classify_prefixes(discovery)
        detail_layout = discovery.detail_layout or discovery.candidate_layout

        tree.parent_type = PARENT
        tree.detail_type = DETAIL
        tree.trailer_type = TRAILER
        tree.record_types = parents + details + trailers

        current_parent: Optional[RecordNode] = None

        with _open(discovery, file_path, source) as f:
            for i, raw_line in enumerate(f):
                line = raw_line.rstrip("\n\r")
                if not line:
                    continue

                if any(line.startswith(t) for t in trailers):
                    node = RecordNode(record_type=TRAILER, line_number=i + 1, raw=line)
                    (current_parent or tree.root).add_child(node)
                    continue

                if any(line.startswith(p) for p in parents):
                    fields = _extract_fields(line, detail_layout)
                    node = RecordNode(
                        record_type=PARENT, line_number=i + 1, fields=fields, raw=line,
                    )
                    tree.add(node)
                    current_parent = node
                    continue

                if any(line.startswith(d) for d in details):
                    fields = _extract_fields(line, detail_layout)
                    node = RecordNode(
                        record_type=DETAIL, line_number=i + 1, fields=fields, raw=line,
                    )
                    (current_parent or tree.root).add_child(node)
                    continue

        return tree


def _discover_record_prefixes(
    discovery: DiscoveryResult,
    sample_lines: int = 200,
) -> List[str]:
    """Sample the file and return distinct leading alphabetic prefixes.

    Used when discovery did not classify record types (e.g. HDR, S, U, T, D).
    Lines starting with whitespace, digits, or quote chars are skipped.
    """
    file_path = (discovery.file_paths or [None])[0]
    if not file_path:
        return []
    prefixes: List[str] = []
    try:
        with _open(discovery, file_path, None) as f:
            for i, line in enumerate(f):
                if i >= sample_lines:
                    break
                stripped = line.rstrip("\n\r")
                if not stripped or stripped[0].isdigit() or stripped[0] == '"':
                    continue
                match = __import__("re").match(r"^[A-Za-z]+", stripped)
                if match:
                    prefix = match.group(0)
                    if prefix not in prefixes:
                        prefixes.append(prefix)
    except Exception as exc:
        logger.warning("record prefix discovery failed: %s", exc)
    return prefixes


def _autodetect_parent(
    parser: "RecordBasedParser",
    discovery: DiscoveryResult,
    potential: List[str],
    trailer_prefixes: List[str],
) -> Tuple[List[str], List[str]]:
    """Detect (parent_prefixes, detail_prefixes) automatically.

    The parent/header record type occurs the FEWEST times (once per
    transaction) and leads each transaction; the detail type dominates by
    count.  Falls back to the first non-trailer candidate as parent.
    """
    candidates = [r for r in potential if r not in trailer_prefixes]
    if not candidates:
        return [], []

    file_path = (discovery.file_paths or [None])[0]
    counts: Dict[str, int] = {}
    first_index: Dict[str, int] = {}
    if file_path:
        try:
            with _open(discovery, file_path, None) as f:
                for i, line in enumerate(f):
                    stripped = line.rstrip("\n\r")
                    if not stripped:
                        continue
                    for r in candidates:
                        if stripped.startswith(r):
                            counts[r] = counts.get(r, 0) + 1
                            first_index.setdefault(r, i)
                            break
        except Exception as exc:
            logger.warning("autodetect_parent sample failed: %s", exc)

    if counts:
        parent = min(
            candidates,
            key=lambda r: (counts.get(r, 0), first_index.get(r, 0)),
        )
    else:
        parent = candidates[0]

    details = [r for r in candidates if r != parent]
    return [parent], details


def _open(discovery: DiscoveryResult, file_path: str, source):
    if source is not None:
        raw = source.open_stream(file_path)
        return io.TextIOWrapper(raw, encoding="utf-8", errors="ignore")
    return open(file_path, "r", encoding="utf-8", errors="ignore")


def _extract_fields(
    line: str, layout: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Extract fields from *line* using a fixed-width layout, else raw line."""
    if not layout:
        return {"raw": line}
    record: Dict[str, Any] = {}
    for col in layout:
        end = min(int(col["end"]), len(line))
        start = int(col["start"])
        raw = line[start:end].strip()
        if col.get("type") == "numeric":
            raw = raw.lstrip("0") or "0"
        record[col["field"]] = raw
    return record


def _rename_columns(df: pl.DataFrame, column_names: List[str]) -> pl.DataFrame:
    """Rename physical columns to canonical names by position."""
    names = list(column_names or [])
    if not names:
        return df
    mapping = {
        col: names[i]
        for i, col in enumerate(df.columns)
        if i < len(names)
    }
    return df.rename(mapping) if mapping else df
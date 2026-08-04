"""Record tree — internal hierarchical model for record-based (HEB) files.

The tree is strictly internal to the parser layer.  The UI never sees it.
It models the physical structure of a record-based file:

    File
    ├── Disclaimer
    ├── Header (metadata)
    ├── Header (HDR)
    ├── Store (parent)
    │   ├── Detail
    │   └── Detail
    ├── Store (parent)
    │   └── Detail
    └── Trailer
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RecordNode:
    """A single record in the hierarchy.

    Attributes:
        record_type: Prefix/kind, e.g. ``disclaimer``, ``header``, ``store``,
                     ``detail``, ``trailer``.
        line_number: 1-based source line this record starts on.
        fields: Parsed field values (dict) for leaf records.
        children: Nested records (e.g. a Store node holds Detail children).
        raw: Optional raw source line.
    """
    record_type: str
    line_number: int = 0
    fields: Dict[str, Any] = field(default_factory=dict)
    children: List["RecordNode"] = field(default_factory=list)
    raw: Optional[str] = None
    parent: Optional["RecordNode"] = None

    def add_child(self, child: "RecordNode") -> "RecordNode":
        child.parent = self
        self.children.append(child)
        return child

    def flatten(self) -> List[Dict[str, Any]]:
        """Flatten this node and all descendants into leaf rows.

        Parent fields are merged (prepended) into each child leaf row so
        a Detail row carries its Store context.
        """
        merged = dict(self.fields)
        if not self.children:
            return [merged]
        rows: List[Dict[str, Any]] = []
        for child in self.children:
            for leaf in child.flatten():
                leaf = {**self.fields, **leaf}
                rows.append(leaf)
        return rows

    def walk(self) -> Any:
        """Yield nodes in depth-first order; convenience for traversal."""
        yield self
        for child in self.children:
            yield from child.walk()

    def descendant_count(self) -> int:
        return sum(1 for _ in self.walk()) - 1


@dataclass
class RecordTree:
    """Internal model of an entire record-based file's structure."""
    root: RecordNode = field(default_factory=lambda: RecordNode(record_type="file"))
    record_types: List[str] = field(default_factory=list)
    detail_type: Optional[str] = None
    parent_type: Optional[str] = None
    trailer_type: Optional[str] = None

    def add(self, node: RecordNode) -> RecordNode:
        """Attach *node* under the root (or a parent by type)."""
        return self.root.add_child(node)

    def find_all(self, record_type: str) -> List[RecordNode]:
        return [n for n in self.root.walk() if n.record_type == record_type]

    def detail_nodes(self) -> List[RecordNode]:
        return self.find_all(self.detail_type or "detail")

    def flatten_details(self) -> List[Dict[str, Any]]:
        """Flatten all leaf detail rows across every parent subtree.

        Parent fields are merged into each detail row.  Trailer records are
        kept in the tree (as transaction boundaries) but never emitted as
        detail rows.
        """
        rows: List[Dict[str, Any]] = []
        for node in self.root.children:
            if node.record_type == self.parent_type:
                for leaf in self._flatten_children(node):
                    rows.append(leaf)
            elif node.record_type == self.detail_type and node.children == []:
                rows.append(dict(node.fields))
        return rows

    def _flatten_children(self, node: RecordNode) -> List[Dict[str, Any]]:
        """Flatten *node's* children, dropping trailer records."""
        rows: List[Dict[str, Any]] = []
        for child in node.children:
            if child.record_type == self.trailer_type:
                continue
            merged = {**node.fields, **child.fields}
            if child.children:
                for leaf in self._flatten_children(child):
                    rows.append({**node.fields, **leaf})
            else:
                rows.append(merged)
        return rows

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the tree (for diagnostics/tests)."""
        return _node_to_dict(self.root)


def _node_to_dict(node: RecordNode) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "record_type": node.record_type,
        "line_number": node.line_number,
        "fields": dict(node.fields),
    }
    if node.children:
        d["children"] = [_node_to_dict(c) for c in node.children]
    return d
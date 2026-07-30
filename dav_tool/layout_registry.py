from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass(frozen=True)
class LayoutEntry:
    field: str
    start: int
    length: int
    type: str = "text"

    @property
    def end(self) -> int:
        return self.start + self.length


@dataclass
class ColumnLayout:
    record_type: str
    columns: List[LayoutEntry]

    def to_parser_format(self) -> List[Dict]:
        return [
            {"field": c.field, "start": c.start, "end": c.end, "type": c.type}
            for c in self.columns
        ]

    @classmethod
    def from_parser_format(cls, record_type: str, layout: List[Dict]) -> "ColumnLayout":
        entries = []
        for col in layout:
            field = col.get("field", "")
            start = col.get("start", 0)
            end = col.get("end", start + col.get("length", 1))
            typ = col.get("type", "text")
            length = end - start
            if length < 0:
                length = 0
            entries.append(LayoutEntry(field=field, start=start, length=length, type=typ))
        return cls(record_type=record_type, columns=entries)


class LayoutRegistry:
    def __init__(self):
        self._layouts: Dict[str, ColumnLayout] = {}

    def register(self, name: str, layout: ColumnLayout) -> None:
        self._layouts[name] = layout

    def get(self, name: str) -> Optional[ColumnLayout]:
        return self._layouts.get(name)

    def get_for_record_type(self, record_type: str) -> Optional[ColumnLayout]:
        for layout in self._layouts.values():
            if layout.record_type == record_type:
                return layout
        return None

    def register_record_layout(self, record_type: str, columns: List[Dict]) -> None:
        layout = ColumnLayout.from_parser_format(record_type, columns)
        self._layouts[record_type] = layout

    def list_record_types(self) -> List[str]:
        return list(self._layouts.keys())

    def _get_prefixes_sorted(self) -> List[str]:
        prefixes = list(self._layouts.keys())
        return sorted(prefixes, key=len, reverse=True)

    def detect_prefix(self, line: str) -> Optional[str]:
        stripped = line.strip()
        if not stripped:
            return None
        for prefix in self._get_prefixes_sorted():
            if stripped.startswith(prefix):
                return prefix
        return None

    def get_layout_for_line(self, line: str) -> Optional[List[Dict]]:
        prefix = self.detect_prefix(line)
        if prefix is None:
            return None
        layout = self._layouts.get(prefix)
        if layout is None:
            return None
        return layout.to_parser_format()

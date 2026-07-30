import logging
from dataclasses import dataclass
from typing import Dict, List

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class RejectedRow:
    file_path: str
    line_number: int
    raw_line: str
    reason: str


class RejectionCollector:
    def __init__(self):
        self._rejected: List[RejectedRow] = []

    def reject(self, file_path: str, line_number: int, raw_line: str, reason: str) -> None:
        self._rejected.append(RejectedRow(file_path, line_number, raw_line, reason))

    def reject_many(self, rows: List[RejectedRow]) -> None:
        self._rejected.extend(rows)

    @property
    def count(self) -> int:
        return len(self._rejected)

    @property
    def empty(self) -> bool:
        return len(self._rejected) == 0

    def to_dataframe(self) -> pl.DataFrame:
        return pl.DataFrame({
            "file_path": [r.file_path for r in self._rejected],
            "line_number": [r.line_number for r in self._rejected],
            "raw_line": [r.raw_line for r in self._rejected],
            "reason": [r.reason for r in self._rejected],
        })

    def clear(self) -> None:
        self._rejected.clear()

    def merge(self, other: 'RejectionCollector') -> None:
        self._rejected.extend(other._rejected)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._rejected:
            counts[r.reason] = counts.get(r.reason, 0) + 1
        return counts

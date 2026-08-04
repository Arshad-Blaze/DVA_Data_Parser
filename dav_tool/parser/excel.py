"""Excel parser — reads .xlsx/.xls workbooks into a structured result."""
import logging
from typing import Any, List, Optional

import polars as pl

from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.factory import register_parser
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


@register_parser
class ExcelParser(BaseParser):
    name = "excel"
    description = "Reads .xlsx/.xls workbooks (first sheet by default)."
    priority = 30

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        if discovery.file_type != "excel":
            return False
        fp = (discovery.file_paths or [None])[0] or ""
        return fp.lower().endswith((".xlsx", ".xls"))

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        sheet = kwargs.get("sheet") or 0
        warnings: List[str] = []
        fp = (discovery.file_paths or [None])[0]
        if not fp:
            return ParsedResult(
                canonical_data=pl.DataFrame(), discovery=discovery,
                metadata={"parser": self.name, "error": "no file path"},
                warnings=["No file path available."],
            )
        try:
            data = pl.read_excel(fp, sheet_id=sheet)
        except Exception as exc:
            data = _read_via_openpyxl(fp, sheet, warnings)
            if data is None:
                logger.warning("Excel read failed for %s (sheet=%s): %s", fp, sheet, exc)
                return ParsedResult(
                    canonical_data=pl.DataFrame(), discovery=discovery,
                    metadata={"parser": self.name, "error": str(exc)},
                    warnings=[f"Could not read Excel file: {exc}"],
                )
        return ParsedResult(
            canonical_data=data,
            metadata={
                "parser": self.name,
                "file_type": "excel",
                "sheet": sheet,
                "row_count": data.height,
                "column_count": data.width,
            },
            discovery=discovery,
            schema=list(data.columns),
            warnings=warnings,
        )


def _read_via_openpyxl(fp: str, sheet: Any, warnings: List[str]) -> Optional[pl.DataFrame]:
    """Read an Excel file using openpyxl when polars' excel engine is absent."""
    try:
        from openpyxl import load_workbook
    except Exception as exc:  # pragma: no cover - openpyxl always available here
        warnings.append(f"openpyxl unavailable for Excel reading: {exc}")
        return None
    try:
        wb = load_workbook(filename=fp, read_only=True, data_only=True)
        ws = wb[sheet] if isinstance(sheet, str) and sheet in wb.sheetnames else wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return pl.DataFrame()
        header, body = list(rows[0]), list(rows[1:])
        data = {str(h): [r[i] if i < len(r) else None for r in body] for i, h in enumerate(header)}
        df = pl.DataFrame(data)
        wb.close()
        return df
    except Exception as exc:
        warnings.append(f"openpyxl Excel read failed: {exc}")
        return None
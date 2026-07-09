import os
import logging
from typing import List, Optional

from dav_tool.config import DEFAULT_ENCODING
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)


def _read_sample_lines(
    file_path: str,
    n: int,
    source: Optional[IDataSource] = None,
) -> List[str]:
    """Read up to *n* lines from a file via source stream or local open."""
    if source is not None:
        try:
            raw = source.read_sample(file_path, n=n)
            return [line.rstrip("\n\r") for line in raw.splitlines()]
        except Exception:
            return []
    try:
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            return [f.readline().rstrip("\n\r") for _ in range(n)]
    except Exception:
        return []


def _count_delimiters_outside_quotes(line: str, delimiter: str) -> int:
    count = 0
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == delimiter and not in_quotes:
            count += 1
    return count


def detect_file_type(file_path, source: Optional[IDataSource] = None):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return "excel", None
        lines = _read_sample_lines(file_path, 5, source)
        lines = [l for l in lines if l]

        delimiters = [",", "|", "\t", ";"]
        scores = {d: sum(_count_delimiters_outside_quotes(line, d) for line in lines) for d in delimiters}
        best = max(scores, key=scores.get)

        if scores[best] > 0:
            return "delimited", best
        return "fixed", None
    except Exception as e:
        logger.warning("Could not detect file type for %s: %s", file_path, e)
        return None, None


def is_multiline_record(file_path, source: Optional[IDataSource] = None):
    """Detect delimited multiline (H|D|) or fixed-width HDR multiline."""
    try:
        lines = _read_sample_lines(file_path, 10, source)
        lines = [l.strip() for l in lines if l.strip()]
        if not lines:
            return False

        # Check for header row: if first line contains values with 3+ alphabetic chars
        # (column names like "Product", "Store"), it's unlikely to be multiline
        def _first_line_is_header():
            if not lines:
                return False
            for delim in (",", "|", "\t", ";"):
                if delim in lines[0]:
                    parts = lines[0].split(delim)
                    long_names = sum(1 for p in parts if len(p.strip()) >= 3 and any(c.isalpha() for c in p.strip()))
                    if long_names >= len(parts) * 0.4:
                        return True
                    return False
            return False

        # Check delimited multiline: 2+ single-letter prefixes (H|, D|, etc.)
        alpha_prefixes = set()
        alpha_count = 0
        for line in lines:
            if len(line) >= 2 and line[0].isalpha() and line[1] in ",|\t;":
                alpha_prefixes.add(line[0])
                alpha_count += 1

        # Require at least 2 distinct prefixes AND at least 40% of lines match
        # AND the first line doesn't look like a header
        if len(alpha_prefixes) >= 2 and alpha_count >= len(lines) * 0.4 and not _first_line_is_header():
            return True

        # Check backslash continuations
        backslash = sum(line.rstrip().endswith("\\") for line in lines)
        if backslash >= 5:
            return True

        # Check fixed-width HDR multiline: some lines start with alphabetic
        # prefix (2+ letters) followed by digits — the rest are plain data lines
        text_prefixes = set()
        data_count = 0
        for line in lines:
            found = False
            for i in range(2, min(6, len(line))):
                if line[:i].isalpha() and i < len(line) and line[i].isdigit():
                    text_prefixes.add(line[:i])
                    found = True
                    break
            if not found and line and line[0].isdigit():
                data_count += 1

        if len(text_prefixes) >= 1 and data_count >= 2:
            return True

        return False
    except Exception as e:
        logger.warning("Could not detect multiline record for %s: %s", file_path, e)
        return False


def detect_hdr_prefix(file_path, sample_lines=20, source: Optional[IDataSource] = None):
    """Detect multi-character HDR prefix (e.g. HDR) in fixed-width multiline."""
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)

        prefixes = set()
        for line in lines:
            if not line:
                continue
            # Look for 2+ alpha chars followed by digit — common HDR pattern
            for i in range(2, min(6, len(line))):
                if line[:i].isalpha() and i < len(line) and line[i].isdigit():
                    prefixes.add(line[:i])
                    break

        return sorted(prefixes, key=len, reverse=True)
    except Exception as e:
        logger.warning("Could not detect HDR prefix for %s: %s", file_path, e)
        return []


def detect_record_types(file_path, delimiter=None, sample_lines=50, source: Optional[IDataSource] = None):
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)

        prefixes = set()
        for line in lines:
            if not line:
                continue
            first = line[0]
            if first.isalpha() and len(line) >= 2:
                sep = line[1]
                if sep in ",|\t;" if delimiter is None else sep == delimiter:
                    prefixes.add(first)

        return sorted(prefixes)
    except Exception as e:
        logger.warning("Could not detect record types for %s: %s", file_path, e)
        return []


def has_header(file_path, delimiter=",", source: Optional[IDataSource] = None):
    try:
        lines = _read_sample_lines(file_path, 1, source)
        first_line = lines[0].strip() if lines else ""

        if not first_line:
            return False

        values = first_line.split(delimiter)
        alpha_count = sum(any(c.isalpha() for c in v) for v in values)
        return alpha_count >= len(values) / 2
    except Exception as e:
        logger.warning("Could not detect header for %s: %s", file_path, e)
        return False

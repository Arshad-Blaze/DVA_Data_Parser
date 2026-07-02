import os
import logging
from dav_tool.config import DEFAULT_ENCODING

logger = logging.getLogger(__name__)


def _count_delimiters_outside_quotes(line: str, delimiter: str) -> int:
    count = 0
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == delimiter and not in_quotes:
            count += 1
    return count


def detect_file_type(file_path):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return "excel", None
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            lines = [f.readline() for _ in range(5)]

        delimiters = [",", "|", "\t", ";"]
        scores = {d: sum(_count_delimiters_outside_quotes(line, d) for line in lines) for d in delimiters}
        best = max(scores, key=scores.get)

        if scores[best] > 0:
            return "delimited", best
        return "fixed", None
    except Exception as e:
        logger.warning("Could not detect file type for %s: %s", file_path, e)
        return None, None


def is_multiline_record(file_path):
    """Detect delimited multiline (H|D|) or fixed-width HDR multiline."""
    try:
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            lines = [f.readline().strip() for _ in range(10)]

        lines = [l for l in lines if l]
        if not lines:
            return False

        # Check delimited multiline: 2+ single-letter prefixes (H|, D|, etc.)
        alpha_prefixes = set()
        for line in lines:
            if len(line) >= 2 and line[0].isalpha() and line[1] in ",|\t;":
                alpha_prefixes.add(line[0])

        if len(alpha_prefixes) >= 2:
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
            if len(line) >= 3 and line[:2].isalpha() and line[2].isdigit():
                text_prefixes.add(line[:3])
            elif line and line[0].isdigit():
                data_count += 1

        if len(text_prefixes) >= 1 and data_count >= 2:
            return True

        return False
    except Exception as e:
        logger.warning("Could not detect multiline record for %s: %s", file_path, e)
        return False


def detect_hdr_prefix(file_path, sample_lines=20):
    """Detect multi-character HDR prefix (e.g. HDR) in fixed-width multiline."""
    try:
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            lines = [f.readline().strip() for _ in range(sample_lines)]

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


def detect_record_types(file_path, delimiter=None, sample_lines=50):
    try:
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            lines = [f.readline().strip() for _ in range(sample_lines)]

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


def has_header(file_path, delimiter=","):
    try:
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            first_line = f.readline().strip()

        if not first_line:
            return False

        values = first_line.split(delimiter)
        alpha_count = sum(any(c.isalpha() for c in v) for v in values)
        return alpha_count >= len(values) / 2
    except Exception as e:
        logger.warning("Could not detect header for %s: %s", file_path, e)
        return False

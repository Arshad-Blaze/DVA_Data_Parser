import os
import re
import time
import logging
from collections import Counter
from typing import Any, List, Optional, Dict, Tuple

from dav_tool._observability import log_phase
from dav_tool.config import DEFAULT_ENCODING
from dav_tool.datasource.base import IDataSource
from dav_tool.io import safe_read_csv

logger = logging.getLogger(__name__)

__all__ = [
    "detect_record_length",
    "detect_candidate_layout",
    "detect_disclaimer_lines",
    "detect_start_line",
    "detect_record_prefix",
    "detect_file_type",
    "is_multiline_record",
    "detect_hdr_prefix",
    "detect_record_types",
    "has_header",
    "detect_trailer_prefix",
    "compute_confidence_score",
    "generate_detection_summary",
    "detect_candidate_columns",
    "detect_candidate_keys",
    "detect_relationship_keys",
    "detect_encoding",
    "detect_date_columns",
    "detect_quantity_columns",
    "detect_weight_columns",
    "detect_uom_columns",
    "detect_delimiter_scores",
]

# Trailer prefixes in order of precedence for auto-detection
TRAILER_PREFIX_CANDIDATES = ["TRL", "TR", "T", "TL", "TRAILER", "F"]

# Minimum sample lines for reliable fixed-width analysis
_FIXED_WIDTH_MIN_SAMPLE = 20
# Minimum consistency ratio for a candidate boundary
_BOUNDARY_CONSISTENCY_RATIO = 0.6


def _has_trailer_candidate(lines: List[str], prefix: str) -> bool:
    """Check if at least 2 lines start with *prefix* followed by digit/delimiter."""
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            rest = stripped[len(prefix):]
            if rest and (rest[0].isdigit() or rest[0] in ",|\t;"):
                count += 1
    return count >= 2


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
        except Exception as e:
            logger.warning("Failed to read sample from source for %s: %s", file_path, e)
            return []
    try:
        with open(file_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            return [f.readline().rstrip("\n\r") for _ in range(n)]
    except Exception as e:
        logger.warning("Failed to read local sample for %s: %s", file_path, e)
        return []


def detect_encoding(
    file_path: str,
    source: Optional[IDataSource] = None,
) -> str:
    """Detect file encoding by trying common encodings on the first 1024 bytes.

    Tries ``cp1252``, ``utf-8``, ``utf8-lossy``, ``latin-1`` in order.
    Returns the first encoding that decodes without error, or ``"utf8-lossy"``
    as a last resort.
    """
    candidates = ["cp1252", "utf-8", "utf8-lossy", "latin-1"]
    try:
        if source is not None:
            try:
                stream = source.open_stream(file_path)
                raw_bytes = stream.read(1024)
                stream.close()
            except Exception as e:
                logger.warning("Failed to open stream for encoding detection: %s", e)
                raw_bytes = None
            if raw_bytes:
                for enc in candidates:
                    try:
                        raw_bytes.decode(enc)
                        return enc
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                return "utf8-lossy"
        for enc in candidates:
            with open(file_path, "rb") as f:
                raw_bytes = f.read(1024)
            try:
                raw_bytes.decode(enc)
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf8-lossy"
    except Exception as e:
        logger.warning("Encoding detection failed for %s: %s", file_path, e)
        return "utf8-lossy"


def _is_fixed_width_line(line: str) -> bool:
    """Check if a line looks like fixed-width data (no consistent delimiter)."""
    if not line or len(line) < 5:
        return False
    for d in (",", "|", "\t", ";"):
        if line.count(d) >= 3:
            return False
    return True


def detect_record_length(
    file_path: str,
    source: Optional[IDataSource] = None,
    sample_lines: int = _FIXED_WIDTH_MIN_SAMPLE,
) -> Optional[int]:
    """Detect the common record length in a fixed-width file.

    Reads sample lines and returns the most common line length
    among non-empty, non-delimited lines. Returns None if no
    consistent length is found.
    """
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)
        lines = [l.rstrip("\n\r") for l in lines if l.strip()]

        fw_lines = [l for l in lines if _is_fixed_width_line(l)]
        if not fw_lines:
            return None

        lengths = [len(l) for l in fw_lines]
        counter = Counter(lengths)
        most_common_len, count = counter.most_common(1)[0]

        if count < len(fw_lines) * _BOUNDARY_CONSISTENCY_RATIO:
            return None

        return most_common_len
    except Exception as e:
        logger.warning("Could not detect record length for %s: %s", file_path, e)
        return None


def _detect_column_boundaries(
    lines: List[str],
    record_length: int,
) -> List[Tuple[int, int]]:
    """Detect column boundaries in fixed-width lines.

    Analyzes character positions across multiple lines to identify
    column boundaries based on:
    - Whitespace gaps (runs of spaces consistent across lines)
    - Character type transitions (digit→alpha, alpha→digit)
    - Consistent separator characters (|, -, etc.)

    Returns a list of (start, end) tuples for each detected column.
    """
    if not lines:
        return []

    n_lines = len(lines)
    # Truncate/pad all lines to record_length
    normalized = []
    for l in lines:
        if len(l) >= record_length:
            normalized.append(l[:record_length])
        else:
            normalized.append(l + " " * (record_length - len(l)))

    # Score each position as a potential boundary
    # A position is a boundary if it's consistently a space or
    # consistently separates character types
    boundary_scores = [0.0] * (record_length + 1)
    boundary_scores[0] = 0.0
    boundary_scores[record_length] = 0.0

    for pos in range(1, record_length):
        space_count = sum(1 for l in normalized if l[pos - 1] == " " or l[pos] == " ")
        space_ratio = space_count / n_lines

        # Character type transitions
        type_transitions = 0
        for l in normalized:
            if pos < len(l):
                prev_c = l[pos - 1]
                curr_c = l[pos]
                prev_is_digit = prev_c.isdigit()
                curr_is_digit = curr_c.isdigit()
                prev_is_alpha = prev_c.isalpha()
                curr_is_alpha = curr_c.isalpha()
                if (prev_is_digit and curr_is_alpha) or (prev_is_alpha and curr_is_digit):
                    type_transitions += 1
        transition_ratio = type_transitions / n_lines

        # Consistent separator character
        sep_count = 0
        separators = set()
        for l in normalized:
            if pos < len(l) and l[pos] in ("|", "-", "_", "."):
                sep_count += 1
                separators.add(l[pos])
        sep_ratio = sep_count / n_lines
        sep_bonus = sep_ratio if len(separators) <= 2 else 0.0

        boundary_scores[pos] = space_ratio * 0.5 + transition_ratio * 0.3 + sep_bonus * 0.2

    # Find column boundaries: positions where score exceeds threshold
    # or where there's a clear gap (space_ratio > 0.8)
    min_threshold = _BOUNDARY_CONSISTENCY_RATIO * 0.5
    gap_threshold = 0.8

    boundaries = [0]
    in_gap = False
    for pos in range(1, record_length):
        space_ratio = sum(1 for l in normalized if l[pos] == " ") / n_lines
        in_gap_now = space_ratio > gap_threshold

        if in_gap_now and not in_gap and pos - boundaries[-1] >= 2:
            if boundary_scores[pos] >= min_threshold:
                boundaries.append(pos)
        elif not in_gap_now and in_gap:
            if boundary_scores[pos] >= min_threshold:
                boundaries.append(pos)
        elif boundary_scores[pos] >= _BOUNDARY_CONSISTENCY_RATIO and pos - boundaries[-1] >= 2:
            boundaries.append(pos)

        in_gap = in_gap_now

    if boundaries[-1] != record_length:
        boundaries.append(record_length)

    # Deduplicate and create intervals
    boundaries = sorted(set(boundaries))
    columns = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end - start >= 2:
            columns.append((start, end))

    return columns


def _infer_column_type(lines: List[str], start: int, end: int) -> str:
    """Infer the data type of a column from sample lines."""
    values = []
    for l in lines:
        if start < len(l):
            val = l[start:end].strip()
            if val:
                values.append(val)

    if not values:
        return "text"

    digit_count = sum(1 for v in values if v.replace(".", "").replace("-", "").isdigit())
    date_count = sum(1 for v in values if _looks_like_date(v))
    alpha_count = sum(1 for v in values if any(c.isalpha() for c in v))

    total = len(values)
    if digit_count / total >= 0.8:
        return "numeric"
    if date_count / total >= 0.6:
        return "date"

    return "text"


def _looks_like_date(value: str) -> bool:
    """Check if a value looks like a date."""
    date_patterns = [
        r"^\d{2}[/-]\d{2}[/-]\d{2,4}$",
        r"^\d{4}[/-]\d{2}[/-]\d{2}$",
        r"^\d{2}[/-]\d{2,4}$",
        r"^\d{6}$",
        r"^\d{8}$",
    ]
    return any(re.match(p, value) for p in date_patterns)


def detect_candidate_layout(
    file_path: str,
    record_length: Optional[int] = None,
    source: Optional[IDataSource] = None,
    sample_lines: int = _FIXED_WIDTH_MIN_SAMPLE,
) -> List[Dict]:
    """Propose a candidate column layout for a fixed-width file.

    Uses whitespace analysis and character-type transitions to
    automatically detect column boundaries. Each returned dict
    has keys: ``field``, ``start``, ``end``, ``length``, ``type``.

    Returns an empty list if no layout can be determined.
    """
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)
        lines = [l.rstrip("\n\r") for l in lines if l.strip()]

        fw_lines = [l for l in lines if _is_fixed_width_line(l)]
        if not fw_lines:
            return []

        if record_length is None:
            lengths = [len(l) for l in fw_lines]
            counter = Counter(lengths)
            record_length, count = counter.most_common(1)[0]
            if count < len(fw_lines) * _BOUNDARY_CONSISTENCY_RATIO:
                return []

        boundaries = _detect_column_boundaries(fw_lines, record_length)
        if not boundaries:
            return []

        layout = []
        for i, (start, end) in enumerate(boundaries):
            col_type = _infer_column_type(fw_lines, start, end)
            layout.append({
                "field": f"Column_{i + 1}",
                "start": start,
                "end": end,
                "length": end - start,
                "type": col_type,
                "from": start + 1,
            })

        return layout
    except Exception as e:
        logger.warning("Could not detect candidate layout for %s: %s", file_path, e)
        return []


def detect_disclaimer_lines(
    file_path: str,
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    record_length: Optional[int] = None,
    source: Optional[IDataSource] = None,
    sample_lines: int = 50,
) -> List[int]:
    """Detect leading non-data lines (disclaimers, blank lines, legal text).

    Reads leading lines and identifies those that don't match the
    expected data pattern. Returns a list of 0-indexed line numbers
    that are disclaimers. Only consecutive leading disclaimers are
    reported — once a data line is found, trailing lines are ignored.
    """
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)
        if not lines:
            return []

        disclaimer_indices: List[int] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                disclaimer_indices.append(i)
                continue

            if file_type == "fixed":
                if record_length and len(stripped) < record_length * 0.5:
                    disclaimer_indices.append(i)
                    continue
                if _is_fixed_width_line(stripped):
                    break
                disclaimer_indices.append(i)
                continue

            if file_type == "delimited" and delimiter:
                delim_count = line.count(delimiter)
                if delim_count <= 1:
                    disclaimer_indices.append(i)
                    continue
                break

            # Unknown type — guess: non-data lines are all-alpha or short
            words = stripped.split()
            avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
            if len(stripped) < 10 or (avg_word_len > 6 and any(c.isalpha() for c in stripped)):
                disclaimer_indices.append(i)
                continue
            break

        return disclaimer_indices
    except Exception as e:
        logger.warning("Could not detect disclaimer lines for %s: %s", file_path, e)
        return []


def detect_start_line(
    file_path: str,
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    record_length: Optional[int] = None,
    source: Optional[IDataSource] = None,
    sample_lines: int = 50,
) -> int:
    """Detect the first data line after disclaimers and headers.

    Returns the 0-indexed line number where actual data begins.
    Returns 0 if no disclaimers or headers are detected.
    """
    try:
        disclaimers = detect_disclaimer_lines(
            file_path, file_type=file_type, delimiter=delimiter,
            record_length=record_length, source=source, sample_lines=sample_lines,
        )
        if not disclaimers:
            return 0

        start = max(disclaimers) + 1

        # Check if the first data line looks like a header
        lines = _read_sample_lines(file_path, start + 5, source)
        if start < len(lines):
            first_data = lines[start].strip()
            if _looks_like_header_line(first_data, delimiter=delimiter):
                return start + 1

        return start
    except Exception as e:
        logger.warning("Could not detect start line for %s: %s", file_path, e)
        return 0


def _looks_like_header_line(line: str, delimiter: Optional[str] = None) -> bool:
    """Check if a line looks like a header row (alphabetic column names)."""
    if not line:
        return False

    if delimiter and delimiter in line:
        parts = line.split(delimiter)
    else:
        parts = line.split()
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        return False

    alpha_parts = sum(1 for p in parts if any(c.isalpha() for c in p) and not p.replace(".", "").replace("-", "").isdigit())
    return alpha_parts >= len(parts) * 0.5


def detect_record_prefix(
    file_path: str,
    file_type: Optional[str] = None,
    source: Optional[IDataSource] = None,
    sample_lines: int = 100,
) -> List[str]:
    """Discover fixed-width record type prefixes (e.g. U, D, S).

    Scans sample lines and collects single-character alphabetic
    prefixes at position 0 that appear on at least 2 lines.
    Returns sorted list of discovered prefixes.
    Only applies to fixed-width files — returns empty for delimited.
    """
    if file_type == "delimited":
        return []

    try:
        lines = _read_sample_lines(file_path, sample_lines, source)
        if not lines:
            return []

        prefix_counts: Counter = Counter()
        data_like_count = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _is_fixed_width_line(stripped):
                data_like_count += 1
                first_char = stripped[0]
                if first_char.isalpha() and first_char.isupper():
                    prefix_counts[first_char] += 1

        # A prefix is valid if it appears on >= 2 data-like lines
        prefixes = [p for p, c in prefix_counts.items() if c >= 2]

        return sorted(prefixes)
    except Exception as e:
        logger.warning("Could not detect record prefix for %s: %s", file_path, e)
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


def detect_delimiter_scores(
    file_path: str,
    source: Optional[IDataSource] = None,
    sample_lines: int = 5,
) -> Dict[str, int]:
    """Count delimiter occurrences across sample lines.

    Returns a dict mapping each candidate delimiter to its total count
    across all sampled lines. Delimiters checked: ``,``, ``|``, ``\\t``, ``;``.
    """
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)
        lines = [l for l in lines if l]
        delimiters = [",", "|", "\t", ";"]
        return {d: sum(_count_delimiters_outside_quotes(line, d) for line in lines) for d in delimiters}
    except Exception as e:
        logger.warning("Could not compute delimiter scores for %s: %s", file_path, e)
        return {}


def detect_file_type(file_path, source: Optional[IDataSource] = None):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return "excel", None
        scores = detect_delimiter_scores(file_path, source=source, sample_lines=5)
        best = max(scores, key=scores.get)

        if scores[best] > 0:
            return "delimited", best
        return "fixed", None
    except Exception as e:
        logger.warning("Could not detect file type for %s: %s", file_path, e)
        return None, None


def detect_date_columns(
    file_path: str,
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    columns: Optional[List[str]] = None,
    layout: Optional[List[Dict]] = None,
    record_length: Optional[int] = None,
    start_line: int = 0,
    source: Optional[IDataSource] = None,
    sample_lines: int = 100,
) -> List[Dict]:
    """Detect columns that likely contain date values.

    Analyses sample data for each column (delimited) or layout column (fixed-width)
    and returns a list of dicts: ``column``, ``type`` (always ``"date"``),
    ``confidence``, ``match_ratio``.

    Uses a 60 % threshold — columns where >=60 % of non-empty values match
    known date patterns are reported.
    """
    try:
        if file_type == "delimited" and delimiter and columns:
            records = _parse_sample_data(
                file_path, file_type=file_type, delimiter=delimiter,
                start_line=start_line, source=source, sample_lines=sample_lines,
            )
            results = []
            for col in columns:
                values = [r.get(col, "") for r in records if r.get(col, "")]
                if not values:
                    continue
                date_count = sum(1 for v in values if _looks_like_date(v))
                ratio = date_count / len(values)
                if ratio >= 0.6:
                    results.append({
                        "column": col,
                        "type": "date",
                        "confidence": round(ratio, 2),
                        "match_ratio": round(ratio, 2),
                    })
            return results

        if file_type == "fixed" and layout:
            fw_lines = _read_sample_lines(file_path, sample_lines, source)
            fw_lines = [l.rstrip("\n\r") for l in fw_lines if l.strip()]
            results = []
            for col_def in layout:
                start = col_def.get("start", 0)
                end = col_def.get("end", start + col_def.get("length", 1))
                col_name = col_def.get("field", f"Column_{start}")
                values = []
                for line in fw_lines:
                    if start < len(line):
                        val = line[start:end].strip()
                        if val:
                            values.append(val)
                if not values:
                    continue
                date_count = sum(1 for v in values if _looks_like_date(v))
                ratio = date_count / len(values)
                if ratio >= 0.6:
                    results.append({
                        "column": col_name,
                        "type": "date",
                        "confidence": round(ratio, 2),
                        "match_ratio": round(ratio, 2),
                    })
            return results

        return []
    except Exception as e:
        logger.warning("Could not detect date columns for %s: %s", file_path, e)
        return []


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

        # Check fixed-width HDR multiline: lines start with alphabetic
        # prefix (2+ letters) followed by digits — plain data lines don't.
        # Require the prefix to repeat on multiple lines (not a one-off)
        # and data lines must NOT contain common delimiters (ruling out CSVs
        # with alphanumerics like "Store123,Product456,75").
        prefix_line_count = {}
        data_count = 0
        has_delimiter_data = False
        for line in lines:
            found = False
            for i in range(2, min(6, len(line))):
                if line[:i].isalpha() and i < len(line) and line[i].isdigit():
                    prefix_line_count[line[:i]] = prefix_line_count.get(line[:i], 0) + 1
                    found = True
                    break
            if not found and line and line[0].isdigit():
                data_count += 1
                if any(d in line for d in ",|\t;"):
                    has_delimiter_data = True

        # Require prefix to repeat on 2+ lines AND no delimiter in data lines
        repeated = sum(1 for cnt in prefix_line_count.values() if cnt >= 2)
        if repeated >= 1 and data_count >= 2 and not has_delimiter_data:
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


def detect_trailer_prefix(file_path, sample_lines=50, source: Optional[IDataSource] = None):
    """Auto-detect trailer prefix (e.g. TRL, T, TRAILER) in multiline files.

    Checks common trailer prefix candidates against the last portion of the
    sample — trailer records typically appear near the end.
    Returns the first confirmed prefix or None.
    Favours shorter, common prefixes over longer ones.
    """
    try:
        lines = _read_sample_lines(file_path, sample_lines, source)
        lines = [l.strip() for l in lines if l.strip()]
        if not lines:
            return None

        for candidate in TRAILER_PREFIX_CANDIDATES:
            if _has_trailer_candidate(lines, candidate):
                return candidate

        return None
    except Exception as e:
        logger.warning("Could not detect trailer prefix for %s: %s", file_path, e)
        return None


def compute_confidence_score(detection_result: Dict) -> float:
    """Compute a confidence score (0.0–1.0) for a detection result dict.

    Evaluates:
    - File type detection certainty
    - Delimiter consistency across sampled lines
    - Multiline vs HDR classification ambiguity
    - Header line confidence
    - Trailer detection completeness
    """
    score = 1.0
    file_type = detection_result.get("file_type")

    if file_type is None:
        return 0.0

    if file_type == "fixed":
        score -= 0.3  # fixed-width is the fallback — least confident

    if file_type == "delimited":
        delim = detection_result.get("delimiter")
        scores = detection_result.get("_delimiter_scores", {})
        if delim and scores:
            best_score = scores.get(delim, 0)
            next_best = sorted(scores.values(), reverse=True)
            next_best = next_best[1] if len(next_best) > 1 else 0
            if best_score == 0:
                score -= 0.3
            elif best_score < next_best * 2:
                score -= 0.15  # ambiguous delimiter

    if detection_result.get("is_multiline"):
        if not detection_result.get("header_prefix") and not detection_result.get("ml_record_types"):
            score -= 0.2

    has_trailer = detection_result.get("trailer_prefix") is not None
    is_multiline = detection_result.get("is_multiline", False)
    if is_multiline and not has_trailer:
        score -= 0.1  # possible missing trailer

    header = detection_result.get("has_header", False)
    if file_type == "delimited" and not header:
        score -= 0.1  # no header row makes column naming harder

    return max(0.0, round(score, 2))


def compute_confidence_breakdown(detection_result: Dict) -> List[str]:
    """Return a human-readable list of factors that affected confidence.

    Each entry describes why a penalty was applied (or why no penalty).
    """
    reasons: List[str] = []
    file_type = detection_result.get("file_type")

    if file_type is None:
        return ["File type could not be determined — confidence = 0.0"]

    if file_type == "fixed":
        reasons.append("Fixed-width format detected — base penalty: -0.30 (fallback format)")

    if file_type == "delimited":
        delim = detection_result.get("delimiter")
        scores = detection_result.get("_delimiter_scores", {})
        if delim and scores:
            best_score = scores.get(delim, 0)
            next_best = sorted(scores.values(), reverse=True)
            next_best_val = next_best[1] if len(next_best) > 1 else 0
            if best_score == 0:
                reasons.append(f"Delimiter '{delim}' scored 0 in sample — penalty: -0.30")
            elif best_score < next_best_val * 2:
                reasons.append(f"Delimiter '{delim}' ambiguous (score {best_score} vs next {next_best_val}) — penalty: -0.15")
            else:
                reasons.append(f"Delimiter '{delim}' cleanly detected (score {best_score}) — no penalty")
        else:
            reasons.append("No delimiter scores available — partial penalty: -0.30")

    if detection_result.get("is_multiline"):
        if not detection_result.get("header_prefix") and not detection_result.get("ml_record_types"):
            reasons.append("Multiline file with no header prefix or record types detected — penalty: -0.20")
        else:
            reasons.append("Multiline file with header/record types — no penalty")

    is_multiline = detection_result.get("is_multiline", False)
    has_trailer = detection_result.get("trailer_prefix") is not None
    if is_multiline and not has_trailer:
        reasons.append("Multiline file missing trailer prefix — penalty: -0.10")
    elif is_multiline and has_trailer:
        reasons.append("Multiline file with trailer prefix — no penalty")

    header = detection_result.get("has_header", False)
    if file_type == "delimited" and not header:
        reasons.append("No header row detected — penalty: -0.10 (columns will be auto-named)")
    elif file_type == "delimited":
        reasons.append("Header row detected — no penalty")

    return reasons


def generate_detection_summary(
    file_path,
    source: Optional[IDataSource] = None,
) -> Dict:
    """Run all detection heuristics and return a consolidated result dict.

    This is the single detection entry point that fully describes a file.
    Downstream layers MUST consume this dict instead of re-detecting.
    """
    logger.info("DETECTION EXECUTED — %s", file_path)
    log_phase(f"Detection — STARTED ({file_path})")
    t0 = time.time()

    file_type, delimiter = detect_file_type(file_path, source=source)
    multiline = is_multiline_record(file_path, source=source) if file_type else False

    encoding = detect_encoding(file_path, source=source)

    result = {
        "file_path": file_path,
        "file_type": file_type,
        "delimiter": delimiter,
        "encoding": encoding,
        "is_multiline": multiline,
        "has_header": False,
        "header_prefix": None,
        "trailer_prefix": None,
        "ml_record_types": None,
        "record_length": None,
        "candidate_layout": [],
        "disclaimer_lines": [],
        "start_line": 0,
        "record_prefix": None,
        "candidate_keys": [],
        "date_columns": [],
        "quantity_columns": [],
        "weight_columns": [],
        "uom_columns": [],
        "columns": [],
        "confidence": 0.0,
        "warnings": [],
        "recommendations": [],
    }

    if file_type is None:
        result["warnings"].append("File type could not be determined")
        result["recommendations"].append("Verify the file format is supported (delimited, fixed-width, multiline, or Excel)")
        result["confidence"] = 0.0
        return result

    if file_type == "excel":
        result["confidence"] = 1.0
        return result

    # Delimiter consistency check
    if file_type == "delimited":
        delim_scores = detect_delimiter_scores(file_path, source=source, sample_lines=5)
        result["_delimiter_scores"] = delim_scores
        if delim_scores.get(delimiter, 0) == 0:
            result["warnings"].append(f"Delimiter '{delimiter}' found 0 times in sample")

    # Fixed-width detection
    if file_type == "fixed":
        record_length = detect_record_length(file_path, source=source)
        if record_length:
            result["record_length"] = record_length
            candidate = detect_candidate_layout(file_path, record_length=record_length, source=source)
            if candidate:
                result["candidate_layout"] = candidate
                columns = [c["field"] for c in candidate]
                result["columns"] = columns
                result["recommendations"].append(
                    f"Auto-detected {len(candidate)} columns from fixed-width layout — review in Layout Builder"
                )
            else:
                result["warnings"].append("Fixed-width file detected but could not determine column layout")
                result["recommendations"].append("Use the Layout Builder to define column positions manually")
        else:
            result["warnings"].append("Fixed-width file detected but could not determine record length")
            result["recommendations"].append("Verify record length is consistent across data lines")

    # Disclaimer and start line detection
    if file_type in ("fixed", "delimited"):
        disclaimers = detect_disclaimer_lines(
            file_path, file_type=file_type, delimiter=delimiter,
            record_length=result.get("record_length"), source=source,
        )
        if disclaimers:
            result["disclaimer_lines"] = disclaimers
            start_line = detect_start_line(
                file_path, file_type=file_type, delimiter=delimiter,
                record_length=result.get("record_length"), source=source,
            )
            if start_line:
                result["start_line"] = start_line
                result["recommendations"].append(
                    f"Auto-detected start line at line {start_line + 1} — review if data skipping is needed"
                )

    # Record prefix detection for fixed-width
    if file_type == "fixed":
        prefixes = detect_record_prefix(file_path, file_type=file_type, source=source)
        if prefixes:
            result["record_prefix"] = prefixes

    # Multiline detection
    if multiline:
        hdr_prefixes = detect_hdr_prefix(file_path, source=source)
        if hdr_prefixes:
            result["header_prefix"] = hdr_prefixes[0]
        record_types = detect_record_types(file_path, delimiter=delimiter, source=source)
        if record_types:
            result["ml_record_types"] = record_types
        trailer = detect_trailer_prefix(file_path, source=source)
        if trailer:
            result["trailer_prefix"] = trailer
        else:
            result["warnings"].append("No trailer prefix detected — trailer may exist or file may lack trailers")
            result["recommendations"].append("If the file has trailer records, set trailer_prefix manually")

    # Header detection
    if file_type == "delimited" and delimiter:
        result["has_header"] = has_header(file_path, delimiter=delimiter, source=source)
        if not result["has_header"]:
            result["warnings"].append("No header row detected — columns will be auto-named")
            result["recommendations"].append("Consider adding a header row or configuring column names")

    # Columns
    if file_type == "delimited" and delimiter:
        try:
            df = safe_read_csv(file_path, separator=delimiter, n_rows=5, source=source)
            result["columns"] = df.columns
        except Exception as e:
            result["warnings"].append(f"Could not read columns: {e}")

    # Business key detection
    columns_list = result.get("columns", [])
    if columns_list and file_type in ("delimited", "fixed"):
        try:
            layout_for_keys = result.get("candidate_layout") or None
            candidate_keys = detect_candidate_keys(
                file_path, columns_list,
                file_type=file_type, delimiter=delimiter,
                layout=layout_for_keys,
                record_length=result.get("record_length"),
                start_line=result.get("start_line", 0),
                source=source,
            )
            if candidate_keys:
                result["candidate_keys"] = candidate_keys
        except Exception as e:
            logger.warning("Could not detect candidate keys for %s: %s", file_path, e)

    # Date column detection
    if columns_list and file_type in ("delimited", "fixed"):
        try:
            date_cols = detect_date_columns(
                file_path, file_type=file_type, delimiter=delimiter,
                columns=columns_list,
                layout=result.get("candidate_layout"),
                record_length=result.get("record_length"),
                start_line=result.get("start_line", 0),
                source=source,
            )
            if date_cols:
                result["date_columns"] = date_cols
        except Exception as e:
            logger.warning("Could not detect date columns for %s: %s", file_path, e)

    # Quantity / Weight / UOM column detection
    if columns_list and file_type in ("delimited", "fixed"):
        try:
            qty_cols = detect_quantity_columns(columns_list)
            if qty_cols:
                result["quantity_columns"] = qty_cols
            wt_cols = detect_weight_columns(columns_list)
            if wt_cols:
                result["weight_columns"] = wt_cols
            uom_cols = detect_uom_columns(columns_list)
            if uom_cols:
                result["uom_columns"] = uom_cols
        except Exception as e:
            logger.warning("Could not detect quantity/weight/uom columns for %s: %s", file_path, e)

    result["confidence"] = compute_confidence_score(result)
    result["confidence_breakdown"] = compute_confidence_breakdown(result)
    elapsed = time.time() - t0
    logger.info("DETECTION COMPLETED — %s (%s, confidence=%s, %.2fs)", file_path, file_type, result['confidence'], elapsed)
    log_phase(f"Detection — COMPLETED ({file_type}, confidence={result['confidence']}, {elapsed:.2f}s)")
    return result


def detect_candidate_columns(columns: List[str]) -> Dict[str, Optional[str]]:
    """Heuristically propose canonical column mappings from physical column names.

    Returns a dict mapping canonical roles to candidate physical column names:
    ``store``, ``upc``, ``description``, ``units``, ``price``, ``weight_qty``,
    ``weight_uom``, ``units_uom``.
    """
    candidates: Dict[str, Optional[str]] = {
        "store": None,
        "upc": None,
        "description": None,
        "units": None,
        "price": None,
        "weight_qty": None,
        "weight_uom": None,
        "units_uom": None,
    }

    col_lower = {c: c.lower().strip() for c in columns}

    for phys_col, name in col_lower.items():
        # Store
        if any(kw in name for kw in ["store", "store_nbr", "location", "site", "branch"]):
            candidates["store"] = candidates["store"] or phys_col

        # UPC
        if any(kw in name for kw in ["upc", "sku", "item", "product_code", "plu", "barcode"]):
            candidates["upc"] = candidates["upc"] or phys_col

        # Description
        if any(kw in name for kw in ["desc", "name", "product", "item_desc", "title", "label"]):
            candidates["description"] = candidates["description"] or phys_col

        # Units (quantity count)
        if any(kw in name for kw in ["unit", "qty", "quantity", "count", "sold", "volume"]):
            if "uom" not in name and "weight" not in name and "lb" not in name and "kg" not in name:
                candidates["units"] = candidates["units"] or phys_col

        # Price
        if any(kw in name for kw in ["price", "amount", "total", "sales", "dollar", "revenue", "cost", "ext"]):
            candidates["price"] = candidates["price"] or phys_col

        # Weight quantity
        if any(kw in name for kw in ["weight", "lb", "kg", "pound"]):
            if "uom" not in name:
                candidates["weight_qty"] = candidates["weight_qty"] or phys_col
                if candidates["units"] == phys_col:
                    candidates["units"] = None

        # Weight UOM
        if any(kw in name for kw in ["uom", "measure", "unit_of_measure"]):
            if any(w in name for w in ["weight", "lb", "kg"]):
                candidates["weight_uom"] = candidates["weight_uom"] or phys_col
            else:
                candidates["units_uom"] = candidates["units_uom"] or phys_col

    return candidates


def detect_quantity_columns(
    columns: List[str],
    sample_data: Optional[List[Dict[str, str]]] = None,
) -> List[Dict]:
    """Detect columns likely to contain quantity / unit counts.

    Uses column name keywords and, when sample data is provided,
    validates that the column values are numeric.

    Returns a list of dicts: ``column``, ``type`` (``"quantity"``), ``confidence``.
    """
    keywords = ["unit", "qty", "quantity", "count", "sold", "volume"]
    results = []
    for col in columns:
        name_lower = col.lower().strip()
        if any(kw in name_lower for kw in keywords):
            if "uom" in name_lower or "weight" in name_lower or name_lower in ("lb", "kg"):
                continue
            confidence = 0.7
            if sample_data:
                values = [r.get(col, "") for r in sample_data if r.get(col, "")]
                if values:
                    numeric = sum(1 for v in values if v.replace(".", "").replace("-", "").isdigit())
                    if numeric / len(values) < 0.6:
                        confidence = 0.3
            results.append({
                "column": col,
                "type": "quantity",
                "confidence": round(confidence, 2),
            })
    return results


def detect_weight_columns(
    columns: List[str],
    sample_data: Optional[List[Dict[str, str]]] = None,
) -> List[Dict]:
    """Detect columns likely to contain weight values.

    Uses column name keywords (weight, lb, kg, pound) and, when sample
    data is provided, checks that values are numeric.

    Returns a list of dicts: ``column``, ``type`` (``"weight"``), ``confidence``.
    """
    keywords = ["weight", "lb", "kg", "pound"]
    results = []
    for col in columns:
        name_lower = col.lower().strip()
        if any(kw in name_lower for kw in keywords):
            if "uom" in name_lower:
                continue
            confidence = 0.7
            if sample_data:
                values = [r.get(col, "") for r in sample_data if r.get(col, "")]
                if values:
                    numeric = sum(1 for v in values if v.replace(".", "").replace("-", "").isdigit())
                    if numeric / len(values) < 0.6:
                        confidence = 0.3
            results.append({
                "column": col,
                "type": "weight",
                "confidence": round(confidence, 2),
            })
    return results


def detect_uom_columns(
    columns: List[str],
    sample_data: Optional[List[Dict[str, str]]] = None,
) -> List[Dict]:
    """Detect columns likely to contain Unit of Measure values.

    Uses column name keywords (uom, measure, unit_of_measure) and
    distinguishes between weight UOM and generic units UOM.

    Returns a list of dicts: ``column``, ``type`` (``"weight_uom"`` or
    ``"units_uom"``), ``confidence``.
    """
    results = []
    for col in columns:
        name_lower = col.lower().strip()
        if any(kw in name_lower for kw in ["uom", "measure", "unit_of_measure"]):
            if any(w in name_lower for w in ["weight", "lb", "kg"]):
                results.append({"column": col, "type": "weight_uom", "confidence": 0.8})
            else:
                results.append({"column": col, "type": "units_uom", "confidence": 0.8})
    return results


# Pattern definitions for business key detection
_KEY_PATTERNS = {
    "upc": {
        "patterns": [r"^\d{12}$", r"^\d{10}$"],
        "keywords": ["upc", "upc_code", "upc_num", "gtin", "ean", "barcode"],
    },
    "sku": {
        "patterns": [r"^[A-Za-z0-9]{4,20}$"],
        "keywords": ["sku", "sku_code", "item_code", "product_code", "article", "part_no"],
    },
    "store": {
        "patterns": [r"^\d{3,10}$", r"^[A-Za-z]\d{2,9}$"],
        "keywords": ["store", "store_nbr", "location", "site", "branch", "outlet"],
    },
    "upc_description": {
        "patterns": [],
        "keywords": [],
    },
    "date": {
        "patterns": [r"^\d{2}[/-]\d{2}[/-]\d{2,4}$", r"^\d{4}[/-]\d{2}[/-]\d{2}$", r"^\d{8}$"],
        "keywords": ["date", "date_", "trans_date", "bus_date", "business_date", "calday", "day"],
    },
    "item_description": {
        "patterns": [],
        "keywords": ["desc", "description", "item_desc", "name", "product", "title", "label"],
    },
}


def _parse_sample_data(
    file_path: str,
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    record_length: Optional[int] = None,
    start_line: int = 0,
    source: Optional[IDataSource] = None,
    sample_lines: int = 100,
) -> List[Dict[str, str]]:
    """Parse a small sample of lines into column→value dicts for analysis."""
    raw_lines = _read_sample_lines(file_path, start_line + sample_lines, source)
    raw_lines = raw_lines[start_line:]
    raw_lines = [l.rstrip("\n\r") for l in raw_lines if l.strip()]

    records: List[Dict[str, str]] = []

    if file_type == "delimited" and delimiter:
        for line in raw_lines:
            parts = line.split(delimiter)
            records.append({str(i): p.strip() for i, p in enumerate(parts)})
        return records

    if file_type == "fixed" and layout:
        sorted_layout = sorted(layout, key=lambda c: c.get("start", 0))
        for line in raw_lines:
            record = {}
            for col in sorted_layout:
                start = col.get("start", 0)
                end = col.get("end", start + col.get("length", 1))
                if start < len(line):
                    record[col["field"]] = line[start:end].strip()
            if record:
                records.append(record)
        return records

    if file_type == "fixed" and record_length:
        for line in raw_lines:
            if len(line) >= record_length:
                records.append({"0": line[:record_length].strip()})
        return records

    # Fallback: use raw lines as single column
    for line in raw_lines:
        records.append({"0": line.strip()})

    return records


def detect_candidate_keys(
    file_path: str,
    columns: List[str],
    file_type: Optional[str] = None,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    record_length: Optional[int] = None,
    start_line: int = 0,
    source: Optional[IDataSource] = None,
    sample_lines: int = 100,
) -> List[Dict]:
    """Identify columns likely to be business keys (UPC, SKU, Store, etc.).

    Analyzes column names and sample data for:
    - High uniqueness ratio
    - Known value patterns (12-digit UPC, alphanumeric SKU)
    - Column name keywords

    Returns a list of dicts sorted by confidence (highest first):
    ``column``, ``key_type``, ``confidence``, ``uniqueness``, ``pattern_match``, ``name_match``.
    """
    if not columns:
        return []

    sample = _parse_sample_data(
        file_path, file_type=file_type, delimiter=delimiter,
        layout=layout, record_length=record_length,
        start_line=start_line, source=source, sample_lines=sample_lines,
    )
    total_rows = len(sample)

    results: List[Dict] = []

    for col in columns:
        name_lower = col.lower().strip()
        values = [r.get(col, r.get(str(columns.index(col)), "")) for r in sample]
        values = [v for v in values if v]

        if not values:
            continue

        # Uniqueness score
        unique = set(values)
        uniqueness = len(unique) / max(len(values), 1)
        uniqueness_score = min(uniqueness / 0.5, 1.0)  # 0.5+ uniqueness → high score

        # Evaluate each key type
        for key_type, config in _KEY_PATTERNS.items():
            if key_type in ("date",):
                continue  # Dates are not join keys

            # Name match score
            name_score = 0.0
            if config["keywords"]:
                for kw in config["keywords"]:
                    if kw in name_lower or name_lower in kw:
                        name_score = 1.0
                        break
                else:
                    # Partial match: word overlap
                    name_words = set(name_lower.replace("_", " ").split())
                    kw_words = set(" ".join(config["keywords"]).split())
                    overlap = len(name_words & kw_words)
                    if overlap > 0:
                        name_score = min(overlap / 2.0, 0.8)

            # Pattern match score
            pattern_score = 0.0
            if config["patterns"]:
                matches = 0
                for v in values[:min(len(values), 50)]:  # Check up to 50 values
                    for pat in config["patterns"]:
                        if re.match(pat, v):
                            matches += 1
                            break
                pattern_score = matches / max(min(len(values), 50), 1)

            # Combined confidence: weighted average
            confidence = uniqueness_score * 0.4 + name_score * 0.3 + pattern_score * 0.3

            if confidence >= 0.2:
                results.append({
                    "column": col,
                    "key_type": key_type,
                    "confidence": round(confidence, 2),
                    "uniqueness": round(uniqueness, 2),
                    "pattern_match": round(pattern_score, 2),
                    "name_match": round(name_score, 2),
                })

    # Deduplicate: keep only the best key_type per column
    seen_cols: Dict[str, float] = {}
    deduped: List[Dict] = []
    for r in sorted(results, key=lambda x: -x["confidence"]):
        if r["column"] not in seen_cols or seen_cols[r["column"]] < r["confidence"]:
            seen_cols[r["column"]] = r["confidence"]
            deduped.append(r)

    return sorted(deduped, key=lambda x: -x["confidence"])


def detect_relationship_keys(
    source_keys: List[Dict],
    target_keys: List[Dict],
) -> List[Dict]:
    """Suggest join key pairs between two file detection results.

    Takes candidate keys from two files and recommends pairs
    where column names or key types match with sufficient confidence.

    Returns list of dicts: ``source_column``, ``target_column``,
    ``confidence``, ``match_reason``.
    """
    suggestions: List[Dict] = []

    for sk in source_keys:
        for tk in target_keys:
            if sk["key_type"] != tk["key_type"]:
                continue

            # Same key type → good join candidate
            confidence = min(sk["confidence"], tk["confidence"])
            if sk["column"] == tk["column"]:
                confidence = min(1.0, confidence + 0.1)

            suggestions.append({
                "source_column": sk["column"],
                "target_column": tk["column"],
                "key_type": sk["key_type"],
                "confidence": round(confidence, 2),
                "match_reason": f"Matched on key type: {sk['key_type']}",
            })

    return sorted(suggestions, key=lambda x: -x["confidence"])

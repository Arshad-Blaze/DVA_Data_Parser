import os
import logging
from typing import List, Optional, Dict

from dav_tool.config import DEFAULT_ENCODING
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)

# Trailer prefixes in order of precedence for auto-detection
TRAILER_PREFIX_CANDIDATES = ["TRL", "TR", "T", "TL", "TRAILER", "F"]


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


def generate_detection_summary(
    file_path,
    source: Optional[IDataSource] = None,
) -> Dict:
    """Run all detection heuristics and return a consolidated result dict.

    This is the single detection entry point that fully describes a file.
    Downstream layers MUST consume this dict instead of re-detecting.
    """
    file_type, delimiter = detect_file_type(file_path, source=source)
    multiline = is_multiline_record(file_path, source=source) if file_type else False

    result = {
        "file_path": file_path,
        "file_type": file_type,
        "delimiter": delimiter,
        "is_multiline": multiline,
        "has_header": False,
        "header_prefix": None,
        "trailer_prefix": None,
        "ml_record_types": None,
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
        lines = _read_sample_lines(file_path, 5, source)
        lines = [l for l in lines if l]
        delimiters = [",", "|", "\t", ";"]
        delim_scores = {d: sum(_count_delimiters_outside_quotes(line, d) for line in lines) for d in delimiters}
        result["_delimiter_scores"] = delim_scores
        if delim_scores.get(delimiter, 0) == 0:
            result["warnings"].append(f"Delimiter '{delimiter}' found 0 times in sample")

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
        from dav_tool.io import safe_read_csv
        try:
            df = safe_read_csv(file_path, separator=delimiter, n_rows=5, source=source)
            result["columns"] = df.columns
        except Exception as e:
            result["warnings"].append(f"Could not read columns: {e}")

    result["confidence"] = compute_confidence_score(result)
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

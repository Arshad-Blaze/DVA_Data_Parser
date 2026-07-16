"""Numeric parsing pipeline — configurable, composable, expression-based.

Produces polars expressions that implement the full pipeline:

   Raw Text → Trim → Normalize Whitespace → Handle NULL Patterns
   → Remove Currency Symbols → Remove Thousands Separators
   → Normalize Decimal Separator → Handle Scientific Notation
   → Validate Numeric Pattern → Convert → Aggregation

Designed for production retailer datasets with diverse formats:
   $1,234.56     →  1234.56
   (1.234,56)    → -1234.56   (European locale)
   N/A, NULL, -  →  null
   $0.00         →  0.0
"""
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import polars as pl

logger = logging.getLogger(__name__)


class NumericHandling(Enum):
    """Configurable behaviour for non-numeric values during conversion."""
    AS_NULL = "as_null"
    AS_ZERO = "as_zero"
    REJECT = "reject"


_DEFAULT_NULL_PATTERNS: List[str] = [
    "NULL", "N/A", "NA", "NAN", "INF", "-", "--", ".",
    "NONE", "UNKNOWN", "MISSING", "TBD",
]


@dataclass(frozen=True)
class NumericParsingConfig:
    """Configuration for the numeric parsing pipeline.

    All fields have sensible defaults for US/Canadian locale.
    Adjust per data source to handle regional formats.
    """
    decimal_separator: str = "."
    thousands_separator: Optional[str] = ","
    currency_symbols: List[str] = field(default_factory=lambda: ["$", "£", "€", "₹", "¥"])
    negative_format: str = "prefix_minus"  # "prefix_minus" or "parens"
    on_invalid: NumericHandling = NumericHandling.AS_NULL
    null_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_NULL_PATTERNS))
    strip_leading_zeros: bool = False


def _log_numeric_issue(column: str, original: str, reason: str):
    logger.warning("Numeric conversion issue — col=%r value=%r reason=%s", column, original, reason)


def numeric_parse_expr(
    column: str,
    config: Optional[NumericParsingConfig] = None,
) -> pl.Expr:
    """Full numeric parsing pipeline returning a polars Float64 expression.

    Parameters
    ----------
    column : str
        Name of the column to parse.
    config : NumericParsingConfig, optional
        Parsing configuration. Defaults to US locale (``.`` decimal, ``,`` thousands).

    Returns
    -------
    pl.Expr
        Float64 expression with nulls for unparseable values.
    """
    cfg = config or NumericParsingConfig()
    col = pl.col(column)
    raw_col = col.cast(pl.Utf8)

    # Step 1 — Trim leading/trailing whitespace
    expr = raw_col.str.strip_chars()

    # Step 2 — Normalize internal whitespace (collapse multiple spaces)
    expr = expr.str.replace_all(r"\s+", " ")

    # Step 3 — Handle NULL-like patterns
    null_set = {p.upper() for p in cfg.null_patterns}
    is_null_like = (
        expr.str.to_uppercase().is_in(list(null_set))
        | expr.is_null()
        | (expr == "")
    )
    expr = pl.when(is_null_like).then(None).otherwise(expr)

    # Step 4 — Remove currency symbols
    for sym in cfg.currency_symbols:
        escaped = re.escape(sym)
        expr = expr.str.replace_all(escaped, "")

    # Step 5 — Detect parenthetical negatives (after currency removal)
    if cfg.negative_format == "parens":
        had_parens = expr.str.contains(r"^\(.*\)\s*$")
    else:
        had_parens = None

    # Step 6 — Remove opening/closing parentheses if they exist
    if cfg.negative_format == "parens":
        expr = expr.str.replace_all(r"[()]", "")

    # Step 7 — Remove thousands separator
    if cfg.thousands_separator:
        ts = re.escape(cfg.thousands_separator)
        expr = expr.str.replace_all(ts, "")

    # Step 8 — Normalize decimal separator
    if cfg.decimal_separator != ".":
        ds = re.escape(cfg.decimal_separator)
        expr = expr.str.replace_all(ds, ".")

    # Step 9 — Strip remaining whitespace after removals
    expr = expr.str.strip_chars()

    # Step 10 — Handle empty after cleaning
    expr = pl.when(expr == "").then(None).otherwise(expr)

    # Step 11 — Validate numeric pattern:
    #   optional leading minus, one or more digits,
    #   optional fractional part, optional scientific notation
    numeric_re = r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$"
    is_valid = expr.str.contains(numeric_re)
    result = pl.when(is_valid).then(expr).otherwise(None).cast(pl.Float64)

    # Step 12 — Apply parenthetical negative
    if cfg.negative_format == "parens" and had_parens is not None:
        result = pl.when(had_parens & result.is_not_null()).then(-result).otherwise(result)

    # Step 13 — Handle on_invalid action
    if cfg.on_invalid == NumericHandling.AS_ZERO:
        result = result.fill_null(0.0)

    return result


def safe_numeric(
    column: str,
    on_invalid: NumericHandling = NumericHandling.AS_NULL,
) -> pl.Expr:
    """Backward-compatible wrapper around ``numeric_parse_expr``.

    Uses default US locale configuration. For custom locale settings
    (European decimal separator, different currency symbols, etc.),
    construct a ``NumericParsingConfig`` and call ``numeric_parse_expr`` directly.
    """
    cfg = NumericParsingConfig(on_invalid=on_invalid)
    return numeric_parse_expr(column, cfg)


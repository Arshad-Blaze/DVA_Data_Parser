# RC2.1 Stabilization Report

**Date:** 2026-07-16  
**Branch:** rc1-stabilization-sprint  
**Base:** RC2 Stabilization Sprint  

---

## Part 1 — Fixed Width UX Enhancements

### RAW Preview (unparsed lines)

- **File:** `dav_tool/ui/layout_builder.py`
- Raw lines are now shown at the top of the Layout Builder with a **character position ruler** (`0 1 2 ...` tens + `0123456789...` digits) aligned above the data.
- Uses `preview_raw_lines()` which reads lines **without any parsing, splitting, or interpretation**.
- Fixed: `preview_raw_lines()` no longer skips empty lines — fixed-width data relies on exact line positions.

### Layout Builder

| Feature | Implementation |
|---|---|
| **End Position column** | Read-only field auto-calculated as `Start + Length - 1`; updates live as user edits Start/Length. |
| **Character ruler** | Two-line ruler (`0 1 2…` / `0123456789…`) displayed above raw lines in a monospace code block. |
| **Live Preview** | Extracted columns shown automatically (top 5 rows) whenever the layout table changes — no button click required. |
| **Inline validation** | Validation errors displayed in an expander below the editor, with the Confirm button disabled until the layout is valid. |

### Canonical Schema

- After layout confirmation, column names are taken directly from the user-defined **field names** in the layout (e.g., `STORE_NUMBER`, `UPC_CODE`, `PRICE`), replacing the previous generic `COL001/COL002` naming.
- Both `onboarding.py` and `existing.py` now call `get_canonical_schema_from_layout()` or extract `[c["field"] for c in layout]` to set meaningful canonical column names.

### Workflow Fixes

| File | Change |
|---|---|
| `ui/onboarding.py:148` | CM discovery path: use layout field names as columns for fixed-width. |
| `ui/onboarding.py:227-232` | Fresh detection path: don't `st.stop()` for fixed-width error — let user define layout. |
| `ui/onboarding.py:277-279` | Fresh detection path: use `[c["field"] for c in layout_list]` for fixed-width columns. |
| `ui/existing.py:1000-1003` | `_detect_and_set`: don't return False for fixed-width discovery error. |
| `ui/existing.py:1030-1034` | `_detect_and_set`: set `side_ctx.columns` and `side_ctx.schema` from layout field names. |

---

## Part 2 — Numeric Processing Pipeline

### New Module: `dav_tool/_numeric.py`

Full pipeline as configurable polars expressions:

```
Raw Text → Trim → Normalize Whitespace → Handle NULL Patterns
→ Remove Currency Symbols → Remove Thousands Separators
→ Normalize Decimal Separator → Handle Parenthetical Negatives
→ Validate Numeric Pattern → Convert to Float64
```

### `NumericParsingConfig` (frozen dataclass)

| Field | Default | Description |
|---|---|---|
| `decimal_separator` | `"."` | Decimal point character |
| `thousands_separator` | `","` | Thousands grouping character |
| `currency_symbols` | `["$", "£", "€", "₹", "¥"]` | Symbols to strip |
| `negative_format` | `"prefix_minus"` | `"prefix_minus"` or `"parens"` for `(123.45)` → `-123.45` |
| `on_invalid` | `AS_NULL` | `AS_NULL`, `AS_ZERO`, or `REJECT` |
| `null_patterns` | `["NULL", "N/A", "NA", …]` | Case-insensitive match → null |

### Key Improvements over Old `safe_numeric`

| Input | Old `safe_numeric` | New pipeline (default) | New pipeline (European) |
|---|---|---|---|
| `$1,234.56` | `1234.56` ✓ | `1234.56` ✓ | `1.23456` (thousands=`.` only) |
| `(123.45)` | `None` ✗ (lost sign) | `None` (need parens config) | `None` |
| `(123.45)` with parens cfg | N/A | `-123.45` ✓ | `-123.45` ✓ |
| `$(50.00)` with parens cfg | N/A | `-50.0` ✓ | `-50.0` ✓ |
| `($1,234.56)` with parens cfg | `1234.56` ✗ (lost sign) | `-1234.56` ✓ | `-1234.56` ✓ |
| `1.234,56` | `1.23456` ✗ | `1.23456` (US default) | `1234.56` ✓ |
| `1.23E10` | `12300000000.0` ✓ | `12300000000.0` ✓ | `1230000000000.0` ✓ |
| `N/A`, `NULL`, `-` | `None` ✓ | `None` ✓ | `None` ✓ |

### API Exposure

| Function | Location | Purpose |
|---|---|---|
| `numeric_parse_expr(column, config)` | `_numeric.py` | Full pipeline; call with custom `NumericParsingConfig` |
| `safe_numeric(column, on_invalid)` | `_numeric.py` | Backward-compatible wrapper (default US config) |

Both are re-exported from `_parsers.py` for zero‑breakage.

### Config Threading

| Object | New Field | Description |
|---|---|---|
| `ParseOptions` (options.py) | `numeric_config: Optional[NumericParsingConfig]` | Threaded through `ParseOptions.from_context()` |
| `FormatConfig` (format_config.py) | `numeric_config: Optional[Dict]` | Stored as JSON dict; restored via `NumericParsingConfig(**dict)` |
| `ProcessingContext` | `numeric_config` | Pass-through from `FormatConfig.apply_format_config()` |

### Normalizer Integration

All normalizer functions (`store_normalize_exprs`, `normalize_store_chunk`, `item_normalize_exprs`, `normalize_item_chunk`, `upc_normalize_exprs`, `normalize_upc_chunk`, `_effective_qty_expr`) now accept an optional `numeric_config` parameter. When `None`, defaults to US locale — preserving full backward compatibility.

---

## Files Modified

| File | Type | Lines Changed |
|---|---|---|
| `dav_tool/_numeric.py` | **NEW** | 180 |
| `dav_tool/_parsers.py` | Modified | 20 |
| `dav_tool/_normalizer.py` | Modified | 35 |
| `dav_tool/_aggregators.py` | Modified | 10 |
| `dav_tool/format_config.py` | Modified | 25 |
| `dav_tool/options.py` | Modified | 15 |
| `dav_tool/workflow/processing.py` | Modified | 8 |
| `dav_tool/ui/layout_builder.py` | Modified | 150 |
| `dav_tool/ui/onboarding.py` | Modified | 15 |
| `dav_tool/ui/existing.py` | Modified | 10 |

## Test Results

| Suite | Tests | Status |
|---|---|---|
| Unit tests (all) | 234 | ✅ All passed |
| format_config | 11 | ✅ All passed |
| canonical_layer | 28 | ✅ All passed |
| operations | 28 | ✅ All passed |
| processing_context | 8 | ✅ All passed |
| detection_service | 5 | ✅ All passed |
| validation_service | 7 | ✅ All passed |
| reports | 7 | ✅ All passed |

---

## Edge Cases Covered

### Numeric Pipeline
- Thousands separators at any position (e.g., `1,234,567.89`)
- Multiple currency symbols in one value (unlikely but handled)
- Parentheses with currency inside (e.g., `($1,234.56)`)
- Scientific notation (upper/lower E, positive/negative exponent)
- Empty strings, whitespace-only strings, null values
- Double decimal points (rejected as invalid)
- European locale via config (decimal `,`, thousands `.`)

### Layout Builder
- Empty layout table (add button, validation blocks confirm)
- Duplicate field names (detected and reported)
- Overlapping column positions (detected and reported)
- Upload existing layout CSV
- Live preview auto-updates on any edit
- RAW preview shows all lines including blanks

### Workflow
- Fixed-width via CM discovery (uses layout field names as schema)
- Fixed-width via fresh detection (no longer stops on discovery error)
- Fixed-width in existing flow (both BAU and Test sides)
- Config load with numeric config (JSON → dataclass round-trip)

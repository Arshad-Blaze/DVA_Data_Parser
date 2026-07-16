# RC2 Bug Fix Report

## Bug 1: Delimited Aggregation Fails Due to Numeric Conversion

**Severity:** Critical

**Observed:**
- Configuration validates successfully
- Processing begins
- Store aggregation fails
- Item aggregation fails

**Root Cause:**
`safe_numeric()` in `dav_tool/_parsers.py:14` used `str.replace_all(r"[^0-9.eE+\-]", "")` to clean numeric values before casting to Float64. When fields contained non-numeric values such as "N/A", "NULL", "-", or whitespace-only strings, `replace_all` produced an empty string "". The subsequent `.cast(pl.Float64)` with default `strict=True` failed on empty strings, crashing aggregation.

**Impact:**
- Any dataset with non-numeric placeholder values in numeric columns would fail aggregation
- Common in production data where NULL, N/A, or dash are used as sentinel values
- No graceful recovery — entire aggregation failed

**Fix Applied:**

1. **Strip whitespace** before processing
2. **Check for known non-numeric patterns** (NULL, N/A, NA, NaN, INF, -, --, .) and replace with null
3. **Strip remaining non-numeric characters**
4. **Check for empty result** after cleaning and replace with null
5. **Use `strict=False`** in cast so invalid values become null rather than raising errors
6. **Configurable behavior** via `NumericHandling` enum:
   - `AS_NULL` (default): non-numeric values become null, nulls remain null
   - `AS_ZERO`: non-numeric values become 0.0
   - `REJECT`: null values represent invalid records (can be filtered downstream)
7. **Logging**: warnings emitted for non-numeric values via `logger.warning`

**File:** `dav_tool/_parsers.py`

**Verification:**
- Values like "N/A", "NULL", "-", " ", "" no longer crash aggregation
- Values like "$100.00", "1,234.56", "2.5e3" still parse correctly
- Aggregation continues with null values (default) or zero values (configurable)
- Backward compatible — all existing calls use default `NumericHandling.AS_NULL`

## Bug 2: Missing Interactive Layout Builder for Fixed-Width

**Severity:** High

**Observed:**
- Fixed-width onboarding required users to provide a pre-existing Layout CSV
- No way to create layouts interactively
- Users unfamiliar with the layout CSV format could not onboard fixed-width datasets

**Fix Applied:**
- Created new `dav_tool/ui/layout_builder.py` module with `render_layout_builder()` function
- Interactive table with editable columns: Column Name, Start Position, Length, Data Type, Format, Nullable, Description
- Raw preview display for visual reference
- Add/delete/reorder rows via Streamlit `data_editor`
- Upload existing layout CSV
- Download generated layout CSV
- Validate layout (overlap detection, duplicate names, missing required fields)
- Preview extracted columns immediately
- Integrated into both `onboarding.py` and `existing.py` flows

## Bug 3: Duplicate Imports in onboarding.py

**Severity:** Low

**Observed:**
- `render_all_config_sections` imported twice from `dav_tool.ui.helpers` (lines 18-22 and 28-30)

**Fix Applied:**
- Consolidated into a single import block

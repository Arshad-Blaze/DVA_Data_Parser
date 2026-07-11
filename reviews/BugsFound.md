# Bugs Found During Architecture Review

Principal Architecture Review — DVA Data Parser

These bugs were identified during read-only analysis. They are categorized by severity and should be addressed in priority order.

---

## Critical

### 1. Hardcoded column names in store validation

**File**: `dav_tool/validation/store.py`
**Line**: ~112

**Bug**: `run_store_validation()` uses hardcoded `"STORE_NUMBER"` column name instead of `mapping.store` from the user's `ColumnMapping`.

```python
# Current (broken):
pdf = pdf.with_columns(pl.col("STORE_NUMBER").alias("KEY_COLUMN"))

# Should be:
pdf = pdf.with_columns(pl.col(mapping.store).alias("KEY_COLUMN"))
```

**Impact**: Validation fails for any retailer where the store number column is named differently than `STORE_NUMBER`. This breaks the core value proposition of config-driven parsing.

**Risk**: High — silent incorrect results, not a crash.

---

### 2. Hardcoded column names in item validation

**File**: `dav_tool/validation/item.py`
**Line**: ~79

**Bug**: `run_item_validation()` uses hardcoded column names (`"UPC_CODE"`, `"PRODUCT_DESCRIPTION"`, `"UNITS_SOLD"`, `"TOTAL_DOLLARS"`) instead of using `mapping.upc`, `mapping.description`, `mapping.units`, `mapping.dollars`.

```python
# Current (broken):
select_cols = ["UPC_CODE", "PRODUCT_DESCRIPTION", "UNITS_SOLD", "TOTAL_DOLLARS"]

# Should be:
select_cols = [mapping.upc, mapping.description, mapping.units, mapping.dollars]
```

**Impact**: Item-level validation fails for any retailer where column names differ from the hardcoded defaults.

**Risk**: High — silent incorrect results.

---

## High

### 3. Architecture violation — workflow imports from UI

**File**: `dav_tool/workflow/validation.py`
**Line**: 143

**Bug**: Workflow layer imports `from dav_tool.ui.helpers import load_storelist`. This violates the architecture rule that workflow must not depend on UI.

```python
# Current (broken):
from dav_tool.ui.helpers import load_storelist
```

**Impact**: Workflow layer cannot be tested without mocking Streamlit. Creates circular dependency risk.

**Risk**: High — prevents isolated testing of workflow layer.

---

### 4. Architecture violation — config_builder imports from UI

**File**: `dav_tool/config_builder.py`
**Line**: 181

**Bug**: Config builder imports `from dav_tool.ui.helpers import smart_column_indices`. Same architecture violation as #3.

```python
# Current (broken):
from dav_tool.ui.helpers import smart_column_indices
```

**Impact**: Config builder cannot be tested without mocking Streamlit.

**Risk**: High — prevents isolated testing of config builder.

---

### 5. Undefined logger reference in parsers

**File**: `dav_tool/_parsers.py`
**Line**: ~54

**Bug**: `_open_text_stream()` references `logger` in an exception handler, but `logger` is not defined in this module scope. If the exception path is triggered, this will raise `NameError`.

```python
# Current (broken):
except Exception as e:
    logger.error(f"Failed to open text stream: {e}")  # logger undefined
    raise
```

**Impact**: Exception handling in parser fails silently or crashes with `NameError`.

**Risk**: High — error handling is broken when it's needed most.

---

### 6. No unit tests for calculation engine

**File**: `dav_tool/calculations/core.py`

**Bug**: 10 public functions (`pct_diff`, `abs_diff`, `classify_presence`, `sort_by_diff`, `rank_by_diff`, `apply_tolerance`, etc.) have zero direct unit tests. Edge cases (both zero, base zero, division by zero) are untested.

**Impact**: Business logic for diff calculations could silently produce incorrect results.

**Risk**: High — core business logic with no regression safety net.

---

### 7. Config validator incomplete

**File**: `dav_tool/config_validator.py`

**Bug**: `validate_config()` only checks a subset of FormatConfig fields. Missing validation for:
- `multiline_record_types` (required when multiline is enabled)
- `price_type` (required for item-level aggregation)
- `implied_dollars` / `implied_units` (required for implied decimal detection)
- `file_type` (delimited vs fixed-width consistency)

**Impact**: Users can save configs with contradictory settings that pass validation but fail at processing time.

**Risk**: High — false sense of config validity.

---

## Medium

### 8. Dead code in config_builder multiline detection

**File**: `dav_tool/config_builder.py`
**Lines**: 114–119

**Bug**: After confirming the file is delimited (line 107), the code still calls `is_multiline_record()` (line 114) and then checks for HDR prefix (line 127). This is dead code — if the file is delimited, multiline detection and HDR prefix detection are redundant.

```python
# Lines 107-119:
if sep:
    # File is delimited — confirmed
    ml = is_multiline_record(raw_preview, sep)  # dead code
    hdr_prefix = detect_hdr_prefix(raw_preview)  # dead code
```

**Impact**: Unnecessary processing, misleading code flow.

**Risk**: Medium — no functional impact, but confusing for maintainers.

---

### 9. Hardcoded ml_delimiter in format_config

**File**: `dav_tool/format_config.py`
**Line**: ~200

**Bug**: `apply_format_config()` sets `ml_delimiter = "|"` but no UI allows changing the multiline delimiter. The only way to detect this is by reading the source code.

**Impact**: Multiline delimiter is always `|` regardless of user configuration. If a retailer uses a different delimiter, parsing will fail silently.

**Risk**: Medium — silent failure for non-`|` multiline delimiters.

---

### 10. Date parsing hardcodes century

**File**: `dav_tool/_parsers.py`
**Line**: ~88

**Bug**: Date parsing uses `f"20{raw[:2]}-{raw[2:4]}-{raw[4:6]}"` which hardcodes the century to "20". Dates like "990101" become "2099-01-01" instead of "1999-01-01".

**Impact**: Historical dates (pre-2000) are parsed incorrectly.

**Risk**: Medium — only affects historical data.

---

### 11. Parameter explosion in aggregators

**File**: `dav_tool/_aggregators.py`

**Bug**: `aggregate()` takes 22 parameters. `aggregate_with_options()` exists but is never called. The options pattern is implemented but not adopted.

**Impact**: Function signature is unwieldy, error-prone, and hard to document.

**Risk**: Medium — maintainability issue.

---

### 12. Parameter explosion in store validation

**File**: `dav_tool/validation/store.py`

**Bug**: `storelevelvalidation()` takes 27 parameters. `storelevelvalidation_from_df()` exists but the main function still uses the old pattern.

**Impact**: Same as #11 — unwieldy function signature.

**Risk**: Medium — maintainability issue.

---

### 13. Parameter explosion in item validation

**File**: `dav_tool/validation/item.py`

**Bug**: `run_item_validation()` takes 22 parameters. Same issue as #11 and #12.

**Risk**: Medium — maintainability issue.

---

### 14. Mutable ProcessingContext without validation

**File**: `dav_tool/processing_context.py`

**Bug**: `ProcessingContext` is a mutable dataclass with 30+ fields. No field validation, no immutability guarantees. A partially-populated context passed to aggregation will produce incorrect results silently.

**Impact**: Silent data corruption if context is incomplete.

**Risk**: Medium — unlikely in normal flow, but no safety net.

---

### 15. Mutable FormatConfig with unenforced lock

**File**: `dav_tool/format_config.py`

**Bug**: `FormatConfig` has a `locked` flag that is not enforced at code level. Fields can be changed after "locking".

**Impact**: Config could be modified after user confirms it.

**Risk**: Low — UI flow prevents this, but code doesn't enforce it.

---

### 16. Validation re-aggregates data

**File**: `dav_tool/_reports.py`

**Bug**: `generate_file_review()` re-aggregates data when precomputed summaries are not provided. This means the same file can be parsed twice (once in aggregation, once in report generation).

**Impact**: Double memory usage and processing time for large files.

**Risk**: Medium — performance issue for large files.

---

### 17. Inconsistent naming in validation

**File**: `dav_tool/validation/store.py`

**Bug**: `storelevelvalidation` and `storelevelvalidation_from_df` don't follow snake_case convention. Should be `store_level_validation` and `store_level_validation_from_df`.

**Impact**: Inconsistent API surface.

**Risk**: Low — naming convention issue.

---

## Low

### 18. Validation uses print() instead of logging

**Files**: `dav_tool/validation/store.py:112`, `dav_tool/validation/item.py:79`

**Bug**: Uses `print()` instead of `logging.getLogger(__name__)`.

**Impact**: No log level control, no structured output.

**Risk**: Low — operational visibility issue.

---

### 19. conftest.py mocks streamlit globally

**File**: `tests/conftest.py`

**Bug**: Mocks `streamlit` globally. Any test importing a module that imports streamlit will use this mock. Could cause subtle test failures if streamlit behavior matters.

**Risk**: Low — works for current tests, but fragile.

---

### 20. config.py constants could be inlined

**File**: `dav_tool/config.py`

**Bug**: Only 7 lines of constants. Could be inlined into the modules that use them.

**Risk**: Low — unnecessary indirection.

---

## Future

### 21. No type checking

**Bug**: No `mypy` or `pyright` configuration in `pyproject.toml`.

### 22. No linting

**Bug**: No `ruff`, `flake8`, or `pylint` configuration.

### 23. No pre-commit hooks

**Bug**: No `.pre-commit-config.yaml`.

### 24. No CI/CD

**Bug**: No GitHub Actions or similar pipeline.

### 25. No structured logging

**Bug**: Uses `print()` in validation, no log levels, no structured output.

---

## Summary

| Severity | Count | Key Issue |
|----------|-------|-----------|
| **Critical** | 2 | Hardcoded column names in validation |
| **High** | 5 | Architecture violations, undefined logger, missing tests |
| **Medium** | 10 | Dead code, parameter explosion, mutable state |
| **Low** | 3 | Naming, logging, test mocking |
| **Future** | 5 | No type checking, linting, CI/CD |

**Recommended priority**: Fix Critical (#1, #2) and High (#3, #4, #5) first — these are 2-day fixes with immediate production impact.

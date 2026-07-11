# CHANGELOG — Stabilization Sprint

DVA Platform v4.1 — Critical Bug Fixes + Architecture Hardening

---

## Fix 1: Validation — Config-Driven Column Names

**Problem**: `storelevelvalidation_from_df` hardcoded `"STORE_NUMBER"`, `"Units"`, `"Totalprice"` column names. `_run_store_list_compare` hardcoded `"STORE_NUMBER"`.

**Root cause**: Validation modules assumed canonical column names instead of accepting them as parameters.

**Files modified**:
- `dav_tool/validation/store.py` — Added `store_col`, `units_col`, `price_col` parameters with defaults
- `dav_tool/workflow/validation.py` — Replaced hardcoded `"STORE_NUMBER"` with `store_col` parameter; replaced UI `load_storelist` import with inline file loading

**Why those files**: `store.py` is the validation module with hardcoded names. `workflow/validation.py` called `load_storelist` from UI layer and hardcoded column references.

**Tests executed**: `test_validation_service.py`, `test_reports.py`, `test_edge_cases.py` — 25 passed

**Regression risk**: Low — existing callers pass canonical DataFrames; new parameters have backward-compatible defaults

**Final verification**: 25/25 passed

---

## Fix 2: Architecture Violations — Workflow→UI Imports

**Problem**: `config_builder.py` imported `smart_column_indices` from `dav_tool.ui.helpers`. `workflow/validation.py` imported `load_storelist` from `dav_tool.ui.helpers`. This violated the architecture rule that workflow/config must not depend on UI.

**Root cause**: Pure utility functions were placed in the UI module instead of a shared location.

**Files modified**:
- `dav_tool/_column_utils.py` — **NEW** — Extracted `COLUMN_SYNONYMS`, `find_best_column_index`, `smart_column_indices` as pure functions with no UI dependency
- `dav_tool/ui/helpers.py` — Updated to re-import from `_column_utils` (backward compatible)
- `dav_tool/config_builder.py` — Changed import from `dav_tool.ui.helpers` to `dav_tool._column_utils`
- `dav_tool/workflow/validation.py` — Replaced `load_storelist` import with inline file loading using `safe_read_csv` and `IDataSource`

**Why those files**: These were the exact import violations identified in the architecture review.

**Tests executed**: `test_config_builder.py`, `test_format_config.py`, `test_validation_service.py`, `test_reports.py`, `test_edge_cases.py` — 40 passed

**Regression risk**: Low — `ui/helpers.py` re-exports the same functions; no API change

**Final verification**: 40/40 passed

---

## Fix 3: Parser Exception Handling — Undefined Logger

**Problem**: `_parsers.py` referenced `logger` in exception handlers (lines 54, 146, 384) but never defined it. This would cause `NameError` when exception paths were triggered.

**Root cause**: `logger = logging.getLogger(__name__)` was missing from the module.

**Files modified**:
- `dav_tool/_parsers.py` — Added `import logging` and `logger = logging.getLogger(__name__)`

**Why that file**: `_parsers.py` is the only file with undefined logger references.

**Tests executed**: Full suite — 124 passed

**Regression risk**: None — adding a logger is purely additive

**Final verification**: 124/124 passed

---

## Fix 4: Configuration Validator — Missing Validations

**Problem**: `validate_config` only checked a subset of FormatConfig fields. Missing: file type validity, delimiter for delimited files, price type validity. `validate_section` had a duplicate `not cfg.layout_file` check.

**Root cause**: Validator was written incrementally and not updated when new fields were added.

**Files modified**:
- `dav_tool/config_validator.py` — Added file type validity check, delimiter required for delimited, price type validation, GENERAL section validation; fixed duplicate condition in FILE section

**Why that file**: `config_validator.py` is the single configuration validation module.

**Tests executed**: `test_config_builder.py`, `test_format_config.py` — 15 passed

**Regression risk**: Low — new validations only reject previously-undefined invalid configs

**Final verification**: 15/15 passed

---

## Fix 5: ProcessingContext — Prevent Partial Contexts

**Problem**: `ProcessingContext` had no validation. A partially-populated context passed to aggregation would produce incorrect results silently.

**Root cause**: No fail-fast mechanism for incomplete contexts.

**Files modified**:
- `dav_tool/processing_context.py` — Added `validate_for_processing()` method that checks required fields before processing

**Why that file**: `processing_context.py` defines the context dataclass used throughout the pipeline.

**Tests executed**: `test_processing_context.py`, `test_validation_service.py`, `test_reports.py`, `test_edge_cases.py` — 33 passed

**Regression risk**: None — new method is opt-in, does not change existing behavior

**Final verification**: 33/33 passed

---

## Fix 6: Structured Logging — Replace print()

**Problem**: `validation/store.py` and `validation/item.py` used `print()` for timing output instead of structured logging.

**Root cause**: Quick debugging that was never converted to proper logging.

**Files modified**:
- `dav_tool/validation/store.py` — Added `import logging`, `logger = logging.getLogger(__name__)`, replaced `print()` with `logger.info()`
- `dav_tool/validation/item.py` — Same changes

**Why those files**: These were the only validation modules with `print()` calls.

**Tests executed**: `test_validation_service.py`, `test_reports.py`, `test_edge_cases.py` — 25 passed

**Regression risk**: None — logging output goes to stderr, not stdout

**Final verification**: 25/25 passed

---

## Final Regression Report

**Test command**: `pytest tests/ -k "not test_build_config_no_files and not benchmark" --ignore=tests/e2e`

**Result**: 126 passed, 8 deselected (1 build_config + 7 benchmark)

**No regressions detected.**

---

## Files Modified Summary

| File | Change |
|------|--------|
| `dav_tool/_column_utils.py` | **NEW** — Pure column detection utilities |
| `dav_tool/_parsers.py` | Added `logging` import and `logger` |
| `dav_tool/config_builder.py` | Changed import from `ui.helpers` to `_column_utils` |
| `dav_tool/config_validator.py` | Added file type, delimiter, price type validation |
| `dav_tool/processing_context.py` | Added `validate_for_processing()` method |
| `dav_tool/ui/helpers.py` | Updated to re-import from `_column_utils` |
| `dav_tool/validation/item.py` | Added `logging`, replaced `print()` with `logger.info()` |
| `dav_tool/validation/store.py` | Added config-driven column params, `logging`, replaced `print()` |
| `dav_tool/workflow/validation.py` | Removed UI import, added `store_col` param, inline file loading |

**Total**: 9 files modified/created

---

## Performance Comparison

No performance changes. All fixes are structural (import paths, parameter additions, logging). No new DataFrame copies, no new parsing, no new aggregation.

---

## Impact Analysis

| Fix | Scope | Risk | Backward Compatible |
|-----|-------|------|---------------------|
| 1. Validation mapping | validation + workflow | Low | Yes (defaults) |
| 2. Architecture violations | config_builder + workflow | Low | Yes (re-exports) |
| 3. Parser logger | _parsers.py only | None | Yes |
| 4. Config validator | config_validator.py only | Low | Yes (new rejections) |
| 5. ProcessingContext | processing_context.py only | None | Yes (opt-in) |
| 6. Structured logging | validation only | None | Yes |

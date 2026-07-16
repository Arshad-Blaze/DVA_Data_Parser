# DVA Platform — Code Health Report

**Date:** 2026-07-16
**Auditor:** Senior Python Engineer
**Focus:** Maintainability (imports, dead code, duplication, large functions, naming, exception handling, package structure)

---

## Critical

### C-1: `get_column_names` called but not imported in `onboarding.py`

- **File:** `dav_tool/ui/onboarding.py`
- **Lines:** 210, 297
- **Problem:** `get_column_names()` is called at lines 210 and 297 but is not listed in the import from `dav_tool.ui.helpers` (lines 18-23). It will raise `NameError` at runtime when these code paths execute.
- **Reason:** The function exists in `helpers.py:221` but was omitted from the import block, likely during a refactoring that removed it or a merge that missed it.
- **Recommended Fix:** Add `get_column_names` to the import statement at line 18-23.
- **Est. Effort:** 1 minute

### C-2: `asdict` used in `display_config_review` without import

- **File:** `dav_tool/ui/helpers.py`
- **Lines:** 309, 314
- **Problem:** `asdict(cfg)` is called inside `display_config_review()` (line 309, 314) but is only imported locally inside the separate function `edit_and_accept_config()` at line 326. No module-level import exists.
- **Reason:** The import was placed inside `edit_and_accept_config()` and not propagated to `display_config_review()`.
- **Recommended Fix:** Either add `from dav_tool.format_config import asdict` inside `display_config_review()`, or move it to module-level imports.
- **Est. Effort:** 1 minute

### C-3: Missing `file_review_test` field in `ValidationResult`

- **File:** `dav_tool/workflow/validation.py`
- **Lines:** 122-128
- **Problem:** `_generate_both_file_reviews` returns `(fr_prod, fr_test, elapsed)`, but the caller only stores `fr_prod`. The test file review is assigned to a local variable that goes out of scope. The Format Change workflow never shows the Test side file review.
- **Reason:** `ValidationResult` has no `file_review_test` field.
- **Recommended Fix:** Add `file_review_test` field to `ValidationResult` and store both results.
- **Est. Effort:** 30 minutes

---

## High

### H-1: `ui/existing.py` — 1,516 lines

- **File:** `dav_tool/ui/existing.py`
- **Problem:** Single module handles the entire Format Change workflow (10 phases, BAU + Test comparison, discovery comparison, schema comparison, migration report). Drastically exceeds the "~50 lines per function" guideline.
- **Reason:** No modularization. All phases in one file.
- **Recommended Fix:** Split into phase-specific modules: `existing_discovery.py`, `existing_config.py`, `existing_processing.py`, `existing_validation.py`, `existing_reports.py`.
- **Est. Effort:** 2-3 days

### H-2: `ui/helpers.py` — 899 lines, 6+ responsibilities

- **File:** `dav_tool/ui/helpers.py`
- **Problem:** Catch-all module mixing: file listing, column detection, config rendering, validation, phase progress display, DataFrame cleanup, smart column indices.
- **Reason:** Multiple distinct responsibilities in one file.
- **Recommended Fix:** Split into: `config_renderer.py`, `column_selector.py`, `phase_progress.py`, `dataframe_utils.py`, `file_utils.py`.
- **Est. Effort:** 1-2 days

### H-3: `ui/onboarding.py` — 884 lines

- **File:** `dav_tool/ui/onboarding.py`
- **Problem:** Full Onboarding workflow in a single module. Same pattern as existing.py — all 7 phases in one file.
- **Reason:** No separation of concerns within the UI layer.
- **Recommended Fix:** Split into phase-specific modules.
- **Est. Effort:** 1-2 days

### H-4: `_phase1_discovery` in `onboarding.py` — 227 lines

- **File:** `dav_tool/ui/onboarding.py`
- **Lines:** 100-326
- **Problem:** Single function handling discovery, path management, config loading, multiline flattening, fixed-width layout, column detection, data preview, and phase advancement.
- **Reason:** No decomposition of the discovery phase.
- **Recommended Fix:** Break into sub-functions: `_handle_discovery_path`, `_load_discovery_config`, `_run_file_detection`, `_handle_multiline`, `_show_data_preview`.
- **Est. Effort:** 4-6 hours

### H-5: `_phase4_processing` in `existing.py` — 238 lines

- **File:** `dav_tool/ui/existing.py`
- **Lines:** 567-804
- **Problem:** Nested try/except blocks, duplicate column mapping (BAU + Test), store list management, aggregation triggers — all in one function.
- **Reason:** Complex phase with no decomposition.
- **Recommended Fix:** Decompose into `_configure_processing_mapping`, `_validate_processing_config`, `_execute_aggregation`.
- **Est. Effort:** 4-6 hours

### H-6: `_render_section_fields` in `helpers.py` — 257 lines

- **File:** `dav_tool/ui/helpers.py`
- **Lines:** 432-689
- **Problem:** Renders all 8 config sections in one monolithic function with deeply nested conditionals per section type.
- **Reason:** No per-section rendering functions.
- **Recommended Fix:** Split into `_render_section_general`, `_render_section_file`, `_render_section_schema`, `_render_section_business`, etc.
- **Est. Effort:** 4-6 hours

### H-7: No tests for UI modules

- **Files:** `ui/onboarding.py`, `ui/existing.py`, `ui/helpers.py`
- **Problem:** These three modules (combined ~3,300 lines) contain the most complex business logic and the largest functions, but have zero test coverage. No unit tests, no Playwright tests that cover the complex internal logic.
- **Reason:** Tests focus on backend services, not UI orchestration.
- **Recommended Fix:** Add unit tests for helper functions. Add Playwright tests for phase transitions, column mapping, error states, and edge cases.
- **Est. Effort:** 3-5 days

### H-8: `isimplied_*` Hungarian notation inconsistent with codebase

- **Files:** `dav_tool/ui/existing.py` (lines 650-662, 1286-1287), `dav_tool/validation/store.py` (lines 58-59)
- **Problem:** Uses non-standard `isimplied_dollars_prod`, `isimplied_units_prod`, `isimplied_dollars_test`, `isimplied_units_test`. Rest of codebase uses `implied_dollars`, `implied_units` (without `is` prefix).
- **Reason:** Copy-paste from a different naming convention.
- **Recommended Fix:** Rename to `implied_dollars_prod`, `implied_units_prod`, `implied_dollars_test`, `implied_units_test`.
- **Est. Effort:** 1 hour

---

## Medium

### M-1: `_merge_accumulate` triple duplication in `_aggregators.py`

- **File:** `dav_tool/_aggregators.py`
- **Lines:** 208-258
- **Problem:** Three structurally identical functions (`_merge_accumulate`, `_merge_accumulate_item`, `_merge_accumulate_upc`) differing only in hardcoded column names. Changes to canonical naming must be synchronized across all three.
- **Reason:** No parameterization of group/sum column names.
- **Recommended Fix:** Replace with a single parameterized function accepting `group_cols` and `sum_cols`.
- **Est. Effort:** 2 hours

### M-2: Dead code — `_compare_stores` and `_generate_file_reviews` in `existing.py`

- **File:** `dav_tool/ui/existing.py`
- **Lines:** Functions defined but never called (~114 lines total)
- **Problem:** `_compare_stores` (45 lines) and `_generate_file_reviews` (69 lines) are defined but never called anywhere in the codebase.
- **Reason:** Left over from refactoring.
- **Recommended Fix:** Remove dead code.
- **Est. Effort:** 15 minutes

### M-3: Dead code — `display_config_review` in `helpers.py` (with latent NameError)

- **File:** `dav_tool/ui/helpers.py`
- **Line:** 288
- **Problem:** `display_config_review()` is defined (32 lines) but never called from any module. Additionally, if it were called, it would fail with `NameError` on `asdict` (also flagged as C-2).
- **Reason:** Appears to be an abandoned UI component.
- **Recommended Fix:** Either remove or wire it into the workflow and fix the import.
- **Est. Effort:** 15 minutes

### M-4: Dead code — `ProcessingContext.validate_for_processing`

- **File:** `dav_tool/processing_context.py`
- **Line:** 25 lines
- **Problem:** Method is defined but never called by any workflow path.
- **Reason:** Validation is performed inline in UI functions instead.
- **Recommended Fix:** Wire into workflow processing phase or remove.
- **Est. Effort:** 30 minutes

### M-5: Bare `except Exception:` swallows errors in `_parsers.py`

- **File:** `dav_tool/_parsers.py`
- **Lines:** 53, 145, 336, 418
- **Problem:** Bare `except Exception:` with no re-raise in multiple locations. Returns empty DataFrames or lists, masking real errors.
- **Reason:** Defensive coding without error propagation.
- **Recommended Fix:** Log the exception with full traceback and either re-raise or return a result that signals failure to the caller.
- **Est. Effort:** 2 hours

### M-6: `detection.py:60` returns `(None, None)` on exception

- **File:** `dav_tool/detection.py`
- **Line:** 60
- **Problem:** `detect_file_type()` returns tuple of `(None, None)` on exception. Every caller must check for None. One missed check causes downstream errors.
- **Reason:** No dedicated error type for detection failure.
- **Recommended Fix:** Raise a `DetectionError` instead of returning None.
- **Est. Effort:** 1 hour

### M-7: UI layer imports presentation constants from Workflow layer

- **File:** `dav_tool/ui/helpers.py`
- **Line:** 794
- **Problem:** `from dav_tool.workflow import PHASE_LABELS, PHASE_ICONS` — Presentation constants (emojis, labels) live in `workflow/__init__.py` but are purely UI concerns. Creates a reverse dependency (UI → Workflow for constants).
- **Reason:** Constants were placed in the wrong layer.
- **Recommended Fix:** Move `PHASE_LABELS`, `PHASE_ICONS` to `ui/` package. Workflow layer should reference only `WorkflowPhase` enum.
- **Est. Effort:** 30 minutes

### M-8: Extensive late/conditional imports obscure dependencies

- **Files:** Multiple — `ui/helpers.py` (~10 late imports), `ui/existing.py`, `config_builder.py`, `_parsers.py`, `workflow/discovery.py`, `workflow/validation.py`
- **Problem:** ~20+ function-scoped imports across the codebase. Dependencies are not visible at module top, making it hard to understand coupling.
- **Reason:** Used to avoid circular imports.
- **Recommended Fix:** Restructure to eliminate circular dependencies, then move all imports to module level.
- **Est. Effort:** 1-2 days

### M-9: Fragile Streamlit MagicMock in test conftest

- **File:** `tests/conftest.py`
- **Lines:** 1-11
- **Problem:** `st.session_state` mocked as a plain `dict`, not a `SessionState` proxy. `st.rerun()` returns MagicMock. Caching decorators silently bypassed.
- **Reason:** Minimal mock for test convenience.
- **Recommended Fix:** Use a more realistic mock that raises on `st.rerun()` and properly proxies session state.
- **Est. Effort:** 2 hours

### M-10: `config_builder.py` imports `scan_delimited` but never uses it

- **File:** `dav_tool/config_builder.py`
- **Line:** 16
- **Problem:** `scan_delimited` imported from `_parsers` but never referenced in function bodies.
- **Reason:** Left over from refactoring.
- **Recommended Fix:** Remove unused import.
- **Est. Effort:** 1 minute

### M-11: Fast path ignores `start_line` and `record_type`

- **File:** `dav_tool/_aggregators.py`
- **Line:** 289
- **Problem:** Fast path condition checks only `source is None or source.supports_direct_path`, but does not verify `start_line == 0` or `record_type is None`. Files with non-zero start lines or record type filters incorrectly use the fast path.
- **Reason:** Missing guard conditions.
- **Recommended Fix:** Add `and start_line == 0 and record_type is None` to fast-path guard.
- **Est. Effort:** 30 minutes

### M-12: `full_join_with_coalesce.fill_null(0.0)` corrupts key columns

- **File:** `dav_tool/calculations/core.py`
- **Line:** 64
- **Problem:** `fill_null(0.0)` applied to entire join result, including key columns (e.g., `STORE_NUMBER`). Null keys become `0.0`, corrupting string keys or causing type coercion.
- **Reason:** No exclusion of key columns from `fill_null`.
- **Recommended Fix:** Apply `fill_null(0.0)` only to non-key value columns.
- **Est. Effort:** 30 minutes

---

## Low

### L-1: Empty `__init__.py` at package root

- **File:** `dav_tool/__init__.py`
- **Problem:** Completely empty. Provides no public API surface.
- **Recommended Fix:** Define `__all__` or re-export key public types.
- **Est. Effort:** 15 minutes

### L-2: Empty `__init__.py` in `ui/` package

- **File:** `dav_tool/ui/__init__.py`
- **Problem:** Empty. Doesn't expose UI entry points.
- **Recommended Fix:** Define `__all__` or re-export key UI functions.
- **Est. Effort:** 15 minutes

### L-3: `config_builder.py` imports `Tuple` but never uses it

- **File:** `dav_tool/config_builder.py`
- **Line:** 10
- **Problem:** `Tuple` imported from typing but not used in any type annotation.
- **Reason:** Left over from refactoring.
- **Recommended Fix:** Remove unused import.
- **Est. Effort:** 1 minute

### L-4: Redundant conditional imports in `validation/store.py`

- **File:** `dav_tool/validation/store.py`
- **Lines:** 12, 76, 96
- **Problem:** `from dav_tool._aggregators import stream_store_aggregate` imported at module level (line 12) AND conditionally inside function bodies (lines 76, 96).
- **Reason:** Duplicate of module-level import.
- **Recommended Fix:** Remove the conditional imports.
- **Est. Effort:** 5 minutes

### L-5: Redundant conditional imports in `validation/item.py`

- **File:** `dav_tool/validation/item.py`
- **Lines:** 12, 42, 61
- **Problem:** Same pattern — `stream_item_aggregate` imported at module level AND inside function bodies.
- **Reason:** Duplicate of module-level import.
- **Recommended Fix:** Remove the conditional imports.
- **Est. Effort:** 5 minutes

### L-6: Canonical naming inconsistency — `Totalprice` vs `TOTAL_DOLLARS`

- **File:** `dav_tool/_aggregators.py`
- **Lines:** 178, 205
- **Problem:** Store level uses `Totalprice` (mixed case, no underscore) while item/UPC level uses `TOTAL_DOLLARS` (upper case, underscore). Inconsistent naming propagates to calculations.
- **Reason:** Different authors for different aggregation levels.
- **Recommended Fix:** Standardize on one convention across all levels (e.g., `TOTAL_DOLLARS`).
- **Est. Effort:** 1 hour

### L-7: Test coverage gaps for 6 modules

- **Files:** `_observability.py`, `_numeric.py`, `_column_utils.py`, `processing_context.py`, `options.py`, `config_validator.py`
- **Problem:** Zero test coverage for these modules.
- **Recommended Fix:** Add unit tests for each module.
- **Est. Effort:** 1-2 days total

### L-8: `save_format_config` uses `default=str` which silently type-converts

- **File:** `dav_tool/format_config.py`
- **Problem:** `json.dumps(..., default=str)` converts any non-serializable field to its string representation without warning. The `_completed_sections` set bug (known from prior audit) is one example.
- **Recommended Fix:** Replace `default=str` with explicit serialization for known non-serializable types.
- **Est. Effort:** 1 hour

### L-9: `has_header` false positive risk at 50% threshold

- **File:** `dav_tool/detection.py`
- **Lines:** 175-188
- **Problem:** Single-line 50% alpha threshold. A data row like `Store123,Product456,75.00,10` hits the threshold (2/4 alpha). Should sample multiple lines.
- **Recommended Fix:** Sample 2-3 lines and compare alpha ratio variance.
- **Est. Effort:** 2 hours

### L-10: `apply_column_names` silently ignores count mismatch

- **File:** `dav_tool/_normalizer.py`
- **Line:** 8
- **Problem:** When `len(column_names) != len(df.columns)`, returns df unchanged with no warning. Downstream code uses wrong column names.
- **Recommended Fix:** Log a warning when column name count doesn't match.
- **Est. Effort:** 15 minutes

---

## Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| **Critical** | 3 | Missing imports that cause NameErrors (C-1, C-2), dropped test file review (C-3) |
| **High** | 8 | Large files/functions (H-1 through H-6), no UI tests (H-7), naming inconsistency (H-8) |
| **Medium** | 12 | Duplicate merge functions (M-1), dead code (M-2, M-3, M-4), exception swallowing (M-5, M-6), cross-boundary imports (M-7), late imports (M-8), fragile mocks (M-9), unused import (M-10), data path bugs (M-11, M-12) |
| **Low** | 10 | Empty init files (L-1, L-2), unused/redundant imports (L-3, L-4, L-5), naming inconsistency (L-6), test gaps (L-7), serialization (L-8), detection edge cases (L-9, L-10) |
| **Total** | **33** | |

**Overall maintainability assessment:** The codebase has good abstractions at the service layer but the UI layer is the primary source of maintainability debt. The three UI files (onboarding.py, existing.py, helpers.py) account for ~3,300 lines, the largest functions, most of the dead code, the missing imports, and the cross-boundary dependencies. Addressing the large file/function decomposition (H-1 through H-6) would resolve the majority of structural issues.

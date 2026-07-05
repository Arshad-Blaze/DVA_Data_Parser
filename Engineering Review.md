# Engineering Review — DVA Data Parser

## Architecture Score: 8/10

The four-layer separation (UI → Parser → Aggregator → Validation → Reports) is clean and well-enforced. Each module has a focused responsibility and imports are structured accordingly. The `ProcessingContext`/`ExistingContext` dataclasses serve as a typed session state layer between UI and business logic.

**Strengths:**
- Clear separation of concerns with enforced module boundaries.
- `ProcessingTimer` and `ProcessingMetrics` provide built-in observability without coupling to any layer.
- Playwright E2E suite covers all major workflows.
- `smart_column_indices()` and `validate_column_mapping()` reduce boilerplate in both onboarding and existing pages.

**Weaknesses:**
- `_phase1_column_mapping()` and `_phase2_validation()` in `existing.py` duplicate ~30 lines of effective-type/column derivation logic.
- Column names (`prod_cols`/`test_cols`) are recomputed in Phase 3 of existing flow instead of being passed through context.
- No integration test coverage for the UI-connector layer (no tests that import UI modules directly).

---

## Maintainability: 7/10

Functions are generally under 50 lines. Naming conventions are consistent. The codebase avoids deep nesting and magic values.

**Strengths:**
- `helpers.py` centralizes shared UI logic (path cleaning, column detection, validation).
- `_observability.py` is a standalone, focused module.
- `ProcessingContext` makes state explicit and typed.

**Weaknesses:**
- No type annotations on several internal helper functions.
- `_phase1_column_mapping` in `existing.py` is ~150 lines and handles both rendering and business logic (column mapping UI + aggregation trigger).
- Error messages are duplicated across `onboarding.py` and `existing.py` (e.g., validation error guidance text).

---

## Performance: 8/10

**Strengths:**
- Aggregation uses Polars LazyFrames (`stream_store_aggregate`, `stream_item_aggregate`) via internal lazy → eager patterns.
- Detection, parsing, and preview are cached by early-return phase guards.
- No redundant aggregation identified in Phase 2/3 transitions.
- `get_column_names` is a lightweight header-only read.

**Weaknesses:**
- `_phase2_validation()` now calls `get_column_names()` again for the Schema Details expander duplicating the Phase 1 call. This is a minor file read (< 100 bytes for test data) but scales with column count.
- No chunked/batched validation execution for very large files.

---

## Memory Usage: 7/10

**Strengths:**
- `ProcessingTimer` runs a background thread tracking RSS peak memory.
- Aggregation functions return Polars DataFrames stored in context, not duplicated.

**Weaknesses:**
- `store_agg` and `item_agg` for both BAU and Test (4 DataFrames) are held in memory throughout Phase 3.
- Validation results (`store_df`, `comparison_df`, `summary_df`, `fr_prod`, `fr_test`) are also held in context until reset.
- No explicit cleanup or garbage collection trigger between phases.

---

## UI Responsiveness: 8/10

**Strengths:**
- `st.spinner()` wrappers on all 4 aggregation calls provide visual progress.
- Expanders for Processing Metrics and Schema Details keep the main view uncluttered.
- `st.rerun()` after aggregation ensures clean phase transitions.
- Error messages use `st.error()` with formatting rather than raw exception dumps.

**Weaknesses:**
- 4 sequential spinners during aggregation could be merged into a single `st.spinner("Running aggregations...")` to reduce visual noise.
- Validation spinner wraps the entire `_execute_validation` call—could be more granular.

---

## Parser Quality: 9/10

**Strengths:**
- Supports delimited, fixed-width, multiline, Excel, and HDR record formats.
- Graceful fallback and detection with user-facing warnings.
- `preview_raw`, `preview_flattened_multiline`, `preview_flattened_multiline_fixed` handle common edge cases.

**Weaknesses:**
- Multiline record support is stubbed but not fully wired through UI.
- Header-only detection for large files may not reflect full column set.

---

## Validation Quality: 9/10

**Strengths:**
- Store-level, item-level, compare-list, summary, and file-review validations all produce structured output.
- Results are stored as DataFrames and made available for report generation.
- `run_store_validation`, `run_item_validation`, `compare_files` all handle empty/null inputs gracefully.

**Weaknesses:**
- Validation execution in `_execute_validation` is a single monolithic function with many parameters.
- No incremental validation progress indicator.

---

## Test Coverage: 7/10

**Strengths:**
- 24 Playwright E2E tests covering onboarding, existing, and regression workflows.
- Tests verify detection, mapping, validation, reports, error states, and reset.
- HTML report generation captures phase-by-phase results.

**Weaknesses:**
- 2 pre-existing flaky/failing tests (`test_navigation_between_pages`, `test_detection_completes_for_both_sides`) with timing-sensitive locators.
- No unit tests for `smart_column_indices`, `validate_column_mapping`, or any `helpers.py` functions.
- No tests for `ProcessingTimer`, `ProcessingMetrics`, or `_observability.py`.
- No integration tests for aggregation or validation without Playwright.

---

## Technical Debt

| Issue | Severity | Impact |
|-------|----------|--------|
| `_phase2_validation` duplicates column-name derivation | Medium | Maintainability, minor perf |
| `columns` field on `ProcessingContext` is unused | Low | Dead code |
| 2 failing Playwright tests | Medium | CI reliability |
| `_phase1_column_mapping` too long (150+ lines) | Medium | Readability |
| Duplicate validation-error strings in onboarding/existing | Low | DRY violation |
| `_execute_validation` parameter explosion (20+ params) | Medium | Fragility |
| No unit tests for helper functions | High | Regression risk |

---

## Immediate Improvements (Next Sprint)

1. **Extract shared helpers**: Move effective-type column derivation to a shared function in `helpers.py` to eliminate the Phase 2/3 duplication.
2. **Fix flaky tests**: Replace `wait_for_timeout` with targeted `.wait_for()` or `.to_be_visible()` assertions in the 2 failing tests.
3. **Add unit tests**: Add `pytest` unit tests for `smart_column_indices`, `validate_column_mapping`, and `ProcessingTimer`.
4. **Consolidate spinners**: Merge 4 sequential aggregation spinners into one `st.status()` with 4 substeps.
5. **Prune dead code**: Remove unused `columns` field from `ProcessingContext`, or use it to store column names for the Schema Details expander.

---

## Future Roadmap

1. **Multiline record support** (blocked until this sprint completes).
2. **Chunked validation** for files exceeding available memory.
3. **Incremental progress** within long-running validations (e.g., "Validating store 45/200").
4. **Session persistence** — save/reload workflow state across browser sessions.
5. **CI pipeline** — integrate Playwright tests into GitHub Actions with HTML report artifacts.

---

## Multiline Readiness: 6/10

- `_get_hdr_params`, `preview_flattened_multiline`, and `preview_flattened_multiline_fixed` exist and are functional.
- HDR prefix detection and schema remapping are wired in.
- The effective-type/column-name derivation already handles multiline branches.
- What remains: full UI wiring of multiline record-type selection, schema application flow, and E2E tests.

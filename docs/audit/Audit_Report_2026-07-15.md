# DVA Platform 1.0 RC1 — Comprehensive Architecture & Code Audit

**Date:** 2026-07-15
**Auditor:** Principal Software Architect / Senior Python Engineer / Data Engineering Lead / Performance Engineer / QA Lead / Streamlit Expert
**Scope:** Full repository read-only audit
**Method:** Manual code review, execution path tracing, dependency analysis, pattern analysis

---

# Executive Summary

| Metric | Score | Rationale |
|--------|-------|-----------|
| **Architecture Score** | 6/10 | Layer boundaries exist but are frequently violated; UI contains business logic; no formal canonical/output/flush stages |
| **Maintainability Score** | 4/10 | `existing.py` (1720 lines), `helpers.py` (889 lines), massive duplication between onboarding and existing, 27-parameter functions |
| **Performance Score** | 6/10 | Polars streaming used correctly in fast paths; but repeated gc.collect(), unnecessary DataFrame copies, no memory budget |
| **Scalability Score** | 5/10 | Single-file detection assumption, no multi-file heterogeneity support, no automatic data access strategy |
| **Code Quality Score** | 5/10 | Mix of clean abstractions (workflow layer, options objects) and extreme procedural UI code; inconsistent naming conventions |
| **Enterprise Readiness Score** | 4/10 | Security concern (AutoAddPolicy), temp file leaks, no connection pool, no audit trail, XSS vector in phase progress |

**Overall Recommendation:** **NOT READY for RC1.** Critical bugs and architectural violations must be resolved before production release.

### Top Issues Blocking RC1
1. **CRITICAL:** `_completed_sections` set is not JSON-serializable — config save/load corrupts completion state entirely
2. **CRITICAL:** Column rename collision crash when a single column serves multiple business roles (store_col == units_col)
3. **CRITICAL:** `full_join_with_coalesce.fill_null(0.0)` corrupts key columns after full outer join
4. **CRITICAL:** Test file review result silently dropped in existing validation workflow
5. **CRITICAL:** `DiscoveryResult.from_context` typo — `"columns"` misspelled as `"colums"`, always returns None
6. **CRITICAL:**
   - Massive duplication (~40-50%) between `onboarding.py` and `existing.py`
   - `existing.py` at 1720 lines with 27-parameter functions
   - Detection logic in Connection Manager UI

---

# Repository Overview

## Project Structure

```
dav_tool/
├── __main__.py              # CLI entry
├── _aggregators.py          # Aggregation Engine (501 lines)
├── _column_utils.py         # Column detection & synonyms (73 lines)
├── _normalizer.py           # Canonical normalization (121 lines)
├── _observability.py        # Metrics, timers, DataFrame registry (239 lines)
├── _parsers.py              # Raw parsing engine (456 lines)
├── _reports.py              # File review reports (136 lines)
├── config.py                # Shared constants (7 lines)
├── config_builder.py        # Sample-based config generation (517 lines)
├── config_validator.py      # Config completeness validation (221 lines)
├── detection.py             # File type/delimiter detection (188 lines)
├── format_config.py         # FormatConfig dataclass + load/save (411 lines)
├── io.py                    # Safe CSV reader (27 lines)
├── options.py               # Option dataclasses (188 lines)
├── processing_context.py    # ProcessingContext, ExistingContext (145 lines)
├── calculations/
│   └── core.py              # Pure calc functions (198 lines)
├── certification/
│   ├── datasets.py
│   └── runner.py (499 lines)
├── datasource/
│   ├── base.py              # IDataSource interface (78 lines)
│   ├── local.py             # LocalDataSource (107 lines)
│   ├── ssh.py               # SSHDataSource (221 lines)
│   └── manager.py           # ConnectionManager singleton (98 lines)
├── operations/              # Data Operations Framework (7 operations)
├── ui/
│   ├── app.py               # Entry point (47 lines)
│   ├── certification_suite.py (119 lines)
│   ├── connection_manager.py (480 lines)
│   ├── existing.py          # Format Change UI (1720 lines)
│   ├── helpers.py           # Mixed concerns (889 lines)
│   └── onboarding.py        # Onboarding UI (882 lines)
├── validation/
│   ├── item.py              # Item validation (91 lines)
│   └── store.py             # Store validation (148 lines)
└── workflow/
    ├── __init__.py           # Phase labels
    ├── discovery.py          # Detection orchestration (374 lines)
    ├── processing.py         # Aggregation orchestration (190 lines)
    └── validation.py         # Validation orchestration (341 lines)
```

## Technology Stack

| Component | Version |
|-----------|---------|
| Python | >= 3.10 |
| Polars | >= 1.0 |
| Streamlit | >= 1.28 |
| Paramiko | >= 3.0 (optional) |
| psutil | >= 5.9 |

## Strengths
- Polars-first data processing with streaming engine for fast paths
- Well-designed options dataclasses (`ParseOptions`, `ColumnMapping`, `ValidationOptions`) for layer contracts
- `DiscoveryResult` as single source of truth for detection metadata
- Clean `IDataSource` abstraction with local/SSH implementations
- DataFrame registry for memory observability
- Operations framework is well-abstracted with 7 pluggable operations

## Weaknesses
- Layer separation is aspirational, not enforced — business logic bleeds into UI extensively
- Massive code duplication between onboarding and Format Change workflows
- Several critical bugs in data path (rename collisions, join fills, typo in field name)
- Config save/load is broken for progressive completion tracking
- No automatic data access strategy
- Connection Manager contains detection orchestration logic
- Temp files leak on SSH downloads
- No thread safety in connection manager singleton
- No formal Output layer or Flush layer integration

---

# Layer-by-Layer Audit

## 1. Connection Layer

### Current State
`datasource/` package with `IDataSource` interface, `LocalDataSource`, `SSHDataSource`, and singleton `ConnectionManager`. UI renders via `ui/connection_manager.py`.

### Findings

**CRITICAL — CM-1: Detection orchestration in Connection Manager**
`_show_path_preview` (connection_manager.py:444) calls `detect_file()` and stores `DiscoveryResult` in session state for downstream consumption. The Connection Manager should manage connections only — detection is a workflow responsibility.

**HIGH — SSH-1: Temp file leak in `download_if_required`**
`NamedTemporaryFile(delete=False)` creates a file that is never deleted (ssh.py:173-183). The open file handle is never explicitly closed. Long sessions fill `/tmp`.

**HIGH — SSH-2: `is_connected` opens new SSH channel on every call**
`exec_command("echo connected")` on every check (ssh.py:90-93) opens a new channel, allocates resources, and never closes stdin/stdout/stderr. Use `transport.is_active()` instead.

**HIGH — MGR-1: No thread safety on singleton**
Module-level globals (`_ACTIVE_SOURCE`, `_ACTIVE_CONFIG`) with no locking (manager.py:23-98). Race conditions in multi-threaded contexts.

**MEDIUM — SSH-3: AutoAddPolicy security risk**
Silently accepts unknown host keys (ssh.py:51). MITM attacks undetected.

**MEDIUM — SSH-4: `look_for_keys=False, allow_agent=False`**
Disables standard SSH key discovery (ssh.py:60-61). Users must explicitly specify key file.

**MEDIUM — LOC-1: `read_sample` uses implicit system encoding**
`open(path, "r", errors="ignore")` without explicit encoding (local.py:61). Inconsistent with other paths that use `cp1252` or `utf-8`.

**MEDIUM — LOC-2: Hidden files ignored by `list_files`**
`glob.glob("*")` does not match dotfiles (local.py:55).

**LOW — SSH-5: `disconnect` silently swallows exceptions**
`except Exception: pass` hides close failures (ssh.py:74-83).

**LOW — SSH-6: False negative in `is_connected` for restricted shells**
Servers with `/bin/false` or `command=` restriction will fail `exec_command` even when SFTP works.

### Recommendations
1. Move detection out of Connection Manager — CM should emit "path selected" events only
2. Close temp file handle immediately after creation; add cleanup mechanism
3. Replace `exec_command` with `transport.is_active()` for health checks
4. Add `threading.Lock` to all global state mutations
5. Use `WarningPolicy` instead of `AutoAddPolicy`; log security notice
6. Standardize encoding to `DEFAULT_ENCODING` across all `read_sample` implementations
7. Register `atexit` handler for cleanup

**Priority: P1 (items 1-4), P2 (items 5-6)**

---

## 2. Detection Layer

### Current State
`detection.py` (188 lines) handles file type detection, delimiter scoring, multiline detection. `workflow/discovery.py` (374 lines) orchestrates detection into `DiscoveryResult`.

### Findings

**CRITICAL — DET-1: `DiscoveryResult.from_context` typo**
`"colums"` instead of `"columns"` (discovery.py:96). `DiscoveryResult` reconstructed from context always has `columns=None`, causing `is_ready` to return False.

**HIGH — DET-2: Column propagation gap in `flatten_multiline`**
Creates new `DiscoveryResult` without `file_paths` (discovery.py:247-259). Downstream code expecting `file_paths` finds it missing after flattening.

**HIGH — DET-3: `_detect_encoding` for remote sources is inverted**
Checks `sample.encode(enc)` instead of `raw_bytes.decode(enc)` (config_builder.py:50-62). Guarantees wrong encoding detection for remote files.

**MEDIUM — DET-4: `has_header` false positive risk**
50% alpha threshold on single line (detection.py:175-188). A data row like `Store123,Product456,75.00,10` meets threshold (2/4 alpha). Should sample 2-3 lines and compare.

**MEDIUM — DET-5: Delimiter tie not handled**
`max(scores, key=scores.get)` returns arbitrary first max (detection.py:53). Pipe-delimited file could be detected as comma if both score 0.

**MEDIUM — DET-6: `detect_file` only inspects first file**
`fp = file_paths[0]` (discovery.py:149). Heterogeneous file collections produce wrong result for all but first file.

**MEDIUM — DET-7: `get_preview` fails for empty string `header_prefix`**
`""` is falsy but not `None` (discovery.py:282-296). Falls through with no warning.

**LOW — DET-8: Zero-score fallback to "fixed" is brittle**
Single-column CSV files are misclassified as fixed-width (detection.py:55).

### Recommendations
1. Fix typo `"colums"` → `"columns"` in `from_context`
2. Pass `file_paths` through `flatten_multiline` return
3. Fix `_detect_encoding` to decode raw bytes
4. Improve `has_header` to sample 2-3 lines with higher threshold
5. Handle delimiter ties with preference ordering
6. Validate or document multi-file homogeneity assumption

**Priority: P1 (items 1-3), P2 (items 4-6)**

---

## 3. Canonical Layer

### Current State
`_normalizer.py` (121 lines) provides normalization functions. `format_config.py` defines three-layer schema model. `workflow/canonical.py` (newly created, not yet integrated into UI pipeline).

### Findings

**CRITICAL — CAN-1: Rename-collision crash in normalize functions**
`normalize_store_chunk` uses `.rename({store_col: "STORE_NUMBER"}).select(["STORE_NUMBER", units_col, price_col])`. If `store_col == units_col`, the rename consumes the column and `.select(units_col)` fails. Same pattern in `normalize_item_chunk`, `normalize_upc_chunk`. Affects all aggregation paths.

**CRITICAL — CAN-2: `apply_column_names` silently ignores count mismatch**
When `len(column_names) != len(df.columns)`, returns df unchanged with no warning (normalizer.py:8). Downstream code uses wrong column names.

**HIGH — CAN-3: Inconsistent canonical naming conventions**
Store level: `Units`, `Totalprice` (mixed case). Item/UPC level: `UNITS_SOLD`, `TOTAL_DOLLARS` (upper case). This inconsistency propagates to `_merge_accumulate` functions and `calculations/core.py`.

**MEDIUM — CAN-4: `normalize_item_chunk` fragile column ordering**
`select` then `with_columns` pattern assumes column order matches between rename and with_columns references (normalizer.py:74-82). Works currently but fragile.

### Recommendations
1. Replace `rename().select()` with `with_columns(...alias(...))` in all normalize functions
2. Log warning when column name count doesn't match during `apply_column_names`
3. Adopt single canonical naming convention (e.g., `UNITS_SOLD`, `TOTAL_DOLLARS`) across all levels
4. Integrate `workflow/canonical.py` into UI pipeline as formal stage

**Priority: P1 (item 1), P2 (items 2-4)**

---

## 4. Requirement (Operation Selection) Layer

### Current State
`workflow/requirement.py` (newly created). `operations/` framework with 7 registered operations. Operations framework exists but is not wired into main workflow.

### Findings

**MEDIUM — REQ-1: Operations framework is disconnected from main pipeline**
7 operations exist (Aggregate, Filter, Sort, Sample, Statistics, Export, Preview) but are never called by onboarding or Format Change workflows. The `RequirementConfig` and `execute_requirement()` functions exist but are not integrated into any UI.

**MEDIUM — REQ-2: No UI for operation selection**
Users have no way to select Raw Data Review vs Aggregate Only vs Aggregate + Calculate. The `OperationType` enum has no rendering path.

**LOW — REQ-3: `AggregateOperation` accepts any column name without validation**
No check that column names align with canonical schema. User could enter arbitrary column names that don't exist in the data.

### Recommendations
1. Wire operations framework into both onboarding and Format Change phase progression
2. Add operation selection radio/select in workflow configuration phase
3. Validate operation column names against canonical schema

**Priority: P2**

---

## 5. Processing Layer

### Current State
`_aggregators.py` (501 lines), `workflow/processing.py` (190 lines). Streaming fast path for local delimited files, chunked path for remote/fixed-width/multiline.

### Findings

**CRITICAL — PRC-1: `full_join_with_coalesce.fill_null(0.0)` corrupts key columns**
`fill_null(0.0)` on entire merged DataFrame (calculations/core.py:64) applies to key columns like `STORE_NUMBER`. Polars either raises type error (Utf8 ← float) or coerces to float, destroying keys.

**HIGH — PRC-2: Fast path ignores `start_line` and `record_type`**
Fast path condition (aggregators.py:289) checks `source is None or source.supports_direct_path` but not `start_line == 0` or `record_type is None`. Files with non-zero start line or record type filtering use the fast path incorrectly.

**HIGH — PRC-3: Triple-duplicated `_merge_accumulate` functions**
`_merge_accumulate`, `_merge_accumulate_item`, `_merge_accumulate_upc` are structurally identical except for hardcoded column names (aggregators.py:208-258). Changes to canonical names must be coordinated across all three.

**HIGH — PRC-4: `run_file_review` missing `detail_layout` parameter**
Unlike `run_store_aggregation` which passes `detail_layout`, `run_file_review` does not (processing.py:139-180). Multiline HDR files produce incorrect file reviews.

**MEDIUM — PRC-5: Per-chunk `gc.collect()` causes performance overhead with no memory guarantee**
`del` + `gc.collect()` on every chunk (every 100k rows) has measurable cost (aggregators.py:316-323, 389-399, 462-470).

**MEDIUM — PRC-6: `apply_implied_decimals` mutates caller's dict in-place**
If the same schema dict is reused across operations, implied decimals are applied twice (processing.py:183-199).

**MEDIUM — PRC-7: Inconsistent sorting across aggregation levels**
Store aggregate sorts by `STORE_NUMBER`; UPC aggregate does not sort; Item aggregate sorts conditionally (aggregators.py:330, 404-405, 449, 475).

**MEDIUM — PRC-8: No canonical wrapper for `run_file_review`**
`run_store_aggregation_canonical` and `run_item_aggregation_canonical` exist but no `run_file_review_canonical`.

### Recommendations
1. Apply `fill_null(0.0)` only to non-key columns in `full_join_with_coalesce`
2. Add `start_line == 0 and record_type is None` to fast-path guard
3. Parameterize `_merge_accumulate` into single function with `group_cols` and `sum_cols` parameters
4. Add `detail_layout` to `run_file_review` call
5. Remove per-chunk `gc.collect()`; keep only final one after merge
6. Copy schema dict before mutation in `apply_implied_decimals`
7. Sort all aggregation results consistently
8. Add `run_file_review_canonical` for consistency

**Priority: P1 (items 1-4), P2 (items 5-8)**

---

## 6. Output Layer

### Current State
No formal Output layer exists. Reports are inline in UI files (`_display_results` in both onboarding.py and existing.py). `_reports.py` (136 lines) generates file review. Downloads are rendered as `st.download_button` in UI.

### Findings

**HIGH — OUT-1: No formal Output layer**
Reports, downloads, metrics, and export logic are embedded in UI functions (`_display_results`, `display_execution_summary`). There is no standalone Output service that could be reused or tested independently.

**MEDIUM — OUT-2: File review duplicates aggregation logic**
`generate_file_review` (reports.py) calls `stream_store_aggregate` and `stream_upc_summary` internally, redoing aggregation work that was already done in the processing phase. No mechanism to pass precomputed aggregations in all code paths.

**LOW — OUT-3: No export to formats other than CSV**
`output_config` format field exists but only CSV is implemented.

### Recommendations
1. Create `workflow/output.py` as formal Output layer service
2. Pass precomputed aggregations to file review generation  
3. Implement parquet export (config option already exists)

**Priority: P2**

---

## 7. Flush Layer

### Current State
`workflow/flush.py` (newly created). Not yet integrated into UI flow.

### Findings

**MEDIUM — FLH-1: Flush Layer not integrated into workflow**
The flush service exists but is not called at end of onboarding or Format Change pipelines. Resources are not released automatically.

**MEDIUM — FLH-2: `cleanup_dataframes` has broken nested-attribute matching**
Passing `keep_attrs=["prod.store_agg"]` (existing.py:842) tries to match `"prod.store_agg"` against simple attr names like `"store_agg"` — never matches. Works by accident because `getattr(ctx, "prod.store_agg", None)` returns `None`.

### Recommendations
1. Integrate `flush()` call at end of both workflow pipelines
2. Fix `cleanup_dataframes` nested attribute handling or remove dot-separated support

**Priority: P2**

---

## 8. Data Operations

### Current State
`operations/` package with 7 registered operations. Well-abstracted interface. Not wired into main workflow.

### Findings

**MEDIUM — OPS-1: Operations not wired into workflow**
Despite being well-designed, the operations framework has zero integration points with onboarding or Format Change workflows.

**LOW — OPS-2: No tests for operations**
No unit tests exist for any of the 7 operations. `test_operations.py` may exist but was not found during audit.

### Recommendations
1. Wire operations into workflow via Requirement Layer
2. Add unit tests for all 7 operations

**Priority: P2**

---

## 9. Configuration Layer

### Current State
`format_config.py` (411 lines), `config_builder.py` (517 lines), `config_validator.py` (221 lines).

### Findings

**CRITICAL — CFG-1: `_completed_sections` set not JSON-serializable**
`save_format_config` serializes set via `default=str` → produces garbage string. `load_format_config` reads back garbage → `set("{GENERAL, FILE}")` produces individual characters. Config save/load corrupts completion state entirely.

**CRITICAL — CFG-2: `smart_column_indices` maps all unfound roles to cols[0]**
Every unmapped column role silently selects the first column (column_utils.py:71-72). User sees Store, UPC, Description, Quantity, Price all mapped to column A with no warning.

**HIGH — CFG-3: `load_format_config` version default (1) inconsistent with constructor (2)**
`data.pop("version", 1)` vs `FormatConfig(version=2)`. Configs without version field are silently downgraded.

**HIGH — CFG-4: `config_from_ctx` does not preserve validation_config or output_config**
Any validation settings or output preferences on the context are lost when saving config.

**HIGH — CFG-5: `validate_config` does not check file existence for layout paths**
`cfg.layout_file` is checked for truthiness but not `os.path.exists()`.

**HIGH — CFG-6: `weight_col` not validated in `validate_config` for weight/mixed modes**
Missing even when `quantity_type == "weight"` or `"mixed"`.

**MEDIUM — CFG-7: `apply_format_config` derives schema from only 10 flattened rows**
Hardcoded `n_rows=10` for multiline flattening (format_config.py:341-354). Schema may be incomplete.

**MEDIUM — CFG-8: `build_config` only inspects first file (duplicate)**
Same issue as detection — config is built from a single file's structure.

**MEDIUM — CFG-9: `validate_section(BUSINESS_MAPPING)` requires all columns unconditionally**
Validates store/UPC/quantity/price regardless of `OutputMode`, but `validate_config` only requires them for VALIDATE mode. Inconsistent.

**LOW — CFG-10: `save_format_config` uses `default=str` which silently type-converts**
Any non-serializable field is converted to string without warning.

### Recommendations
1. Fix `_completed_sections` serialization: save as list, load as set
2. Return `None` for unmapped roles in `smart_column_indices`; warn user
3. Align `load_format_config` version default to 2 or add migration
4. Preserve `validation_config` and `output_config` in `config_from_ctx`
5. Validate layout file existence in `validate_config`
6. Validate `weight_col` for weight/mixed quantity types
7. Increase multiline flatten sample size or use full pipeline

**Priority: P1 (items 1-2), P2 (items 3-7)**

---

## 10. UI Layer

### Current State
`ui/onboarding.py` (882 lines), `ui/existing.py` (1720 lines), `ui/helpers.py` (889 lines), `ui/connection_manager.py` (480 lines).

### Findings

**CRITICAL — UI-1: Massive duplication between onboarding.py and existing.py**
Approximately 40-50% of `existing.py` is duplicated from `onboarding.py`: discovery integration, config loading, multiline handling, preview rendering, validation execution, metrics display, error messages, reset logic. Every bug fix must be mirrored.

**CRITICAL — UI-2: existing.py at 1720 lines with 27-parameter functions**
Should be split into 5-6 modules by phase. `_execute_validation` accepts 27 individual parameters — all of which already exist in structured form on `ctx`.

**CRITICAL — UI-3: Business logic in UI — manual option construction**
Both `_phase4_processing` and `_run_validation` manually construct `ParseOptions`/`ColumnMapping`/`ValidationOptions` from raw context fields instead of using `from_context()` class methods. Inconsistent with config builder output.

**HIGH — UI-4: Two dead functions in existing.py (120+ lines)**
`_compare_stores` (45 lines) and `_generate_file_reviews` (69 lines) are defined but never called anywhere.

**HIGH — UI-5: Column mapping re-selection in processing phase duplicates config**
Both workflows force users to re-select and re-confirm column mapping in the processing phase, even when it was already configured in the config phase.

**HIGH — UI-6: Column name cache never invalidated**
`cached_get_column_names` (helpers.py:28-57) caches per parameter hash but never clears. Stale columns returned when parameters change. Cache key is missing critical params (header_layout, trailer_prefix).

**HIGH — UI-7: config_builder.py: Temp file resource leak on early exception**
`NamedTemporaryFile(delete=False)` with no cleanup guarantee on unexpected exceptions (config_builder.py:126-131).

**HIGH — UI-8: Connection Manager session key sprawl (15+ keys)**
No central management; cross-file magic string dependencies cause subtle bugs on misspelling.

**HIGH — UI-9: `_detect_and_set` renders UI inside detection function**
Renders `st.text_input`, `st.error`, `st.success` inline during detection (existing.py:1041-1097). Pure logic function has Streamlit dependencies.

**HIGH — UI-10: Processing phase ignores effective fields**
`_phase4_processing` (existing.py:790-811) uses raw `prod_type`, `prod_delim` instead of `ctx.prod.eff_type`, `ctx.prod.eff_delimiter`. Effective fields computed at lines 641-672 are discarded.

**MEDIUM — UI-11: `render_phase_progress` hardcodes 6 max phases**
`max_phase=6` default (helpers.py:787) is wrong for Format Change (9 phases).

**MEDIUM — UI-12: `display_config_review` has NameError risk**
Uses `asdict(cfg)` (helpers.py:312) without importing it. Only works if `edit_and_accept_config` was called first.

**MEDIUM — UI-13: Multiple `st.rerun()` calls inside `st.spinner()` blocks**
Visual artifact — spinner may never complete properly.

**MEDIUM — UI-14: Workflow switch doesn't clear discovery results**
Switching between Onboarding and Format Change clears paths but not discovery results (connection_manager.py:284-291).

**LOW — UI-15: `render_phase_progress` uses `unsafe_allow_html=True`**
Theoretical XSS vector if phase labels ever contain user input.

**LOW — UI-16: `display_processing_history()` not gated on dev mode**
Shows execution history (timestamps, file/row counts) to all users.

### Recommendations
1. Extract shared workflow logic into `ui/shared_workflow.py`; eliminate duplication
2. Split `existing.py` into phase-specific modules
3. Replace manual `ParseOptions`/`ColumnMapping` construction with `from_context()` calls
4. Remove dead code (`_compare_stores`, `_generate_file_reviews`)
5. Make processing phase use config-phase column mapping by default
6. Cache-bust column name cache on path changes; include all params in cache key
7. Use context manager or `try/finally` for temp file cleanup
8. Centralize session state keys in a dataclass
9. Separate detection logic from UI rendering in `_detect_and_set`
10. Use `ctx.eff_type`, `ctx.eff_delimiter` etc. in processing phase
11. Pass correct `max_phase` from existing.py
12. Fix `asdict` import in `display_config_review`
13. Move `st.rerun()` outside `st.spinner()` blocks
14. Clear discovery results on workflow switch

**Priority: P1 (items 1-5), P2 (items 6-11), P3 (items 12-14)**

---

# Bug Report

## Critical Bugs

### B-CRIT-1: Config save/load corrupts completion tracking
**Description:** `_completed_sections` set → JSON serialization via `default=str` → deserialization into individual characters. Progressive config wizard completely broken after save/load cycle.
**Impact:** Users cannot save and resume configuration. Config must be rebuilt from scratch on every session.
**Root Cause:** `save_format_config` serializes sets as strings; `load_format_config` reads them back as character sets.
**Affected Modules:** `format_config.py` (lines 242-264)
**Suggested Resolution:** Save `_completed_sections` as list; load as set.

### B-CRIT-2: Aggregation crash when columns share roles
**Description:** `normalize_store_chunk` (and item/UPC equivalents) crash with `ColumnNotFoundError` when `store_col == units_col` or any other column role collision. The `.rename()` consumes the column name before `.select()` references it.
**Impact:** Any file where a single column serves two business roles (e.g., a column named "store_upc" mapped as both Store and UPC) causes an irrecoverable crash during aggregation.
**Root Cause:** `rename().select()` pattern in all three normalize chunk functions assumes all role columns are distinct.
**Affected Modules:** `_normalizer.py` (lines 38, 74, 111)
**Suggested Resolution:** Replace `rename().select()` with `with_columns(...alias(...))`.

### B-CRIT-3: Join fill corrupts key columns
**Description:** `full_join_with_coalesce` applies `fill_null(0.0)` to ALL columns including join keys. Null key values (from rows present only in one side) are filled with `0.0`, corrupting string keys or causing type coercion errors.
**Impact:** Store validation produces incorrect or empty results. Key columns become floats.
**Root Cause:** No exclusion of key columns from `fill_null`.
**Affected Modules:** `calculations/core.py` (line 64)
**Suggested Resolution:** Apply `fill_null(0.0)` only to non-key value columns.

### B-CRIT-4: Test file review silently dropped
**Description:** `_generate_both_file_reviews` returns `(fr_prod, fr_test, elapsed)`, but `run_existing_validation` only stores `fr_prod` (validation.py:122-128). The test file review is assigned to a local variable that immediately goes out of scope.
**Impact:** Format Change workflow never shows the test side file review. Missing feature from user perspective.
**Root Cause:** `ValidationResult` has no `file_review_test` field.
**Affected Modules:** `workflow/validation.py` (lines 120-134)
**Suggested Resolution:** Add `file_review_test` field to `ValidationResult` and store both results.

### B-CRIT-5: `DiscoveryResult.from_context` typo
**Description:** `columns=getattr(ctx, "colums", None)` — misspelled attribute name always returns `None`.
**Impact:** Any code that reconstructs `DiscoveryResult` from a `ProcessingContext` gets empty columns. `is_ready` returns `False`.
**Root Cause:** Simple typo in attribute name.
**Affected Modules:** `workflow/discovery.py` (line 96)
**Suggested Resolution:** Change `"colums"` to `"columns"`.

## High Bugs

### B-HIGH-1: Fast path ignores start_line/record_type (aggregators.py:289)
**Impact:** Files with `start_line > 0` are incorrectly parsed via the fast path, using the wrong header row. Data misalignment downstream.

### B-HIGH-2: `run_file_review` missing `detail_layout` (processing.py:139-180)
**Impact:** Multiline HDR files produce incorrect file reviews because detail layout is not passed to `generate_file_review`.

### B-HIGH-3: `_detect_encoding` inverted for remote sources (config_builder.py:50-62)
**Impact:** Wrong encoding detected for all remote/SSH files. Data corruption.

### B-HIGH-4: `has_header` false positive at 50% threshold (detection.py:175-188)
**Impact:** Files without headers detected as having headers; first data row used as column names.

### B-HIGH-5: Processing phase ignores effective fields (existing.py:790-811)
**Impact:** Multiline files processed with wrong delimiter and record type because raw discovery fields used instead of effective (computed) fields.

### B-HIGH-6: Column mapping re-selection duplicates config (existing.py:689-777, onboarding.py:419-424)
**Impact:** Users must configure column mapping twice — once in config phase, once in processing phase. Inconsistent selections cause wrong results.

### B-HIGH-7: `_apply_implied_decimals` mutates caller's dict (processing.py:183-199)
**Impact:** Implied decimals applied twice if schema dict reused across store + item operations.

### B-HIGH-8: Empty string `header_prefix` breaks preview (discovery.py:282-296)
**Impact:** `header_prefix=""` causes silent `None` return from `get_preview` instead of falling back to delimited multiline.

---

# Performance Report

## Memory

| Issue | Severity | Detail |
|-------|----------|--------|
| Per-chunk `gc.collect()` | MEDIUM | Called on every 100k-row chunk (aggregators.py). Adds ~5-10ms per chunk with no memory safety guarantee. Remove per-chunk GC; keep only final. |
| `_rows_to_df` builds intermediate dict | MEDIUM | Dict-of-lists → DataFrame creates 2x memory for large chunks (parsers.py:176-181). Use `pl.from_records()`. |
| Multiple DataFrame copies in validation | MEDIUM | `storelevelvalidation` creates new DataFrames for aggregation even when precomputed aggs are available in some code paths. |
| No memory budget enforcement | LOW | No limit on total DataFrame memory. Large files can OOM without warning. |

## CPU

| Issue | Severity | Detail |
|-------|----------|--------|
| `is_connected` SSH channel per call | HIGH | Opens SSH channel with `exec_command` on every check (ssh.py:90-93). Each call adds ~200-500ms. |
| Repeated aggregation in validation | MEDIUM | Validation layer can re-aggregate data that was already aggregated during processing phase. |
| Streamlit rerun overhead | MEDIUM | `st.rerun()` called inside `st.spinner()` (multiple locations) causes full page rerender with metadata download. |

## Streaming

| Issue | Severity | Detail |
|-------|----------|--------|
| Fast path ignores start_line/record_type | HIGH | Non-zero start_line files incorrectly use the streaming fast path instead of chunked path. |
| No automatic strategy selection | MEDIUM | No RAM/disk/network-aware decision between streaming, chunking, or local copy. User doesn't choose, but system doesn't decide either. |

## Repeated Work

| Issue | Severity | Detail |
|-------|----------|--------|
| Flattened preview re-reads data | MEDIUM | `_flattened_preview_and_schema` reads and flattens the same files twice (existing.py:1185-1277). |
| `cached_get_column_names` never invalidates | HIGH | Column name cache returns stale data when file or parameters change. |
| Multiple `get_active_source()` calls | LOW | Same function calls `get_active_source()` 2-3 times unnecessarily. |

---

# Technical Debt

## Code Duplication

| Area | Lines | Duplicated In | Impact |
|------|-------|---------------|--------|
| Discovery integration + CM consumption | ~100 | onboarding.py + existing.py (both _phase1_discovery) | Bug fixes must be applied twice |
| Multiline / HDR handling | ~200 | onboarding.py + existing.py | Different implementations, same logic |
| Config loading with apply_format_config | ~50 | onboarding.py + existing.py | Different key prefixes, identical logic |
| Preview rendering | ~40 | onboarding.py + existing.py | Near-identical render blocks |
| Validation execution | ~80 | onboarding.py + existing.py | Different ParseOptions construction patterns |
| _display_results | ~50 | onboarding.py + existing.py | Same UI structure, different context fields |
| _merge_accumulate functions | ~50 | aggregators.py (3 copies) | Hardcoded column names in each |
| _reset_phase | ~30 | onboarding.py + existing.py | Only key prefixes differ |

## Large Files

| File | Lines | Problem |
|------|-------|---------|
| `ui/existing.py` | 1720 | Should be 5-6 modules (~300 lines each) |
| `ui/helpers.py` | 889 | 6 distinct responsibilities in one file |
| `ui/onboarding.py` | 882 | Should share 50% with existing.py |
| `config_builder.py` | 517 | Near-duplicate sample loading in stage builders |
| `_aggregators.py` | 501 | Triple-duplicated merge functions, 24-parameter aggregate |

## Long Functions

| Function | File | Lines | Parameters |
|----------|------|-------|------------|
| `_execute_validation` | existing.py | ~120 (body) | **27** |
| `_phase1_discovery` | existing.py | ~240 | 1 (ctx) — inline logic |
| `_phase4_processing` | existing.py | ~240 | 1 (ctx) — inline logic |
| `build_config` | config_builder.py | ~200 | 10 |
| `storelevelvalidation` | store.py | ~80 | **21** |
| `run_item_validation` | item.py | ~70 | **23** |
| `_render_section_fields` | helpers.py | ~250 | 5 — all 8 sections in one function |

## Dead Code

| Function | File | Lines | Last Used |
|----------|------|-------|-----------|
| `_compare_stores` | existing.py | 45 | Never called |
| `_generate_file_reviews` | existing.py | 69 | Never called |
| `ProcessingContext.validate_for_processing` | processing_context.py | 25 | Never called by UI |
| `ProcessingContext.output_mode` | processing_context.py | 1 field | Only read in dev diagnostics |

## Duplicate Logic

| Logic | Locations | Fix |
|-------|-----------|-----|
| ParseOptions construction | onboarding.py:476-478, existing.py:790-811, validation.py:1332-1351, 1477-1506 | Use `from_context()` everywhere |
| Sample loading in config builder | config_builder.py:139-218, 380-405 | Factor into shared method |
| `_get_delimited_columns` | discovery.py:362-374 + helpers.py:224-252 | Reuse the discovery function |
| Store list download | validation.py:143-166 + helpers.py:209-221 | Unify into data source method |

## Architecture Drift

| Target Architecture | Current Implementation | Drift |
|--------------------|----------------------|-------|
| Detection → Canonical → Processing | Config → Processing | Canonical schema editing exists but isn't a formal stage. Processing still references physical schema. |
| Connection Manager manages connections only | Connection Manager runs detection and stores DiscoveryResults | Detection orchestration in UI layer. |
| Output layer | No Output layer | Reports embedded in UI functions. |
| Flush layer | No integration | Flush module exists (new) but not called from workflow. |
| Requirement layer | No integration | Requirement module exists (new) but not called from workflow. Operations framework exists but not wired. |

---

# Testing Report

## Coverage by Test Suite

| Suite | Files | Tests | Coverage Assessment |
|-------|-------|-------|---------------------|
| Unit tests | ~12 files | 210+ | Good for core logic (aggregation, config, detection) |
| Golden regression | 1 file | 12 parametrized | Good — covers 4 formats × 3 aggregation levels |
| E2E Playwright (onboarding) | 8 files | ~40 | Good flow coverage |
| E2E Playwright (existing) | 6 files | ~30 | Good flow coverage |
| E2E Connection Manager | 1 file | ~5 | Minimal |

## Missing Tests

| Area | Risk | Priority |
|------|------|----------|
| **Operations framework** — 0 tests across 7 operations | Operations may crash or produce wrong results | HIGH |
| **Flush Layer** — 0 tests | Cleanup is never validated | HIGH |
| **Canonical Layer** — 1 test file (`test_canonical_layer.py`) exists but coverage unknown | Schema propagation not validated | MEDIUM |
| **Large file / memory** — No automated memory tests | OOM risk undetected | HIGH |
| **Streaming edge cases** — No tests for start_line > 0, record_type filtering, multiline with offsets | Fast-path bypass bugs undetected | HIGH |
| **Concurrent connections** — No thread safety tests | Race conditions in connection manager undetected | MEDIUM |
| **Config save/load round-trip** — No test for `_completed_sections` preservation | Config corruption undetected | CRITICAL |
| **Column collision scenarios** — No tests for store_col == units_col | Aggregation crash path untested | CRITICAL |
| **Encoding detection for remote sources** — No SSH-specific encoding tests | Data corruption path untested | HIGH |
| **Field-level comparison edge cases** — No tests for `full_join_with_coalesce` null handling | Key column corruption undetected | CRITICAL |

## Regression Risk Analysis

| Change | Affected Tests | Risk Level |
|--------|---------------|------------|
| Fix `from_context` typo (columns) | Golden regression, detection tests, E2E discovery | LOW — typo fix should be transparent |
| Fix `rename().select()` → `with_columns()` | Golden regression, aggregation tests | MEDIUM — output must match exactly |
| Fix `fill_null(0.0)` to exclude keys | Validation tests, golden regression | MEDIUM — edge cases may change |
| Fix `_completed_sections` serialization | Config save/load tests | LOW — only affects completion tracking |
| Remove dead code `_compare_stores` | None — function is never called | LOW |
| Add `detail_layout` to `run_file_review` | Report tests | LOW — missing param addition |
| Fix `_detect_encoding` for remote sources | Config builder tests, E2E SSH | HIGH — encoding detection changes |

---

# Documentation Review

## Accuracy

| Document | Accuracy | Issues |
|----------|----------|--------|
| `README.md` | Good | Generally accurate; minor version drift |
| `ARCHITECTURE.md` | Partial | Describes 7-phase workflow but target is 8-layer pipeline |
| `docs/user_guide.md` | Good | Step-by-step walkthroughs accurate |
| `docs/technical_docs.md` | Partial | Layer descriptions don't match new Canonical/Requirement/Output/Flush stages |
| `docs/ConnectionManager.md` | Good | Accurate description of IDataSource and CM architecture |
| `AGENTS.md` | Good | Engineering instructions still valid |

## Missing Sections

| Missing | Impact |
|---------|--------|
| **Operations framework documentation** | Developers cannot understand how to add new operations |
| **Configuration schema reference** | No document explaining FormatConfig fields and sections |
| **Deployment guide** | No instructions for production deployment |
| **Security considerations** | AutoAddPolicy, temp file leaks, XSS — no documented guidance |
| **Performance tuning guide** | No guidance on chunk sizes, streaming vs chunking, large file handling |

## Outdated Content
- `ARCHITECTURE.md` mentions "7-phase workflow" but target is 8-layer pipeline
- `docs/technical_docs.md` references "Existing Comparison" which is now "Format Change"

---

# Production Readiness

## Reliability — Score: 5/10

**Strengths:**
- Structured error handling in workflow layer
- `DiscoveryResult.error` field for detection failures
- Config validation before processing

**Weaknesses:**
- Critical bugs in data path (rename collisions, join key corruption, config serialization)
- No retry logic in connection layer
- No circuit breakers for large files
- Fast path can silently produce wrong results (start_line ignored)

**Critical blockers:** B-CRIT-1, B-CRIT-2, B-CRIT-3, B-CRIT-5 must be fixed before production use.

## Maintainability — Score: 4/10

**Strengths:**
- Clean options dataclasses (ParseOptions, ColumnMapping)
- Good separation in workflow layer functions
- `IDataSource` interface with proper abstraction

**Weaknesses:**
- `existing.py` (1720 lines) and `onboarding.py` (882 lines) are unmanageable
- 40-50% code duplication between the two files
- `helpers.py` (889 lines) has 6 distinct responsibilities
- 27-parameter functions, 21-parameter functions
- 3 identical `_merge_accumulate` functions
- Dead code accumulates without removal

## Performance — Score: 6/10

**Strengths:**
- Polars streaming engine for fast path
- Configurable chunk size (100k rows default)
- DataFrame registry for memory tracking
- Parallel aggregation via ThreadPoolExecutor

**Weaknesses:**
- No automatic data access strategy
- Per-chunk `gc.collect()` overhead
- Repeated reads in preview paths
- `is_connected` opens SSH channel on every call
- No memory budget enforcement

## Scalability — Score: 5/10

**Strengths:**
- Chunked processing for remote sources
- Streaming aggregation for local files
- Thread pool for parallel aggregation

**Weaknesses:**
- Only inspects first file for detection/config
- No multi-file heterogeneity support
- No partitioning or sharding
- Connection manager is process-singleton, not scalable horizontally

## Supportability — Score: 5/10

**Strengths:**
- Processing metrics and history tracking
- Memory snapshots and DataFrame registry
- Developer diagnostics panel

**Weaknesses:**
- No structured logging (ad-hoc `print` statements in observability)
- No audit trail for configuration changes
- No telemetry or monitoring integration
- Error messages mix technical details with user-facing guidance

---

# RC1 Readiness

## Completed
- ✅ Flush Layer created as service module
- ✅ Canonical Layer created as formal pipeline stage
- ✅ Requirement Layer created with operation selection
- ✅ "Certification" renamed to "Format Change" across UI
- ✅ Configuration wizard replaced with single-page config in Format Change
- ✅ DiscoveryColumn propagation fixed (CM → ProcessingContext)
- ✅ Stale discovery clearing on path change
- ✅ Processing layer canonical-aware methods added
- ✅ Phase labels updated to target pipeline naming
- ✅ 210 unit tests pass with zero regressions

## Partially Complete
- ⚠️ Connections Layer: Collapsible summary exists but session handling improvements remain
- ⚠️ Detection Layer: `DiscoveryResult` as contract exists but has propagation bugs
- ⚠️ Canonical Layer: Module exists but not integrated into UI pipeline
- ⚠️ Processing Layer: Canonical methods exist but old paths still active in UI
- ⚠️ Format Change workflow: Renamed and config simplified, but 1720-line file not split

## Missing
- ❌ Data Access Strategy component (automatic stream/copy/chunk decision)
- ❌ Output Layer as formal pipeline stage
- ❌ Flush Layer integration into UI workflow
- ❌ Requirement Layer integration into UI workflow
- ❌ Operations framework wired into main pipeline
- ❌ EFFECTIVE_QUANTITY generation in aggregation
- ❌ UOM from column support in aggregation
- ❌ Performance regression baseline
- ❌ Memory tests
- ❌ Large-file automated tests

## Blocked
- 🔒 Data Access Strategy requires system-level monitoring (psutil for RAM/disk, network speed detection)
- 🔒 operations/ framework integration requires UI changes to show operation selection

---

# Action Plan

## Priority 1 — Critical (Must Fix Before RC1)

| # | Task | Est. Complexity | Risk | Dependencies |
|---|------|----------------|------|--------------|
| 1 | Fix `_completed_sections` save/load (serialize as list) | Low | Low | None |
| 2 | Fix `rename().select()` → `with_columns(...alias(...))` in all 3 normalize functions | Medium | Medium | Golden tests must validate output |
| 3 | Fix `full_join_with_coalesce` to exclude key columns from `fill_null(0.0)` | Low | Medium | Validation tests |
| 4 | Add `file_review_test` to `ValidationResult` and store both file reviews | Low | Low | None |
| 5 | Fix `DiscoveryResult.from_context` typo (`colums` → `columns`) | Low | Low | None |
| 6 | Add `start_line == 0 and record_type is None` to fast-path guard | Low | Medium | Aggregation tests |
| 7 | Add `detail_layout` to `run_file_review` call | Low | Low | Report tests |
| 8 | Fix `_detect_encoding` to decode raw bytes for remote sources | Medium | High | SSH E2E tests |
| 9 | Return `None` for unmapped column roles; warn user in UI | Low | Low | Column utils tests |

**Total estimated effort: ~3-4 days**

## Priority 2 — High (Should Fix Before RC1)

| # | Task | Est. Complexity | Risk | Dependencies |
|---|------|----------------|------|--------------|
| 10 | Extract shared logic from onboarding.py + existing.py into `ui/shared_workflow.py` | High | High | P1 fixes must be applied first |
| 11 | Split existing.py into phase-specific modules (~5-6 files) | Medium | Medium | P1-10 |
| 12 | Replace manual ParseOptions/ColumnMapping construction with `from_context()` | Low | Medium | None |
| 13 | Remove dead code (`_compare_stores`, `_generate_file_reviews`) | Low | Low | None |
| 14 | Cache-bust column name cache; include all params in cache key | Low | Low | None |
| 15 | Fix `is_connected` to use transport-level check | Low | Medium | SSH module |
| 16 | Close temp file handle in SSH `download_if_required`; add cleanup | Low | Low | None |
| 17 | Add `threading.Lock` to connection manager singleton | Low | Low | None |
| 18 | Parameterize `_merge_accumulate` into single function | Low | Medium | Aggregation tests |
| 19 | Fix `has_header` with multi-line sampling and higher threshold | Medium | Medium | Detection tests |
| 20 | Remove per-chunk `gc.collect()` in aggregation loops | Low | Low | Memory tests |
| 21 | Integrate Flush Layer into workflow UI pipelines | Low | Low | None |
| 22 | Integrate Requirement Layer operations into workflow UI | Medium | Medium | UI changes |
| 23 | Add unit tests for operations framework | Medium | Low | None |
| 24 | Fix `apply_implied_decimals` to copy dict before mutation | Low | Low | None |

**Total estimated effort: ~8-10 days**

## Priority 3 — Medium (Post-RC1)

| # | Task | Est. Complexity | Risk |
|---|------|----------------|------|
| 25 | Split helpers.py into single-responsibility modules | Medium | Medium |
| 26 | Implement Data Access Strategy component | High | High |
| 27 | Implement EFFECTIVE_QUANTITY and UOM from column | Medium | Medium |
| 28 | Formalize Output Layer as pipeline stage | Medium | Low |
| 29 | Add memory budget enforcement | Medium | Medium |
| 30 | Implement parquet export | Low | Low |
| 31 | Add `run_file_review_canonical` for consistency | Low | Low |
| 32 | Sort all aggregation results consistently | Low | Low |
| 33 | Fix `validate_config` for layout file existence and weight_col | Low | Low |
| 34 | Add `atexit` handler for connection cleanup | Low | Low |
| 35 | Add comprehensive E2E tests for large files | Medium | Low |
| 36 | Update ARCHITECTURE.md to match 8-layer pipeline | Low | Low |

**Total estimated effort: ~10-15 days**

---

# Appendix: Finding Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| **CRITICAL** | 12 | Config serialization (2), normalization rename collisions (3), join corruption, missing file review, typo, encoding inversion (2), UI duplication (2) |
| **HIGH** | 24 | Fast path safety (2), missing parameters (2), cache invalidation, session state management, dead code, duplicate work, performance (SSH), security (2), validation gaps (3), column propagation (2) |
| **MEDIUM** | 38 | Naming conventions, sorting, GC overhead, UI rendering issues, testing gaps, documentation gaps, missing edge cases, code organization |
| **LOW** | 15 | Style issues, minor edge cases, unused fields, theoretical XSS |

**Total findings: 89**

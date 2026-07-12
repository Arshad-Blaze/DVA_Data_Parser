# CHANGELOG — Workflow Refactoring Sprint (Discovery Elimination)

**Branch:** phase4_streaming
**Date:** 2026-07-12
**Scope:** Connection → Discovery → Configuration workflow deduplication

---

## Objective

Eliminate duplicate detection, preview generation, flattening, and file enumeration
between Connection Manager and Discovery phases. Ensure Discovery consumes the existing
DiscoveryResult produced during remote preview. Remove fallback to legacy local-file
discovery when a remote datasource is active.

---

## Bug Fixes (Critical)

### 1. `is_multiline_record()` False Positives for Standard Delimited Files
**File:** `dav_tool/detection.py`
**Severity:** Critical

The fixed-width HDR multiline check (lines 103-118) fired too easily. Standard CSV
files with alphanumerics like `Store123,Product456,75,12.99` would produce
`text_prefixes={"St"}` and `data_count=2`, incorrectly triggering `True` for multiline.

This caused standard delimited files to enter the multiline path, requiring unnecessary
flattening and displaying "Complete file detection and flattening above to proceed"
messages for simple CSVs.

**Fix:** Require prefix to repeat on 2+ lines AND verify data lines contain no common
delimiters (ruling out CSVs with alphanumerics).

### 2. `cached_get_column_names` Cache Key Incomplete
**File:** `dav_tool/ui/helpers.py`
**Severity:** High

Cache key used only `paths|file_type|delimiter|record_type`, missing `layout`,
`start_line`, and `header_prefix`. Two different layouts/sources could return stale
cached results.

**Fix:** Cache key now includes all parameters that affect column name extraction.

### 3. Misleading "Complete file detection and flattening" Message
**File:** `dav_tool/ui/onboarding.py`
**Severity:** Medium

The message appeared for all cases where `parsing_ready=False`, including delimited
files that don't need flattening.

**Fix:** Three distinct messages: detection didn't complete, multiline needs flattening,
or column detection failed.

### 4. Pre-existing: `build_config([])` Returns `file_type='fixed'`
**File:** `dav_tool/config_builder.py`
**Severity:** Low

When called with empty file_paths, the function fell through to `detect_file_type("")`
which returned "fixed" for empty input.

**Fix:** Early return with empty `FormatConfig()` when no file path provided.

### 5. Connection Manager → Discovery "No files found" Bug
**File:** `dav_tool/ui/onboarding.py`
**Severity:** Critical

`_phase1_discovery()` called `get_file_list()` which required explicit file paths,
but the CM stored a folder path. When the CM was active, the fallback `get_file_list()`
returned no files, showing "No files found" even though CM had already discovered them.

**Fix:** Reordered `_phase1_discovery()` to check `_cm_discovery` FIRST. If CM has a
valid result (file_paths + file_type), consume it directly. Fallback to `get_file_list()`
+ `detect_file()` only when no CM result.

### 6. Config Wizard Stuck (Config → Validate Config)
**File:** `dav_tool/ui/onboarding.py`, `dav_tool/ui/existing.py`
**Severity:** Critical

`build_config()` was called on every Streamlit rerun, creating fresh `FormatConfig`
with empty `_completed_sections`. The wizard could never complete because sections
were reset on each rerun.

**Fix:** Reuse existing `ctx._generated_config` via `getattr(ctx, '_generated_config', None)`.
Only call `build_config()` when no config exists yet.

### 7. "Configuration complete" Never Shown
**File:** `dav_tool/ui/onboarding.py`
**Severity:** High

The `all_done` block in `_phase2_configuration()` set `ctx.phase = PHASE_CONFIG_VALIDATED`
+ `st.rerun()`, so the `if ctx.config_locked:` block (which renders "Configuration complete.
Proceed to validation.") was never reached.

**Fix:** Removed premature phase advance from `all_done` block. The button now appears
correctly after config is locked.

### 8. Connection Manager Per-Side Discovery Keys
**File:** `dav_tool/ui/connection_manager.py`
**Severity:** High

`_show_path_preview()` stored all discoveries under `_cm_discovery`, so selecting BAU
overwrote Test's discovery (or vice versa).

**Fix:** Added `discovery_key` parameter to `_show_path_preview()`. Existing workflow
stores BAU/Test under `_cm_bau_discovery` / `_cm_test_discovery`.

### 9. Explicit file_paths Assignment
**File:** `dav_tool/ui/connection_manager.py`
**Severity:** Medium

The Connection Manager's `_show_path_preview()` detected file type and columns but
did not set `discovery.file_paths = file_paths` before storing the result. Downstream
consumption found `file_paths` empty.

**Fix:** Added explicit `discovery.file_paths = file_paths` before session storage.

### 10. Polars DataFrame Constructor Warning
**File:** `dav_tool/_parsers.py`
**Severity:** Low

`pl.DataFrame(rows)` produced a warning about `orient` parameter.

**Fix:** Added `orient="row"` to `pl.DataFrame(rows)` construction.

---

## Architecture Changes

### 5. `DiscoveryResult` Enhanced as Single Source of Truth
**File:** `dav_tool/workflow/discovery.py`

`DiscoveryResult` now carries ALL detection metadata:
- `file_paths`, `file_type`, `delimiter`, `columns`, `schema`
- `header_prefix`, `header_layout`, `detail_layout`
- `trailer_prefix`, `trailer_layout`
- `ml_record_types`, `ml_delimiter`, `ml_flattened`
- `start_line`, `record_type`, `layout`

New methods:
- `from_context(ctx)` — build from existing ProcessingContext
- `apply_to_context(ctx)` — apply all results to a ProcessingContext
- `needs_flattening` — property: True only for multiline/hierarchical formats

### 6. Connection Manager Stores DiscoveryResult
**File:** `dav_tool/ui/connection_manager.py`

`_show_path_preview()` now uses `detect_file()` from the discovery service instead
of calling `is_multiline_record()` and `detect_file_type()` directly. Stores the
result in `st.session_state["_cm_discovery"]` for downstream consumption.

Removed direct imports of `preview_raw`, `is_multiline_record`, `detect_file_type`.

### 7. Onboarding Consumes Existing DiscoveryResult
**File:** `dav_tool/ui/onboarding.py`

`_phase1_discovery()` now:
1. Checks for `_cm_discovery` from Connection Manager
2. If found and matching current file paths, reuses it — **no re-detection**
3. If not found, runs `detect_file()` once via the Discovery service
4. Stores `discovery` on `ctx.discovery` for downstream consumption
5. Standard delimited files skip flattening entirely

Added import: `from dav_tool.workflow.discovery import detect_file, DiscoveryResult`

### 8. Existing Workflow Uses DiscoveryResult
**File:** `dav_tool/ui/existing.py`

`_detect_and_set()` now uses `detect_file()` instead of calling detection functions
directly. Stores `DiscoveryResult` on `side_ctx.discovery`.

Added import: `from dav_tool.workflow.discovery import detect_file, DiscoveryResult`

### 9. `config_builder.build_config()` Accepts DiscoveryResult
**File:** `dav_tool/config_builder.py`

New optional parameter `discovery: Optional[DiscoveryResult]`. When provided, reuses
detected `file_type`, `delimiter`, `header_prefix`, `ml_record_types`, and layout
metadata — **no re-detection**.

Both onboarding and existing workflows now pass `discovery=ctx.discovery` or
`discovery=ctx.prod.discovery` / `ctx.test.discovery`.

### 10. `ProcessingContext` Carries Discovery
**File:** `dav_tool/processing_context.py`

New field: `discovery: Optional[DiscoveryResult] = None`

This is the bridge between the Discovery phase and all downstream phases.

### 11. Remote Source Fallback Removed
**File:** `dav_tool/ui/helpers.py`

`get_file_list()` documentation updated. When a remote source is active, it
ALWAYS uses the source — never falls back to local filesystem. Falls back to
local only when source is None (local mode).

### 12. FormatConfig Reuse (Config Wizard Fix)
**Files:** `dav_tool/ui/onboarding.py`, `dav_tool/ui/existing.py`

`build_config()` is no longer called on every Streamlit rerun. The existing
`ctx._generated_config` is reused via `getattr()`. This prevents the config
wizard from being stuck with empty `_completed_sections`.

### 13. Per-Side Discovery Keys (Existing Page)
**File:** `dav_tool/ui/connection_manager.py`

`_show_path_preview()` now accepts a `discovery_key` parameter. The Existing
workflow stores BAU and Test discoveries separately under `_cm_bau_discovery`
and `_cm_test_discovery` to prevent overwrite.

### 14. Explicit file_paths Assignment
**File:** `dav_tool/ui/connection_manager.py`

Added `discovery.file_paths = file_paths` before session storage to ensure
downstream consumption has valid paths.

---

## Files Modified

| File | Change |
|------|--------|
| `dav_tool/detection.py` | Fixed false positive in `is_multiline_record()` |
| `dav_tool/_parsers.py` | Added `orient="row"` to `pl.DataFrame(rows)` |
| `dav_tool/workflow/discovery.py` | Enhanced `DiscoveryResult` with full metadata, `from_context()`, `apply_to_context()`, `needs_flattening` |
| `dav_tool/processing_context.py` | Added `discovery` field to `ProcessingContext` |
| `dav_tool/config_builder.py` | Added `discovery` parameter to `build_config()`, early return on empty paths |
| `dav_tool/ui/connection_manager.py` | `_show_path_preview()` uses Discovery service, stores result, per-side discovery keys, explicit file_paths |
| `dav_tool/ui/onboarding.py` | `_phase1_discovery()` consumes existing DiscoveryResult, fixed misleading message, config wizard reuse |
| `dav_tool/ui/existing.py` | `_detect_and_set()` uses Discovery service, config wizard reuse |
| `dav_tool/ui/helpers.py` | Fixed cache key, documented remote fallback behavior |
| `tests/e2e/onboarding/test_onboarding_config_builder.py` | Fixed strict mode, updated flow test |
| `tests/e2e/onboarding/test_onboarding_config_validation.py` | Updated `_navigate_to_config_validation` helper |

---

## Test Results

**Before:** 113 passed, 1 failed (pre-existing `test_build_config_no_files`)
**After:** 134 passed, 0 failed

All golden tests pass (delimited, fixed, multiline, hdr_fixed × store/item/upc).
All edge case tests pass.
All datasource tests pass.
All validation service tests pass.
All report tests pass.

---

## Workflow After Changes

```
Connection (CM detects file type, stores DiscoveryResult)
    ↓
Discovery (Onboarding/Existing CONSUMES CM's DiscoveryResult — no re-detection)
    ↓
Configuration (build_config CONSUMES DiscoveryResult — no re-detection)
    ↓
Configuration Validation
    ↓
Processing
    ↓
Validation
    ↓
Reports
```

No duplicated backend work occurs between phases.
No misleading messages displayed.
No local filesystem logic invoked during remote streaming workflows.
Flattening only executes for multiline/hierarchical/header-detail formats.
Config wizard is not stuck on reruns (FormatConfig reuse).
"Configuration complete" message now visible (no premature phase advance).
Per-side discoveries prevent overwrite (Existing page).

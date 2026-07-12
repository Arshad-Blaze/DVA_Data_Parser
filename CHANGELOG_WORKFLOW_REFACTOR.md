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

---

## Files Modified

| File | Change |
|------|--------|
| `dav_tool/detection.py` | Fixed false positive in `is_multiline_record()` |
| `dav_tool/workflow/discovery.py` | Enhanced `DiscoveryResult` with full metadata, `from_context()`, `apply_to_context()`, `needs_flattening` |
| `dav_tool/processing_context.py` | Added `discovery` field to `ProcessingContext` |
| `dav_tool/config_builder.py` | Added `discovery` parameter to `build_config()`, early return on empty paths |
| `dav_tool/ui/connection_manager.py` | `_show_path_preview()` uses Discovery service, stores result |
| `dav_tool/ui/onboarding.py` | `_phase1_discovery()` consumes existing DiscoveryResult, fixed misleading message |
| `dav_tool/ui/existing.py` | `_detect_and_set()` uses Discovery service |
| `dav_tool/ui/helpers.py` | Fixed cache key, documented remote fallback behavior |

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

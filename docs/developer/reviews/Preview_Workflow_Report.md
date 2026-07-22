# Preview Workflow Report

## Root Cause

The preview system had no explicit staging. The same `cached_preview_raw` function was called at different points in the UI with different parameter sets, making it unclear what each preview represented. No function name indicated the preview stage.

## Architecture Impact

**Low.** No architecture changes. Added 5 dedicated stage helper functions with clear names and documentation. The underlying `_parsers.preview_raw()` function already handled all file types correctly.

## Business Impact

Users saw "Data Preview" labels without knowing whether they were looking at raw data, parsed data, or mapped data. This was especially confusing for fixed-width files where raw lines and parsed columns look completely different.

## Fix Implemented

### 1. Five preview stage helpers

**File:** `dav_tool/ui/onboarding.py:106-166`

```
Raw Preview (unparsed lines)
    ↓
Detected Preview (parsed per detection result)
    ↓
Flattened Preview (multiline only — HDR/record-type merging)
    ↓
Parsed Preview (columns extracted per layout)
    ↓
Canonical Preview (post-mapping column names)
```

### 2. Each function documents its stage

Each function has:
- A unique `st.subheader()` label showing the stage name
- A clear info message when no data is available at that stage
- Explicit parameter list matching what that stage requires

### 3. Fixed-width flow uses staged previews

In `_fixed_width_workflow_staged()`:
- Raw Preview → always shown first
- Parsed Preview → shown only after layout is confirmed

### 4. Multiline flow uses flattened preview

The existing `_multiline_flow()` already called `_show_ml_preview_and_schema()` — this is preserved but now prefixed with `_show_raw_preview()`.

## No Data Staleness

Preview caching uses `cached_preview_raw()` which computes a hash of all parameters (file path, file type, delimiter, layout, start_line, record_type, source id). If any parameter changes, a new cache key is computed and the preview is refreshed.

## Remaining Risks

1. **No explicit "stale preview" indicator**: If the user changes layout but the preview was computed with the old layout, the cache key changes automatically. No staleness issue.
2. **Preview does not trigger re-detection**: Preview functions consume detection results; they never call `detect_file()`. This is by design.
3. **Large previews**: Fixed-width files with many columns produce wide DataFrames. The preview is limited to 10 rows and uses `st.dataframe()` which handles scrolling gracefully.

## Test Evidence

Each stage helper initializes its own `pl.DataFrame()` and checks `is_empty()` before rendering. Empty states display an info message instead of a blank dataframe. The `_show_parsed_preview()` correctly returns early for non-fixed-width file types.

# Fixed-Width Workflow Report

## Root Cause

The fixed-width workflow was embedded inline in `_phase1_discovery()` with no separation between stages:
- Raw preview, layout builder, and parsed preview were mixed in a single conditional block
- Start Line and Record Type inputs appeared after layout, making the flow unclear
- Layout Builder and uploaded layout had different code paths but were supposed to produce the same `LayoutDefinition` object

## Architecture Impact

**Medium.** The workflow stages already existed conceptually but were not expressed in code. The fix adds helper functions that make the stages explicit without changing the architecture.

## Business Impact

Users had no visual cue about which stage of the fixed-width workflow they were in. The same screen showed raw data, layout editor, and parsed preview simultaneously, causing confusion about what action to take next.

## Fix Implemented

### 1. New staged workflow function

**File:** `dav_tool/ui/onboarding.py:168-226`

`_fixed_width_workflow_staged()` implements the clear pipeline:

```
Raw Preview → Detection Results → Layout Builder → Parsed Preview
```

Each stage uses a dedicated helper:
- `_show_raw_preview()` — unparsed lines via `preview_raw_lines`
- `_show_detected_preview()` — parsed per detection (not used for fixed-width directly)
- `_show_parsed_preview()` — columns extracted per confirmed layout

### 2. Stage helpers added

**File:** `dav_tool/ui/onboarding.py:106-166`

| Helper | Purpose |
|--------|---------|
| `_show_raw_preview()` | Display unparsed file content |
| `_show_detected_preview()` | Display parsed data per detection |
| `_show_flattened_preview()` | Multiline flattened preview |
| `_show_parsed_preview()` | Display columns extracted per layout |
| `_show_canonical_preview()` | Display post-mapping columns |

### 3. Updated discovery flow

In `_phase1_discovery()`, the fixed-width path now calls the staged function and then provides Start Line / Record Type inputs only after layout is confirmed.

### 4. Layout Builder simplification

**File:** `dav_tool/ui/layout_builder.py`

Reduced from 7 editable columns to 4:
- Column Name (editable)
- Start (editable)
- End (calculated, disabled)
- Length (editable)
- Type (editable)

Removed: Format, Nullable, Description.

The `_rows_to_layout()` function still produces the same `{field, start, end, from, length, type}` dict for 100% backward compatibility with all callers (`load_layout`, `apply_format_config`, `parse_fixed_width_chunks`, etc.).

## Remaining Risks

1. **Layout Builder session key is shared**: The `SESSION_KEY = "_layout_builder_state"` is global. If the user switches between fixed-width files in the same session, old layout state may persist. Mitigation: each caller uses a unique `key_prefix`.
2. **No undo in Layout Builder**: Users who accidentally clear all rows have no undo — they must re-enter columns from scratch.
3. **Candidate layout is a hint**: Auto-detected boundaries are shown but may not match user expectations. The `_fixed_width_workflow_staged` function passes them through but does not validate them.

## Test Evidence

- `_rows_to_layout()` produces identical output format before and after simplification
- `render_layout_builder()` accepts the same `existing_layout` and `candidate_layout` parameters
- All existing callers (onboarding, existing flow, HDR flow) continue to receive `LayoutDefinition` objects with the same shape

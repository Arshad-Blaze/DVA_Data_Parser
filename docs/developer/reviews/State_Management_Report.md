# Streamlit Session State Management Audit

## 1. Widget Keys That Could Trigger Unnecessary Reruns

### Issue 1.1: `st.text_input("Store List File Path")` — missing key

- **File**: `dav_tool/ui/onboarding.py:548`
- **Root cause**: The store list path text input in `_phase4_processing` has no `key` parameter. Every Streamlit rerun (triggered by any other widget interaction) resets this field to empty, forcing the user to re-enter it.
- **Risk**: **High** — user-visible data loss; store list path disappears on any unrelated widget click.
- **Recommended fix**: Add `key="onb_storelist_path"` to the widget.

### Issue 1.2: `st.selectbox("Store List Delimiter", ...)` — missing key (first instance)

- **File**: `dav_tool/ui/onboarding.py:549`
- **Root cause**: Inside `if not ctx.mapping_confirmed:` block, the first `st.selectbox` for store list delimiter has no key. A second selectbox with the same label appears at line 564 with key `storelist_delim_sel` (inside `if ext not in [".xlsx", ".xls"]:`). The first instance loses its value on every rerun.
- **Risk**: **Medium** — user must re-select delimiter after any widget interaction in the same phase.
- **Recommended fix**: Add `key="onb_storelist_delim"` to line 549.

### Issue 1.3: `st.button("Proceed to Processing & Validation")` — missing key (existing flow)

- **File**: `dav_tool/ui/existing.py:736`
- **Root cause**: Button has no explicit key. Streamlit uses implicit identity based on widget position, which is fragile. If conditional rendering above this button changes, the button's identity could shift, causing state loss or double-submission.
- **Risk**: **Low** — button position is stable in practice, but fragile.
- **Recommended fix**: Add `key="ex_proceed_processing"`.

### Summary

All critical-path widgets in the discovery and config steps (folder paths, selectboxes, radio buttons, number inputs) have stable keys. The two missing keys in `_phase4_processing` are the only gaps.

---

## 2. Session State Initialization

### Issue 2.1: Scattered initialization — no single source of truth

- **Files**: `app.py:9-12`, `connection_manager.py:38-62`, `onboarding.py:74-77`, `existing.py:79-82`, `helpers.py:65-66,102-103,114-115`, `layout_builder.py:180-181`
- **Root cause**: Session state keys are initialized lazily across 6+ modules. Each module uses a defensive `if key not in st.session_state:` pattern, but there is no single entry point that guarantees all keys exist. Example: `_preview_cache` is initialized by two different functions (`cached_preview_raw` and `cached_preview_raw_lines`).
- **Risk**: **Medium** — the defensive pattern prevents crashes, but initialization order is implicit. A new module accessing a key before its lazy init would silently receive the wrong type or miss values. The `_detection_cache` is redundantly initialized in both onboarding.py and existing.py.
- **Recommended fix**: Create a single `_init_session_state()` function called once at app startup in `app.py` that initializes all known session state keys.

### Issue 2.2: `_cm_file_paths` set without initialization check

- **File**: `dav_tool/ui/connection_manager.py:452`
- **Root cause**: `st.session_state["_cm_file_paths"] = file_paths` is set without checking if the key exists first. While Python will create the key, there's no guarantee of type consistency on first access from other modules.
- **Risk**: **Low** — key is only used within `_show_path_preview` itself.
- **Recommended fix**: Initialize `_cm_file_paths` in `_init_state()` alongside other `_cm_*` keys.

### Issue 2.3: `onb_cfg_accepted` popped but never set

- **File**: `dav_tool/ui/onboarding.py:61`
- **Root cause**: `_reset_phase()` pops `"onb_cfg_accepted"` from session state, but this key is never set anywhere in the codebase. Dead code.
- **Risk**: **Low** — harmless `pop` with default.
- **Recommended fix**: Remove line 61.

---

## 3. Preserve Detection Across Reruns

### Issue 3.1: `_cm_selected_path` prematurely set by preview side-effect

- **File**: `dav_tool/ui/connection_manager.py:451` (`_show_path_preview`)
- **Root cause**: `_show_path_preview()` sets `st.session_state["_cm_selected_path"] = path` as a side effect of rendering the data preview. This happens **before** the user clicks "Use This Path for Onboarding". The onboarding page at `onboarding.py:237` reads `_cm_selected_path` and treats the path as confirmed. The "Use This Path" button only collapses the CM — the path was already "selected" by the preview.
- **Risk**: **High** — the path is effectively auto-selected when a user browses to a directory in the CM file browser, bypassing the intended confirmation step.
- **Recommended fix**: Remove `st.session_state["_cm_selected_path"] = path` from `_show_path_preview()`. The path should only be set when the user explicitly clicks "Use This Path" (connection_manager.py:326-329).

### Issue 3.2: Detection + preview dual cache but preview cache never invalidated on re-detect

- **Files**: `dav_tool/ui/onboarding.py:350-355`, `dav_tool/ui/existing.py:350-360`
- **Root cause**: The "Re-detect" buttons clear the `_detection_cache` and `ctx.discovery`, but do NOT clear the `_preview_cache` or `_column_name_cache` (in `helpers.py`). After re-detection, stale preview data could still be served from the preview cache until the cache key changes.
- **Risk**: **Medium** — stale preview data could be shown briefly. The preview cache keys include file paths and column names, so if detection returns different results, the cache key changes and the old entry is naturally evicted. However, if the same file produces different detection results, the cache key is identical and the stale preview persists.
- **Recommended fix**: Call `invalidate_preview_caches()` in `onboarding.py:353` and `existing.py:351-352` (currently `invalidate_preview_caches` is defined at `helpers.py:125` but never called anywhere).

### Issue 3.3: `ctx.discovery` persistence is robust

- **Note**: The dual-caching strategy (`_detection_cache` + `ctx.discovery`) works well. `_phase1_discovery` in onboarding.py stores `ctx.discovery = discovery` at both line 276 (CM path) and line 376 (detection path). In existing.py, `_detect_and_set` stores it at line 993. The `discovery_done` guard (onboarding.py:228) correctly short-circuits re-detection.
- **Risk**: **None** for this sub-point.

---

## 4. Invalidate State Only When Appropriate

### Issue 4.1: `_reset_phase()` correctly scoped

- **Files**: `dav_tool/ui/onboarding.py:55-65`, `dav_tool/ui/existing.py:61-70`
- **Root cause**: Both `_reset_phase()` functions correctly clear only their own context (`onb_ctx` / `ex_ctx`) and prefixed session state keys (`onb_cfg_*` / `ex_cfg_*`). They do **not** touch connection manager state (`_cm_*`), shared caches (`_detection_cache`, `_preview_cache`, `_column_name_cache`), or `execution_history`.
- **Risk**: **None** — appropriate scoping.
- **Recommended fix**: No change needed.

### Issue 4.2: `_reset_phase()` tries to pop session state keys that don't exist

- **File**: `dav_tool/ui/onboarding.py:64`
- **Root cause**: `st.session_state.pop("_show_config", None)` targets a session state key that is never created. The actual `_show_config` is a dynamic attribute set on the context object (`ctx._show_config = True` at line 455), not on `st.session_state`. Similarly `onb_cfg_accepted` (line 61) is never set.
- **Risk**: **Low** — harmless `pop` with default, but misleading.
- **Recommended fix**: Replace line 64's `k == "_show_config"` with a check for context attribute `getattr(ctx, '_show_config', False)` if the intent is to clean up the old context (which is already replaced at line 60). Alternatively, just leave it — the new `ProcessingContext()` won't have `_show_config` set.

### Issue 4.3: `cleanup_dataframes` in existing.py clears both prod/test context DFs

- **File**: `dav_tool/ui/existing.py:570,742,935`
- **Root cause**: `cleanup_dataframes(ctx)` with `ctx` being an `ExistingContext` traverses attributes via `getattr(ctx, attr)`. But the large DataFrames live on `ctx.prod.store_agg`, `ctx.test.store_agg`, etc., not directly on `ctx`. The `df_attrs` list in `cleanup_dataframes` (helpers.py:1001-1005) does not include `prod.` or `test.` prefixed names. These DataFrames on sub-contexts may not be freed.
- **Risk**: **Medium** — memory may not be released when expected for existing-flow aggregations.
- **Recommended fix**: Either expand `df_attrs` to include sub-context paths, or call `cleanup_dataframes` on `ctx.prod` and `ctx.test` separately.

---

## 5. Check for `st.rerun()` Calls That Could Cause Infinite Loops

### Issue 5.1: No infinite loop risks found

- **Verdict**: All 50+ `st.rerun()` calls across the codebase are conditioned on explicit user actions (button clicks, file uploads) or one-shot state transitions. **No infinite loop risk** exists.
- **Specific analysis of onboarding.py:457**: `st.rerun()` is called after `ctx.phase = PHASE_CONFIG`. On the next rerun, `_phase1_discovery` returns early because `discovery_done` is True (phase >= 2). The condition `ctx.phase == 0` at line 447 is then False, so this code path never re-executes. **Safe.**
- **Specific analysis of onboarding.py:508**: `st.rerun()` after accepting mapping. On the next rerun, `ctx.config_locked` is True and `ctx._show_config` is False, so the mapping form is no longer rendered. The button at line 496 is not shown. **Safe.**
- **Recommended fix**: No change needed.

---

## Summary of All Recommendations

| # | File | Line(s) | Issue | Risk | Fix |
|---|------|---------|-------|------|-----|
| 1.1 | onboarding.py | 548 | `st.text_input("Store List File Path")` missing key | High | Add `key="onb_storelist_path"` |
| 1.2 | onboarding.py | 549 | `st.selectbox("Store List Delimiter")` missing key | Medium | Add `key="onb_storelist_delim"` |
| 1.3 | existing.py | 736 | `st.button("Proceed...")` missing key | Low | Add `key="ex_proceed_processing"` |
| 2.1 | multiple | — | Scattered initialization, no single source of truth | Medium | Create `_init_session_state()` in app.py |
| 2.2 | connection_manager.py | 452 | `_cm_file_paths` set without init guard | Low | Add to `_init_state()` |
| 2.3 | onboarding.py | 61 | Dead code: `onb_cfg_accepted` popped but never set | Low | Remove line 61 |
| 3.1 | connection_manager.py | 451 | `_cm_selected_path` set as preview side-effect before user confirms | High | Remove the premature `st.session_state["_cm_selected_path"] = path` assignment |
| 3.2 | helpers.py | 125 | `invalidate_preview_caches()` defined but never called | Medium | Call it on re-detect (onboarding.py:353, existing.py:351-352) |
| 3.3 | — | — | Detection persistence is robust | None | No change |
| 4.1 | — | — | `_reset_phase()` scoping is correct | None | No change |
| 4.2 | onboarding.py | 64 | Popping session state keys that don't exist | Low | Remove or document as no-op |
| 4.3 | existing.py + helpers.py | 1001-1005 | `cleanup_dataframes` doesn't free sub-context DFs (`prod.store_agg`, etc.) | Medium | Expand `df_attrs` or call per sub-context |
| 5.1 | — | — | No infinite loop risks found | None | No change |

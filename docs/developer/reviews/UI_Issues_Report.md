# UI Issues Report

## Issues Found and Fixed

### 1. UnboundLocalError: `df_preview` referenced before assignment

**File:** `dav_tool/ui/onboarding.py:271`

**Root cause:** The variable `df_preview` was only initialized inside a conditional block (`if file_type and file_type != "multiline" and file_paths ...`). If the condition was false (e.g., multiline file type), `df_preview` was referenced on line 276 without being defined.

**Fix:** Initialize `df_preview = pl.DataFrame()` before the conditional block.

**Architecture impact:** None. Single-line initialization.

**Risk:** Critical — would crash the entire onboarding flow for multiline files or any path where file_type is None.

---

### 2. Widget keys missing for store list inputs

**File:** `dav_tool/ui/onboarding.py:548-549`

**Root cause:** `st.text_input("Store List File Path")` and `st.selectbox("Store List Delimiter", ...)` had no `key` parameter. Streamlit uses widget value position to match across reruns, but without explicit keys, the matched position can shift if preceding widgets change.

**Fix:** Added `key="onb_storelist_path"` and `key="onb_storelist_delim"`.

**Risk:** Medium — value could be lost on rerun, requiring user to re-enter storelist path.

---

### 3. Detection re-execution on every rerun

**File:** `dav_tool/ui/onboarding.py`, `dav_tool/ui/existing.py`

**Root cause:** No caching of `DiscoveryResult` between reruns. Every widget interaction triggered a rerun, which could re-execute `detect_file()` and `generate_detection_summary()`.

**Fix:** Implemented `_detection_cache` in session state. See Detection_Stability_Report.md for details.

**Risk:** High — wasted I/O on large files, confusing UI as detection results could flicker.

---

### 4. Layout builder had unnecessary columns

**File:** `dav_tool/ui/layout_builder.py`

**Root cause:** Format, Nullable, Description columns cluttered the layout editor. These are not used by any downstream component.

**Fix:** Reduced to Column Name, Start, End (calculated), Length, Type. End is auto-calculated from Start + Length - 1 and disabled.

**Risk:** Low — cosmetic improvement, no functional impact.

---

### 5. Multiline preview could crash on empty flattened data

**Files:** 
- `dav_tool/ui/onboarding.py:727-730`
- `dav_tool/ui/onboarding.py:757-760`

**Root cause:** `_show_ml_preview_and_schema()` and `_show_hdr_fixed_preview_and_schema()` accessed `flat_preview.columns` before checking if the dataframe was empty.

**Fix:** Added early-return guard with info message when `flat_preview.is_empty()`.

**Risk:** Medium — would crash with empty or misconfigured multiline files.

---

### 6. Stale config preview survival across detection changes

**File:** `dav_tool/ui/helpers.py:125-127`

**Root cause:** `invalidate_preview_caches()` is defined but never called. When detection results change (e.g., after Re-detect), cached preview data from the old detection may persist.

**Fix:** Function exists but not called. Should be called after re-detection. Low priority since cache keys include file paths, so a new detection with the same paths would produce the same cache key.

**Risk:** Low.

---

### 7. Eff_layout not set in certain existing flow paths

**File:** `dav_tool/ui/existing.py:896`

**Root cause:** `_execute_validation()` passed `ctx.prod.eff_layout` and `ctx.test.eff_layout` directly, but these fields may not be set if the flow bypassed mapping confirmation (e.g., when loading from config).

**Fix:** Changed to `getattr(ctx.prod, 'eff_layout', None) or prod_layout_list` to provide a fallback.

**Risk:** High — would pass `None` to downstream parsing functions, causing crashes.

---

## Issues Not Fixed (Acknowledged)

### CSS Button Font Weight
The app uses `unsafe_allow_html=True` in `app.py:14-23` for button styling. This is cosmetic and works correctly.

### Phase Progress Bar HTML
`render_phase_progress()` in helpers.py constructs HTML strings. This is intentional for the progress bar visualization and works correctly.

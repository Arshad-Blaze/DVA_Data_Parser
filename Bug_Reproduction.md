# Bug Reproduction — DVA Platform RC1

**Date:** 2026-07-15
**Scope:** Verified Critical and High issues (excluding Already Fixed)
**Method:** Code execution path tracing, logic analysis

---

## Critical Bugs

### B-CRIT-1: Config save/load corrupts completion tracking

**Severity:** Critical

**Steps to Reproduce:**
1. Open DVA Platform, navigate to Format Change workflow
2. Complete Phase 1 (Detection) and Phase 2 (Configuration) — several sections checked in single-page config
3. Click "Save Config & Phase Labels"
4. Close session or switch workflows
5. Reload or switch back to Format Change
6. Click "Load Saved Config"

**Expected Result:** Previously completed sections are restored; progress is continuous.

**Actual Result:** `_completed_sections` is deserialized as individual characters (`{'{', "'", 'G', 'E', 'N', ...}`). Progressive config wizard shows all sections as incomplete. Config must be rebuilt from scratch.

**Affected Modules:** `dav_tool/format_config.py` (lines 212, 245, 262-264)

**Root Cause:** `_completed_sections` is a `set` which is not JSON-serializable. `save_format_config` uses `json.dump(default=str)` which calls `str()` on the set, producing a JSON string like `"{'GENERAL', 'FILE'}"`. `load_format_config` reads this string back and calls `set("{'GENERAL', 'FILE'}")`, which iterates over individual characters.

**Evidence:**
- `format_config.py:212`: `_completed_sections: set = field(default_factory=set)`
- `format_config.py:262-264`: `json.dump(d, f, indent=2, default=str)`
- `format_config.py:245`: `completed = data.get("_completed_sections", set())` — set() constructor called on string

**Reproducibility:** 100%

---

### B-CRIT-2: Aggregation crash when columns share roles

**Severity:** Critical

**Steps to Reproduce:**
1. Open DVA Platform, upload a file
2. In column mapping, map the same column to two business roles (e.g., Store = "A", Units = "A")
3. Run store or item aggregation

**Expected Result:** Aggregation handles column collision gracefully, possibly using the column twice.

**Actual Result:** `ColumnNotFoundError` raised at `_normalizer.py:38` (or 74, 111). `.rename({store_col: "STORE_NUMBER"})` consumes the column; subsequent `.select()` referencing the original column name fails because the column was already renamed.

**Affected Modules:** `dav_tool/_normalizer.py` (lines 38, 74, 111 — all three normalize functions)

**Root Cause:** Pattern: `df.rename({col_a: "NEW_NAME"}).select(["NEW_NAME", col_b])`. When `col_a == col_b`, the rename changes the column name before select references it.

**Evidence:**
- `_normalizer.py:38-39` (normalize_store_chunk)
- `_normalizer.py:74-75` (normalize_item_chunk)
- `_normalizer.py:111-112` (normalize_upc_chunk)
- All three follow: `df.rename({x: "X"}).select(["X", y, z])`

**Reproducibility:** 100% when any two role columns point to the same column.

---

### B-CRIT-3: Join fill corrupts key columns

**Severity:** Critical

**Steps to Reproduce:**
1. Run store validation with two files that have some stores in one file but not the other
2. The full outer join produces null values in key columns for unmatched rows
3. `fill_null(0.0)` converts these nulls to `0.0`

**Expected Result:** Unmatched rows keep null keys or are handled selectively. Key columns remain strings.

**Actual Result:** Null key values are filled with `0.0`. Depending on Polars version: either type error (Utf8 ← float) or silent coercion of key columns to float, corrupting store numbers like `"01234"` to `1234.0`.

**Affected Modules:** `dav_tool/calculations/core.py` (line 64)

**Root Cause:** `df.fill_null(0.0)` on the entire merged DataFrame, with no exclusion of key/string columns.

**Evidence:**
- `calculations/core.py:64`: `.fill_null(0.0)` called on full outer join result without column filtering

**Reproducibility:** 100% when full outer join produces nulls in key columns.

---

### B-CRIT-4: Test file review silently dropped

**Severity:** Critical

**Steps to Reproduce:**
1. Run Format Change validation (prod vs test)
2. Observe the file review section in the UI

**Expected Result:** Both production and test file reviews are displayed.

**Actual Result:** Only production file review is shown. Test file review is computed (visible in logs/metrics) but never stored or displayed.

**Affected Modules:** `dav_tool/workflow/validation.py` (lines 120-134)

**Root Cause:** `_generate_both_file_reviews` returns `(fr_prod, fr_test, elapsed)`. `run_existing_validation` destructures all three values but only stores `result.file_review = fr_prod`. The `ValidationResult` dataclass has no `file_review_test` field. The `fr_test` variable goes out of scope immediately.

**Evidence:**
- `validation.py:22-33`: `ValidationResult` has `file_review: Optional[...]` but no `file_review_test`
- `validation.py:122-129`: `fr_prod, fr_test, elapsed = _generate_both_file_reviews(...)` followed by `result.file_review = fr_prod`

**Reproducibility:** 100% — always affects Format Change workflow.

---

## High Bugs

### B-HIGH-1: Fast path ignores start_line/record_type

**Severity:** High

**Steps to Reproduce:**
1. Upload a file with `start_line > 0` or with `record_type` filtering
2. Run aggregation

**Expected Result:** Chunked processing path is used, respecting start_line offset and record_type filter.

**Actual Result:** Fast path (Polars `scan_csv`) reads from row 0 with no record_type filter. Data is misaligned — header rows included in data, trailer rows not filtered out.

**Affected Modules:** `dav_tool/_aggregators.py` (lines 289, 362, 436)

**Root Cause:** Fast-path guard condition checks only `can_use_fast_path` (which checks source/delimiter/file_type) but does **not** check `start_line == 0` or `record_type is None`.

**Evidence:**
- `_aggregators.py:289`: `if file_type == "delimited" and can_use_fast_path(...)` — no start_line/record_type check
- Same pattern at lines 362 and 436 for item/uac paths

**Reproducibility:** 100% for delimited files with `start_line > 0` or non-None `record_type`.

---

### B-HIGH-2: `run_file_review` missing `detail_layout`

**Severity:** High

**Steps to Reproduce:**
1. Upload a multiline HDR file with detail_layout defined
2. Run file review in any workflow

**Expected Result:** File review correctly parses detail lines from multiline HDR.

**Actual Result:** `detail_layout` is not passed to `generate_file_review`. For multiline HDR files, detail records are parsed with wrong layout, producing incorrect row/column counts in file review.

**Affected Modules:** `dav_tool/workflow/processing.py` (lines 150-174)

**Root Cause:** `run_file_review` calls `generate_file_review(...)` without `detail_layout=parse_opts.detail_layout`. Compare `run_store_aggregation` which correctly passes `detail_layout=parse_opts.detail_layout`.

**Evidence:**
- `processing.py:55` (store agg): `detail_layout=parse_opts.detail_layout` — present
- `processing.py:170` (file review): no `detail_layout=` argument in `generate_file_review(...)` call

**Reproducibility:** 100% for multiline HDR files with detail_layout.

---

### B-HIGH-3: `_detect_encoding` inverted for remote sources

**Severity:** High

**Steps to Reproduce:**
1. Connect via SSH
2. Upload a file with encoding `cp1252` (or any non-UTF-8 encoding)
3. The file is downloaded; `_detect_encoding` runs on the local copy

**Expected Result:** Encoding is detected correctly from raw bytes.

**Actual Result:** `sample.encode(enc)` re-encodes already-decoded string. The test checks if the string is representable in `enc`, not whether the original bytes decode as `enc`. CP1252 bytes like `\x92` decode to `'` in UTF-8; `'`.encode('cp1252') may fail or produce different bytes. Wrong encoding detected for all remote files.

**Affected Modules:** `dav_tool/config_builder.py` (lines 50-62)

**Root Cause:** For remote sources, file is already decoded to string by `read_sample()`. The function re-encodes this string and checks if it matches. Correct approach: operate on raw bytes before decoding.

**Evidence:**
- `config_builder.py:58`: `sample.encode(enc, errors="strict")` — re-encodes already-decoded string
- `datasource/base.py:53`: `IDataSource.read_sample()` returns `str`

**Reproducibility:** 100% for remote sources with non-UTF-8 encoding.

---

### B-HIGH-4: `has_header` false positive at 50% threshold

**Severity:** High

**Steps to Reproduce:**
1. Upload a file with first data row like `Store123,Product456,75.00,10`
2. Auto-detection runs

**Expected Result:** File detected as having no header.

**Actual Result:** File detected as having a header. Row `Store123,Product456,75.00,10` has 2/4 alpha tokens (50%) — meets threshold. First data row becomes column names.

**Affected Modules:** `dav_tool/detection.py` (lines 175-188)

**Root Cause:** Only 1 line sampled; 50% alpha threshold is too low for single-line heuristic.

**Evidence:**
- `detection.py:177`: `lines = _read_sample_lines(file_path, 1, source)` — 1 line
- `detection.py:185`: `alpha_count >= len(values) / 2` — 50% threshold

**Reproducibility:** ~50% for files with mixed alpha/numeric headers or data rows with 50%+ alpha content.

---

### B-HIGH-5: Processing phase ignores effective fields

**Severity:** High

**Steps to Reproduce:**
1. Upload a multiline file that requires effective field computation (e.g., multi-file with different types)
2. Complete configuration phase (effective fields computed at lines 641-651)
3. Run processing phase

**Expected Result:** Processing uses effective type and delimiter (ctx.prod.eff_type, ctx.prod.eff_delimiter).

**Actual Result:** Processing uses raw fields (`prod_type`, `prod_delim`) from discovery, ignoring the computed effective values. Multiline files processed with wrong delimiter.

**Affected Modules:** `dav_tool/ui/existing.py` (lines 790-811)

**Root Cause:** `_phase4_processing` constructs `ParseOptions` using raw `st.session_state["prod_type"]`, `st.session_state["prod_delim"]` instead of `ctx.prod.eff_type`, `ctx.prod.eff_delimiter` which were computed earlier.

**Evidence:**
- `existing.py:790-798`: `prod_type = st.session_state["prod_type"]`, `prod_delim = st.session_state.get("prod_delim", ...)` — raw
- `existing.py:759-762`: `ctx.prod.eff_type` and `ctx.prod.eff_delimiter` exist but unused in processing

**Reproducibility:** 100% for multiline files where effective fields differ from raw.

---

### B-HIGH-6: Column mapping re-selection duplicates config

**Severity:** High

**Steps to Reproduce:**
1. Map columns in Phase 2 Configuration (e.g., Store = "Store", Units = "Qty")
2. Advance to Phase 4 Processing
3. Observe column mapping UI

**Expected Result:** Phase 2 column mapping is reused; user only confirms or adjusts.

**Actual Result:** Phase 4 shows fresh `st.selectbox` widgets with no pre-selected values. User must re-map all columns from scratch. Values different from Phase 2 produce inconsistent results.

**Affected Modules:** `dav_tool/ui/existing.py` (lines 689-777), `dav_tool/ui/onboarding.py` (lines 419-424)

**Root Cause:** Processing phase UI does not read Phase 2 config values for initial widget states.

**Reproducibility:** 100%.

---

### B-HIGH-7: `_apply_implied_decimals` mutates caller's dict

**Severity:** High

**Steps to Reproduce:**
1. Run store aggregation (applies implied decimals to schema dict)
2. Run item aggregation with the same schema dict

**Expected Result:** Implied decimals applied once.

**Actual Result:** Schema dict already has decimal-adjusted values from step 1. Second application divides by 10 again, producing wrong results (e.g., 12.50 → 1.250 → 0.125).

**Affected Modules:** `dav_tool/workflow/processing.py` (lines 183-199)

**Root Cause:** `apply_implied_decimals` mutates the input `schema` dict in-place. If the same dict is passed to multiple aggregation calls, decimals are applied repeatedly.

**Evidence:**
- `processing.py:195-198`: `schema[mapping.units] = ...`, `schema[mapping.price] = ...` — direct mutation of input parameter

**Reproducibility:** 100% when same schema dict used across multiple aggregation calls.

---

### B-HIGH-8: Empty string `header_prefix` breaks preview

**Severity:** High

**Steps to Reproduce:**
1. Upload a multiline HDR file
2. Set `header_prefix = ""` (empty string — valid value meaning "no header prefix")
3. Request preview

**Expected Result:** Preview falls back to delimited multiline flattening.

**Actual Result:** `get_preview` returns `None` for the flattened preview. Falls through to `preview_raw` which doesn't understand multiline structure.

**Affected Modules:** `dav_tool/workflow/discovery.py` (lines 282-296)

**Root Cause:** `if header_prefix and header_layout and detail_layout:` — `""` is falsy, so multiline path is skipped. `elif header_prefix is None:` — `""` is not None, so multiline fallback is also skipped.

**Evidence:**
- `discovery.py:283`: `if header_prefix and header_layout and detail_layout:` — `""` evaluates to False
- `discovery.py:287`: `elif header_prefix is None:` — `""` is not None

**Reproducibility:** 100% when `header_prefix=""`.

---

### B-HIGH-9: `is_connected` opens SSH channel per call

**Severity:** High

**Steps to Reproduce:**
1. Connect via SSH
2. Poll `is_connected()` frequently (e.g., between UI interactions)

**Expected Result:** `is_connected` uses transport-level check (O(1)).

**Actual Result:** Every call opens a new SSH channel via `exec_command("echo connected")` (~200-500ms). Channels are never closed. After ~100 calls, SSH channel limit may be reached.

**Affected Modules:** `dav_tool/datasource/ssh.py` (lines 90-93)

**Root Cause:** Uses `exec_command` instead of `transport.is_active()`.

**Reproducibility:** 100% — every call to `is_connected()` while SSH is active.

---

### B-HIGH-10: `_detect_and_set` renders UI inside detection function

**Severity:** High

**Steps to Reproduce:**
1. Run detection in Format Change workflow

**Expected Result:** Detection logic is separate from UI rendering.

**Actual Result:** `_detect_and_set` (existing.py:1041-1097) renders `st.error`, `st.warning`, `st.success`, and `st.text_input` inline. Logic function has Streamlit UI dependency — cannot be tested without Streamlit runtime.

**Affected Modules:** `dav_tool/ui/existing.py` (lines 1041-1097)

**Root Cause:** Detection logic and UI rendering mixed in single function.

**Reproducibility:** 100%.

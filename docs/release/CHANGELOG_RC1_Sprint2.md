# CHANGELOG — DVA Platform RC1 Sprint 2

**Date:** 2026-07-15
**Sprint:** 2 — Production Blockers

---

## Fixed

### A3 — Join fill no longer corrupts key columns
- **Module:** `dav_tool/calculations/core.py`
- **Problem:** `full_join_with_coalesce` applied `fill_null(0.0)` to ALL columns including join key columns, corrupting string keys or causing type coercion.
- **Fix:** `fill_null` now applies only to non-key columns. Key columns in the `on` parameter are excluded.
- **Tests:** All 198 unit + 12 golden regression pass.

### A5 — Unmapped column roles no longer silently map to first column
- **Module:** `dav_tool/_column_utils.py`
- **Problem:** `find_best_column_index` returned `0` (a valid index) when no match was found, causing every unfound role to silently select the first column. `smart_column_indices` stored `(0, cols[0])` for unmatched roles.
- **Fix:** `find_best_column_index` now returns `-1` for no match. `smart_column_indices` stores `(None, None)` for unmatched roles. UI `st.selectbox` with `index=None` shows no pre-selection.

### A6 — Fast path now respects `start_line` and `record_type`
- **Module:** `dav_tool/_aggregators.py`
- **Problem:** Fast path condition only checked `file_type == "delimited"` and `can_use_fast_path`. Files with `start_line > 0` or non-None `record_type` used the streaming fast path incorrectly, misaligning data.
- **Fix:** Added `start_line == 0 and record_type is None` to fast-path guard in all three aggregation paths (store, item, upc).
- **Tests:** All 198 unit + 12 golden regression pass.

### A7 — `run_file_review` now passes `detail_layout`
- **Module:** `dav_tool/workflow/processing.py`
- **Problem:** `run_file_review` called `generate_file_review` without passing `detail_layout`, unlike `run_store_aggregation` which correctly passed it. Multiline HDR files produced incorrect file reviews.
- **Fix:** Added `detail_layout=parse_opts.detail_layout` to the `generate_file_review` call in `run_file_review`.
- **Tests:** All 198 unit + 12 golden regression pass.

### A2 — Column rename collision no longer crashes aggregation
- **Module:** `dav_tool/_normalizer.py`
- **Problem:** All three `normalize_*_chunk` functions used `.rename({col: "NAME"}).select(["NAME", other_col])`. When `col == other_col`, the rename consumed the column name before the select, causing `ColumnNotFoundError`.
- **Fix:** Replaced `rename().select()` with `select(pl.col(x).alias("NAME"), ...)` in all three normalize functions. Column names are preserved through alias, not destroyed by rename.
- **Tests:** All 198 unit + 12 golden regression pass.

### A1 — Config save/load no longer corrupts completion tracking
- **Module:** `dav_tool/format_config.py`
- **Problem:** `_completed_sections` (a `set`) was serialized via `json.dump(default=str)`, producing a garbage string. On reload, `set("garbage")` produced individual characters. Config save/load completely broke progressive completion tracking.
- **Fix:** `save_format_config` now converts `_completed_sections` to a list of section `.value` strings before JSON dump. `load_format_config` reconstructs the set via `ConfigSection(value)`. Removed `default=str` to prevent silent corruption of other fields.
- **Tests:** All 198 unit + 12 golden regression pass.

### A4 — Test file review no longer silently dropped
- **Module:** `dav_tool/workflow/validation.py`, `dav_tool/ui/existing.py`
- **Problem:** `_generate_both_file_reviews` returned `(fr_prod, fr_test, elapsed)`, but `run_existing_validation` only stored `result.file_review = fr_prod`. The test file review was computed and immediately discarded.
- **Fix:** Added `file_review_test` field to `ValidationResult`. `run_existing_validation` now stores `result.file_review_test = fr_test`. UI stores it to `ctx.fr_test` for display.
- **Tests:** All 198 unit + 12 golden regression pass.

### A9 — `is_connected` no longer opens SSH channel on every call
- **Module:** `dav_tool/datasource/ssh.py`
- **Problem:** `is_connected` called `exec_command("echo connected")` on every check, opening a new SSH channel (~200-500ms) that was never closed.
- **Fix:** Replaced with `transport.is_active()` — uses existing transport state.
- **Tests:** All 198 unit + 12 golden regression pass.

### A11 — Connection manager now thread-safe
- **Module:** `dav_tool/datasource/manager.py`
- **Problem:** Module-level globals `_ACTIVE_SOURCE` and `_ACTIVE_CONFIG` were modified without any locking, risking race conditions.
- **Fix:** Added `threading.RLock()` to protect all global state mutations in `connect_local()`, `connect_ssh()`, and `disconnect()`.
- **Tests:** All 198 unit + 12 golden regression pass.

### A8 — Remote encoding detection now decodes raw bytes
- **Module:** `dav_tool/config_builder.py`
- **Problem:** For remote sources, `_detect_encoding` called `sample.encode(enc)` on an already-decoded string, testing if the string is representable in `enc` rather than whether the original bytes decode as `enc`. Guaranteed wrong encoding for remote files.
- **Fix:** Remote path now reads raw bytes via `source.open_stream()` and tries `raw_bytes.decode(enc)`. Local path unchanged.
- **Tests:** All 198 unit + 12 golden regression pass.

### A10 — SSH temp file handle now properly closed
- **Module:** `dav_tool/datasource/ssh.py`
- **Problem:** `download_if_required` created `NamedTemporaryFile(delete=False)` without closing the handle. The open handle leaked until garbage collection. No cleanup on exception.
- **Fix:** `tmp.close()` called immediately after creation. Exception handler now also closes handle and deletes the temp file on failure.
- **Tests:** All 198 unit + 12 golden regression pass.

---

## Verification

| Test Suite | Result |
|------------|--------|
| Unit tests (198) | ✅ All passed |
| Golden regression (12) | ✅ All passed |
| `full_test.py` (comprehensive) | ✅ Exit 0 |

---

## Files Modified

| File | Changes |
|------|---------|
| `dav_tool/calculations/core.py` | A3: fill_null only non-key columns |
| `dav_tool/_column_utils.py` | A5: find_best_column_index returns -1 on no match |
| `dav_tool/_aggregators.py` | A6: fast-path guard for start_line/record_type |
| `dav_tool/workflow/processing.py` | A7: detail_layout to run_file_review |
| `dav_tool/_normalizer.py` | A2: rename collision → with_columns alias |
| `dav_tool/format_config.py` | A1: completed_sections serialized as list |
| `dav_tool/workflow/validation.py` | A4: file_review_test field + storage |
| `dav_tool/ui/existing.py` | A4: store file_review_test to ctx |
| `dav_tool/datasource/ssh.py` | A9: transport.is_active(); A10: close handle |
| `dav_tool/datasource/manager.py` | A11: threading.RLock() |
| `dav_tool/config_builder.py` | A8: decode raw bytes for remote encoding |

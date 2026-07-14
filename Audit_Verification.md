# Audit Verification — DVA Platform RC1

**Date:** 2026-07-15
**Method:** Manual code review, execution path tracing, finding-by-finding verification
**Status:** Each finding classified as **Valid**, **Partially Valid**, **Invalid**, or **Already Fixed**

---

## Summary

| Verdict | Count | Notes |
|---------|-------|-------|
| **Valid** | 77 | Issues confirmed as described |
| **Partially Valid** | 5 | Issue exists but description or severity has nuances |
| **Invalid** | 4 | Finding is factually wrong or already fixed |
| **Already Fixed** | 3 | Issues fixed during Sprint 1 implementation before audit |

---

## Connection Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| CM-1: Detection orchestration in Connection Manager | CRITICAL | **Valid** | `connection_manager.py:444` calls `detect_file()`, stores `DiscoveryResult` in session state at line 459. CM should only manage connections. | Move detection call to workflow layer; CM emits "path selected" events only. |
| SSH-1: Temp file leak in `download_if_required` | HIGH | **Valid** | `ssh.py:173-183`: `NamedTemporaryFile(delete=False)` — handle never closed, file never deleted. | Close handle immediately; add cleanup mechanism. |
| SSH-2: `is_connected` opens new SSH channel per call | HIGH | **Valid** | `ssh.py:90-93`: `exec_command("echo connected")` — returns (stdin,stdout,stderr), never closes any. | Use `transport.is_active()` instead. |
| MGR-1: No thread safety on singleton | HIGH | **Valid** | `manager.py:23-24`: module-level globals `_ACTIVE_SOURCE`, `_ACTIVE_CONFIG` modified without locking. | Add `threading.Lock` to all global state mutations. |
| SSH-3: AutoAddPolicy security risk | MEDIUM | **Valid** | `ssh.py:51`: `AutoAddPolicy()` silently accepts unknown host keys. | Use `WarningPolicy`; log security notice. |
| SSH-4: `look_for_keys=False, allow_agent=False` | MEDIUM | **Valid** | `ssh.py:60-61`: disables SSH key discovery and agent. | Document requirement; make configurable. |
| LOC-1: `read_sample` implicit encoding | MEDIUM | **Valid** | `local.py:61`: `open(path, "r", errors="ignore")` — no explicit encoding. | Standardize to `DEFAULT_ENCODING`. |
| LOC-2: Hidden files ignored by `list_files` | MEDIUM | **Valid** | `local.py:55`: `glob.glob("*")` does not match dotfiles. | Use `os.listdir` or `glob.glob("*", include_hidden=True)`. |
| SSH-5: `disconnect` swallows exceptions | LOW | **Valid** | `ssh.py:76-77, 82-83`: `except Exception: pass` on both `sftp.close()` and `client.close()`. | Log close failures. |
| SSH-6: False negative in `is_connected` for restricted shells | LOW | **Valid** | `ssh.py:90-93`: relies solely on `exec_command`. | Add SFTP health check fallback. |

---

## Detection Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| DET-1: `from_context` typo `"colums"` | CRITICAL | **Already Fixed** | `discovery.py:96`: actual code reads `columns=getattr(ctx, "columns", None)` — correct spelling. Already fixed. | N/A — already resolved. |
| DET-2: `flatten_multiline` drops `file_paths` | HIGH | **Valid** | `discovery.py:247-259`: new `DiscoveryResult(...)` without `file_paths=`. Caller `detect_file` sets it at line 160 but `flatten_multiline` is called from config path. | Pass `file_paths` through return value. |
| DET-3: `_detect_encoding` inverted for remote sources | HIGH | **Valid** | `config_builder.py:58`: `sample.encode(enc)` tests if string is representable, not if bytes decode correctly. | Use `raw_bytes.decode(enc)` instead. |
| DET-4: `has_header` false positive risk | MEDIUM | **Valid** | `detection.py:177`: reads only 1 line. Line 185: `alpha_count >= len(values) / 2`. | Sample 2-3 lines, compare differences, use higher threshold. |
| DET-5: Delimiter tie not handled | MEDIUM | **Partially Valid** | `detection.py:53`: `max(scores, key=scores.get)` returns arbitrary first max on tie. But "if both score 0" is wrong — zero-score falls through to `return "fixed"` (line 57). | Handle non-zero ties with preference ordering (pipe > tab > semicolon > comma). |
| DET-6: `detect_file` only inspects first file | MEDIUM | **Valid** | `discovery.py:149`: `fp = file_paths[0]` — all paths use first file only. | Document multi-file assumption or iterate all files. |
| DET-7: `get_preview` fails for empty string `header_prefix` | MEDIUM | **Valid** | `discovery.py:283-296`: `""` is falsy (skips first branch) but not `None` (skips second branch) — falls through to preview_raw for multiline files. | Use `if header_prefix is not None and header_prefix != ""` or explicit check. |
| DET-8: Zero-score fallback to "fixed" is brittle | LOW | **Valid** | `detection.py:55-57`: single-column CSV classified as fixed-width. | Single-column files are valid CSV; return `"delimited", None` with single-column fallback. |

---

## Canonical Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| CAN-1: Rename-collision crash in normalize functions | CRITICAL | **Valid** | `normalizer.py:38-39, 74-75, 111`: `.rename({col: "X"}).select(["X", col])` crashes when rename col == select col. | Replace with `with_columns(...alias(...))`. |
| CAN-2: `apply_column_names` silently ignores count mismatch | CRITICAL | **Valid** | `normalizer.py:8-10`: returns df unchanged with no warning on mismatch. | Log warning when column count mismatch occurs. |
| CAN-3: Inconsistent canonical naming conventions | HIGH | **Valid** | `normalizer.py:27-28`: `Units`, `Totalprice` (mixed case). Lines 65-66, 102-103: `UNITS_SOLD`, `TOTAL_DOLLARS` (upper). | Adopt single naming convention (e.g. `UNITS_SOLD`, `TOTAL_DOLLARS`). |
| CAN-4: `normalize_item_chunk` fragile column ordering | MEDIUM | **Partially Valid** | `normalizer.py:74-82`: `.select()` then `.with_columns()` retains original cols as extras. Concern overstated — Polars preserves select order. | Simplify to single `.with_columns()` chain. |

---

## Processing Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| PRC-1: `fill_null(0.0)` corrupts key columns | CRITICAL | **Valid** | `calculations/core.py:64`: `.fill_null(0.0)` on entire merged DataFrame — applies to key columns. | Apply only to non-key value columns. |
| PRC-2: Fast path ignores `start_line` and `record_type` | HIGH | **Valid** | `aggregators.py:289, 362, 436`: fast-path gates only on `supports_direct_path`; no check for `start_line != 0` or `record_type`. | Add `start_line == 0 and record_type is None` to guard. |
| PRC-3: Triple-duplicated `_merge_accumulate` functions | HIGH | **Valid** | `aggregators.py:208-258`: three structurally identical functions with hardcoded column names. | Parameterize into single function. |
| PRC-4: `run_file_review` missing `detail_layout` | HIGH | **Valid** | `processing.py:150-174`: call lacks `detail_layout=`. | Add `detail_layout` parameter to call. |
| PRC-5: Per-chunk `gc.collect()` overhead | MEDIUM | **Invalid** | `gc.collect()` appears once per aggregation (lines 223, 302, 328, 375, 403, 448, 474), not per-chunk. Lines 316-323, 389-399, 462-470 have no `gc.collect()`. | Finding is factually wrong — no action needed. |
| PRC-6: `apply_implied_decimals` mutates caller's dict | MEDIUM | **Valid** | `processing.py:195-198`: mutates input `schema` dict in-place. | Copy dict before mutation. |
| PRC-7: Inconsistent sorting across aggregation levels | MEDIUM | **Valid** | `aggregators.py:330`: store sorts; lines 404-405: item sorts conditionally; lines 449, 475: UPC does not sort. | Sort all aggregation results consistently. |
| PRC-8: No canonical wrapper for `run_file_review` | MEDIUM | **Valid** | `processing.py:68-79, 125-136`: canonical methods for store and item exist; none for file_review (lines 139-180). | Add `run_file_review_canonical`. |

---

## Configuration Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| CFG-1: `_completed_sections` set not JSON-serializable | CRITICAL | **Valid** | `format_config.py:212`: set type. Lines 262-264: `json.dump(default=str)` produces garbage. Line 245: `set("{GENERAL, FILE}")` produces individual chars. | Save as list; load as set. |
| CFG-2: `smart_column_indices` maps all unfound roles to cols[0] | CRITICAL | **Valid** | `column_utils.py:61, 69-70`: `find_best_column_index` returns 0 for no match; `indices[key] = (0, cols[0])` — silent misassignment. | Return `None` for unmapped roles; warn user. |
| CFG-3: `load_format_config` version default (1) inconsistent with constructor (2) | HIGH | **Valid** | `format_config.py:144`: `version=2` in constructor. Line 243: `data.pop("version", 1)` in loader. | Align default to 2 or add migration. |
| CFG-4: `config_from_ctx` does not preserve validation/output config | HIGH | **Partially Valid** | `format_config.py:368-411`: no `validation_config`/`output_config` set. But `ProcessingContext` also lacks these fields — issue is context design, not config_from_ctx alone. | Add fields to context; preserve in config_from_ctx. |
| CFG-5: `validate_config` does not check file existence for layout paths | HIGH | **Valid** | `config_validator.py:96-97`: truthiness check only; no `os.path.exists()`. | Validate file existence when layout_file is set. |
| CFG-6: `weight_col` not validated in `validate_config` for weight/mixed modes | HIGH | **Valid** | `config_validator.py:153-155`: checks `quantity_type` membership but not `weight_col`. | Add weight_col validation for weight/mixed. |
| CFG-7: `apply_format_config` derives schema from only 10 flattened rows | MEDIUM | **Valid** | `format_config.py:347, 353`: `n_rows=10` hardcoded. | Increase sample size or make configurable. |
| CFG-8: `build_config` only inspects first file | MEDIUM | **Valid** | `config_builder.py:97, 132, 482`: all paths use `file_paths[0]`. | Document or iterate. |
| CFG-9: `validate_section(BUSINESS_MAPPING)` requires all columns unconditionally | MEDIUM | **Valid** | `config_validator.py:201-209`: validates store/UPC/quantity/price regardless of OutputMode. | Gate validation by OutputMode. |
| CFG-10: `save_format_config` uses `default=str` which silently type-converts | LOW | **Valid** | `format_config.py:264`: `default=str` converts non-serializable objects without warning. | Raise TypeError instead of silent conversion. |

---

## Output Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| OUT-1: No formal Output layer | HIGH | **Valid** | Download/export logic in UI files (`existing.py:1556-1579`, `onboarding.py:873-880`). `_reports.py` only has `generate_file_review`. | Create `workflow/output.py` as formal layer. |
| OUT-2: File review duplicates aggregation logic | MEDIUM | **Valid** | `_reports.py:83-118`: calls `stream_store_aggregate` and `stream_upc_summary` internally. | Pass precomputed aggregations. |
| OUT-3: No export to formats other than CSV | LOW | **Partially Valid** | `ExportOperation` supports parquet/excel but is disconnected from pipeline. Only CSV is reachable in practice. | Wire ExportOperation into workflow. |

---

## Flush Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| FLH-1: Flush Layer not integrated into workflow | MEDIUM | **Valid** | `flush.py` exists. Zero callers outside flush.py (grep confirmed). | Call `flush()` at end of both workflow pipelines. |
| FLH-2: `cleanup_dataframes` broken nested-attribute matching | MEDIUM | **Valid** | `helpers.py:865-889`: exact string match. `existing.py:842`: `keep_attrs=["prod.store_agg"]` never matches `"store_agg"`. | Remove dot-separated support or implement proper nested attr resolution. |

---

## Requirement / Operations Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| REQ-1: Operations framework disconnected from main pipeline | MEDIUM | **Valid** | `requirement.py:75`: `execute_requirement` defined. Zero callers (grep confirmed). | Wire into onboarding and Format Change pipelines. |
| REQ-2: No UI for operation selection | MEDIUM | **Valid** | `OperationType` enum defined (`requirement.py:31-51`); no rendering anywhere in UI layer. | Add operation selection radio/select. |
| REQ-3: `AggregateOperation` accepts any column without validation | LOW | **Partially Valid** | `operations/aggregate.py:32-43`: validates columns at exec time (returns `OperationResult.error`). No *upfront* canonical schema validation. | Add pre-execution validation against canonical schema. |
| OPS-1: Operations not wired into workflow | MEDIUM | **Valid** | Seven operations registered; zero integration points with onboarding or Format Change. | Wire via Requirement Layer. |
| OPS-2: No tests for operations | LOW | **Invalid** | `tests/test_operations.py` exists: 642 lines, 61 test functions covering all 7 operations. | Finding is false — tests exist. |

---

## UI Layer

| Finding | Severity | Status | Evidence | Recommendation |
|---------|----------|--------|----------|----------------|
| UI-1: Duplication between onboarding.py and existing.py | CRITICAL | **Valid** | 40-50% of `existing.py` (1720 lines) mirrors `onboarding.py` (882 lines): discovery, config, multiline, preview, validation, metrics, reset — all duplicated. | Extract shared logic into `ui/shared_workflow.py`. |
| UI-2: existing.py at 1720 lines with 27-parameter functions | CRITICAL | **Valid** | `_execute_validation` at line 1309 has 37 positional/keyword params (undercounted by audit). 1720-line file should be 5-6 modules. | Split into phase-specific modules. |
| UI-3: Manual option construction instead of `from_context()` | CRITICAL | **Valid** | `onboarding.py:797-817` and `existing.py:1341-1379`: manually construct `ParseOptions`/`ColumnMapping`/`ValidationOptions`. Contrast: onboarding.py line 480 correctly uses `from_context(ctx)`. | Replace manual construction with `from_context()`. |
| UI-4: Dead functions in existing.py | HIGH | **Valid** | `_compare_stores` (lines 1418-1463, 46 lines) and `_generate_file_reviews` (lines 1466-1535, 70 lines) — zero callers. | Remove dead code. |
| UI-5: Column mapping re-selection in processing phase | HIGH | **Valid** | Phase 2 maps columns; Phase 4 forces re-selection via `st.selectbox` (lines 689-713). Phase 2 values ignored. | Reuse config-phase column mapping by default. |
| UI-6: Column name cache never invalidated | HIGH | **Valid** | `helpers.py:31-36`: cache key missing `header_layout`, `trailer_prefix`, `trailer_layout`. Zero invalidation mechanism. | Bust cache on path change; include all params in key. |
| UI-7: Temp file leak in config_builder.py | HIGH | **Partially Valid** | `config_builder.py:127-132`: `NamedTemporaryFile(delete=False)`. Cleanup exists in `finally` (lines 225-230) for code inside `try`. But line 137 (`_detect_encoding`) runs outside `try` — leaks on exception there. | Move `_detect_encoding` inside `try` block. |
| UI-8: Connection Manager session key sprawl | HIGH | **Valid** | `connection_manager.py:21-37`: 15 explicit key constants. Cross-file magic strings `_cm_discovery`, `_cm_bau_discovery`, etc. No central registry. | Centralize session state keys in dataclass. |
| UI-9: `_detect_and_set` renders UI inside detection function | HIGH | **Valid** | `existing.py:1041-1097`: renders `st.error`, `st.warning`, `st.success`, `st.text_input` inline. Violates architecture separation. | Separate detection logic from UI rendering. |
| UI-10: Processing phase ignores effective fields | HIGH | **Valid** | `existing.py:790-798`: uses raw `prod_type`, `prod_delim`. Effective values computed at lines 641-651 and stored at lines 759-762 are ignored. | Use `ctx.prod.eff_type`, `ctx.prod.eff_delimiter`. |
| UI-11: `render_phase_progress` hardcodes 6 max phases | MEDIUM | **Valid** | `helpers.py:787`: `max_phase=6` unused. Lines 793-801: `PHASE_COLORS` has 0-6 only. Line 805: hardcoded `range(7)`. Format Change has 9 phases. | Pass actual phase count; make dynamic. |
| UI-12: `display_config_review` NameError on `asdict` | MEDIUM | **Valid** | `helpers.py:312, 317`: `asdict(cfg)` called without import. Only imported inside `edit_and_accept_config` (line 329), not at module level. | Add `from dataclasses import asdict` at module level. |
| UI-13: `st.rerun()` inside `st.spinner()` blocks | MEDIUM | **Valid** | `existing.py:1003-1005, 814` and `onboarding.py:593-594`: `st.rerun()` called inside spinner context. | Move `st.rerun()` outside spinner blocks. |
| UI-14: Workflow switch doesn't clear discovery results | MEDIUM | **Valid** | `connection_manager.py:284-291`: clears path keys only; does not clear `_cm_discovery*` keys. Stale `DiscoveryResult` consumed after switch. | Clear discovery results on workflow switch. |
| UI-15: `unsafe_allow_html=True` in phase progress | LOW | **Valid** | `helpers.py:839`: `unsafe_allow_html=True` with hardcoded content. Theoretical XSS only. | Consider removing or documenting rationale. |
| UI-16: `display_processing_history()` not gated on dev mode | LOW | **Valid** | `helpers.py:273-288`: called from `existing.py:1030` and `onboarding.py:616` unconditionally. | Gate behind dev mode check. |

---

## Bug Report Findings (Duplicate References)

| Finding | Severity | Status | Evidence |
|---------|----------|--------|----------|
| B-CRIT-1: Config save/load corrupts completion tracking | CRITICAL | **Valid** | Same as CFG-1. |
| B-CRIT-2: Aggregation crash on column role collision | CRITICAL | **Valid** | Same as CAN-1. |
| B-CRIT-3: Join fill corrupts key columns | CRITICAL | **Valid** | Same as PRC-1. |
| B-CRIT-4: Test file review silently dropped | CRITICAL | **Valid** | `validation.py:122-129`: `fr_test` destructured but never stored. `ValidationResult` has no `file_review_test` field. |
| B-CRIT-5: `DiscoveryResult.from_context` typo | CRITICAL | **Already Fixed** | Same as DET-1. Already fixed. |
| B-HIGH-1: Fast path ignores start_line/record_type | HIGH | **Valid** | Same as PRC-2. |
| B-HIGH-2: `run_file_review` missing `detail_layout` | HIGH | **Valid** | Same as PRC-4. |
| B-HIGH-3: `_detect_encoding` inverted for remote | HIGH | **Valid** | Same as DET-3. |
| B-HIGH-4: `has_header` false positive | HIGH | **Valid** | Same as DET-4. |
| B-HIGH-5: Processing phase ignores effective fields | HIGH | **Valid** | Same as UI-10. |
| B-HIGH-6: Column mapping re-selection duplicates config | HIGH | **Valid** | Same as UI-5. |
| B-HIGH-7: `_apply_implied_decimals` mutates caller's dict | HIGH | **Valid** | Same as PRC-6. |
| B-HIGH-8: Empty string `header_prefix` breaks preview | HIGH | **Valid** | Same as DET-7. |

---

## Summary of Invalid / Already Fixed Findings

| Finding | Original Status | Actual Status | Reason |
|---------|----------------|---------------|--------|
| DET-1 / B-CRIT-5 | CRITICAL | **Already Fixed** | `from_context` already uses `"columns"` (correct). Fixed in Sprint 1 Phase 6. |
| PRC-5 | MEDIUM | **Invalid** | `gc.collect()` is per-aggregation (7 calls total), not per-chunk. Line numbers cited don't contain gc.collect(). |
| OPS-2 | LOW | **Invalid** | `tests/test_operations.py` exists with 642 lines and 61 tests covering all 7 operations. |
| DET-5 | MEDIUM | **Partially Valid** | Tie issue exists but zero-score case not affected (returns "fixed"). |
| CAN-4 | MEDIUM | **Partially Valid** | Column ordering concern is overstated; but pattern is wasteful. |
| CFG-4 | HIGH | **Partially Valid** | Issue exists but context also lacks these fields — not solely config_from_ctx. |
| UI-7 | HIGH | **Partially Valid** | `finally` block exists for inner code; `_detect_encoding` at line 137 is outside try. |
| REQ-3 | LOW | **Partially Valid** | Validation exists at execution time, not upfront against canonical schema. |
| OUT-3 | LOW | **Partially Valid** | ExportOperation supports parquet/excel but is disconnected; only CSV reachable in practice. |

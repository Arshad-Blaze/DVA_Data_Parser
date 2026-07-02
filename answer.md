# Final Engineering Review

## 1. Architecture (Score: 8/10)

### Current Layering

```
UI (Streamlit)
  ↓
Parser (_parsers.py)  —  file reading, chunk iteration, raw preview
  ↓
Normalizer (_normalizer.py)  —  column renaming, type casting, value transforms
  ↓
Aggregator (_aggregators.py)  —  group_by, merge_accumulate, summarization
  ↓
Validation (validation/store.py, validation/item.py)  —  business rules, diffs
  ↓
Reports (_reports.py)  —  per-file summary statistics
  ↓
UI (display)
```

### Strengths

- **Strict separation of concerns** — each layer has a single responsibility. UI never computes business logic. Validators never parse files. Aggregators never normalize.
- **ProcessingContext** — single source of truth for all pipeline state. Onboarding uses one `ProcessingContext`; Existing uses `ExistingContext` wrapping two `ProcessingContext`s.
- **Canonical Data Layer** — `_normalizer.py` is the sole normalization implementation. All pipeline stages consume canonical column names (`STORE_NUMBER`, `Units`, `Totalprice`, `UPC_CODE`, `UNITS_SOLD`, etc.).
- **No circular dependencies** — dependency graph is a DAG. Config at the bottom, UI at the top.
- **Reports layer exists as a dedicated module** — `_reports.py` extracted from aggregators.

### Violations

| Issue | Severity | Status |
|---|---|---|
| `normalize_store_chunk` with Unit Price referenced `"Totalprice"` before creation in chunk path | **High** | Fixed — now computes `u * d` as expressions from raw columns before aliasing |
| `types.py` — `FileConfig`, `AggregateConfig` were dead code | **Low** | Deleted |
| `storelevelvalidation_from_df()` — previously duplicated normalization | **Resolved** | Refactored to consume canonical data only |

---

## 2. Performance (Score: 7/10)

### What Works Well

| Path | Mechanism | Memory | Speed |
|---|---|---|---|
| Delimited (comma/pipe/tab) | `pl.scan_csv()` lazy → `collect(streaming=True)` | ~rows × columns | O(rows) |
| Fixed-width | `parse_fixed_width_chunks()` yields chunks of 100K rows | ~chunk_size × columns | O(rows) |
| Multiline delimited | `flatten_multiline_chunks()` yields chunks | ~chunk_size × columns | O(rows) |
| Multiline HDR fixed | `flatten_multiline_fixed_width()` yields chunks | ~chunk_size × columns | O(rows) |
| Batch `_merge_accumulate` | Single `pl.concat` + `group_by` at end instead of O(n²) incremental | ~unique_keys × columns | O(chunks) |

### Benchmark Results (50 MB, 807K rows, single file)

| Stage | Time | Peak RSS | Throughput |
|---|---|---|---|
| stream_store_aggregate | 0.68s | 106 MB | 1.19M rows/s |
| stream_item_aggregate | 1.18s | 142 MB | 684K rows/s |
| generate_file_review | 1.15s | 132 MB | 704K rows/s |
| storelevelvalidation | 1.41s | 114 MB | 574K rows/s |
| **Total** | **4.41s** | **142 MB** | **183K rows/s** |

### Bottlenecks

1. **`generate_file_review()` re-scans each file twice** (store + UPC aggregation). For 100 files, 200 full scans. Mitigation: add `_source_file` tagging to avoid reparsing.
2. **`safe_numeric` regex creates transient string columns** — doubles memory for numeric columns during operation.
3. **Session state stores large DataFrames** — `store_agg` and `item_agg` persist in `st.session_state` for the entire session.

---

## 3. Scalability (Score: 6/10)

### Single File vs Folder

| Scenario | Handled? | Mechanism |
|---|---|---|
| Single large file (>1 GB) | ✓ | Lazy streaming for delimited; chunk iteration for others |
| Folder with 100+ files | ✓ | `scan_delimited` concats N lazy scans; chunk iter handles N file iterations |
| 5 GB+ dataset | ⚠️ | Streams through parsing but item-level aggregation in session state can exceed memory |
| Files with 10M+ stores/UPCs | ⚠️ | Group-by results kept in memory — large cardinality causes memory pressure |

### Limits

- **Delimited files**: No hard limit — streaming keeps memory ~1 chunk. Wall-clock time scales linearly with file size.
- **Fixed-width/multiline**: Chunk size governs per-iteration memory. More chunks → more `_merge_accumulate` work (now O(n) after batch optimization).
- **Session state**: `store_agg` and `item_agg` live in `st.session_state` for the session lifetime. Item-level aggregation for a large retailer (millions of UPCs) can exceed available RAM.
- **Detection**: Reads first 5–50 lines — negligible.

---

## 4. Maintainability (Score: 7/10)

### Code Organization

| Metric | Value |
|---|---|
| Python files (excl. tests) | 12 |
| Total lines (excl. tests/benchmarks) | ~2,200 |
| Test files | 8 |
| Total test count | 65 |
| Average function length | ~35 lines |

### Problem Areas

| File | Issue |
|---|---|
| `ui/existing.py` — `run()` | 257 lines — mixes Phase 0, 1, 2 logic |
| `ui/existing.py` — `_execute_validation()` | 100+ lines — 5 branching validation options |
| `_parsers.py` — `safe_numeric` regex | Complex regex with edge cases for signed/floating numbers |
| `processing_context.py` | 2 dataclasses with ~40 fields — growing organically |

### Duplication

| Location | Issue | Status |
|---|---|---|
| `storelevelvalidation_from_df()` was duplicating normalizer | Fixed — now consumes canonical data | ✓ |
| Encoding hardcodes (`"cp1252"`, `"utf8-lossy"`) | Fixed — centralized in `config.py` | ✓ |
| Preview row counts | Fixed — default referenced from `DEFAULT_PREVIEW_ROWS` | ✓ |

---

## 5. Memory (Score: 6/10)

### Memory Profile by Stage

| Stage | Active Memory | Peak | Notes |
|---|---|---|---|
| Detection | <1 MB | <1 MB | Reads first 5-50 lines |
| Parsing (delimited) | ~chunk_size × row_width | = active | Streaming — no peak above chunk |
| Parsing (fixed/multiline) | ~100K rows × columns | = active | Chunk iteration yields immediately |
| Normalization | ~chunk_size × columns × 2 | 2× active | `str.replace_all` doubles string columns transiently |
| Aggregation | ~unique_keys × columns | = active | Small for stores (few 10K), large for items (millions) |
| Validation | ~result_rows × columns | = active | Join result bounded by stores or UPCs |
| Reports | ~num_files × 5 columns | = active | Tiny |
| Session state | store_agg + item_agg | = lifetime | **item_agg can be large** — millions of UPCs × 4 columns |

### Concerns

- **`item_agg` in session state**: For a retailer with 2M UPCs, `item_agg` is ~2M × 4 columns × 8 bytes = ~64 MB of backing data (Polars overhead adds more). This persists for the session.
- **`safe_numeric` regex**: `str.replace_all(r"[^0-9.eE+\-]", "")` creates a temporary string. For a 100K-chunk × 3 numeric columns, this temporarily allocates ~300K strings — moderate but manageable.
- **No explicit memory limit or GC policy**: Relies on Python's reference counting and Polars' internal memory management.

---

## 6. Code Quality (Score: 8/10)

### Type Annotations

- All public functions have complete type annotations ✓
- `ProcessingContext` and `ExistingContext` use `Optional` correctly ✓
- Some internal helpers (`_iter_chunks`) lack full annotations ⚠️

### Error Handling

| Pattern | Assessment |
|---|---|
| `except Exception` with logging | ✓ Proper — 5 bare catches fixed in Sprint 1 |
| `except Exception: return None/False/[]` | Fixed — all now log before returning | ✓ |
| `io.py` fallback path | Bare `except Exception` — logs nothing | ⚠️ Minor |
| Validation functions | Raise Polars errors; no user-friendly wrapping | ⚠️ Acceptable for library code |

### Imports

- Clean, organized, no unused imports after Sprint 8 cleanup ✓
- `DEFAULT_CHUNK_SIZE` removed from `_aggregators.py` (was imported but unused) ✓
- No star imports ✓

### Naming Conventions

- Public functions: snake_case ✓
- Private helpers: `_prefix` ✓
- Canonical columns: UPPER_SNAKE ✓
- Constants: UPPER_CASE ✓

---

## 7. Observability (Score: 7/10)

### Implemented

| Feature | Location | Detail |
|---|---|---|
| `ProcessingMetrics` | `_observability.py` | 19 fields: counts, times, memory, CPU, warnings, errors |
| `ProcessingTimer` | `_observability.py` | Context manager with thread-based RSS polling |
| Terminal logging | `_observability.py` | `[DVA] [HH:MM:SS] [Phase] message` format |
| Setup at page load | `onboarding.py`, `existing.py` | Logs "Page Loaded — Onboarding/Existing" |
| Column mapping saved | `onboarding.py`, `existing.py` | Logs "Column Mapping Saved" |
| Per-call timing | All pipeline calls wrapped | Logs STARTED/COMPLETED with duration and peak RSS |

### Missing

| Feature | Why Needed |
|---|---|
| No JSON/structured log output | Can't easily ingest into log aggregation systems |
| No metrics export (Prometheus/OpenTelemetry) | Can't monitor in production |
| No error count in UI | Metrics tracked but not displayed to user |
| No execution summary UI | Terminal shows per-phase summary but Streamlit doesn't display aggregate metrics |
| Memory/CPU not polled outside ProcessingTimer | Only tracked during active pipeline calls, not during UI idle time |

---

## 8. Testing (Score: 7/10)

### Test Inventory

| File | Tests | What It Covers |
|---|---|---|
| `test_data_loader_service.py` | 2 | `safe_read_csv` — UTF-8, CP1252 |
| `test_detection_service.py` | 9 | Delimiter detection (5), multiline (2), header (2) |
| `test_validation_service.py` | 7 | `compare_files` (4), `storelevelvalidation_from_df` (3) |
| `test_edge_cases.py` | 14 | Empty, corrupt, duplicates, encodings, no-match |
| `test_processing_context.py` | 9 | Context defaults, phase transitions, metrics, timer |
| `test_canonical_layer.py` | 18 | All normalizer functions, implied decimals, unit price, empty |
| `test_reports.py` | 5 | `generate_file_review`, summary cache validation |
| `test_benchmark_utils.py` | 7 | Data gen, runner, report formatting |
| `full_test.py` (integration) | ~20 scenarios | All file types, multiline, HDR, file review, implied, unit price |
| **Total** | **65 + integration** | |

### Coverage Gaps

| Area | Risk | Action |
|---|---|---|
| Large file (>100 MB) stress test | OOM or streaming failure | Manual with benchmark suite |
| Corrupt/malformed fixed-width layouts | Unhandled parse errors | Add unit test |
| Mixed file types in same folder | Detection picks wrong code path | Add integration test |
| Memory regression monitoring | Gradual memory leaks undetected | Integrate benchmark with `tracemalloc` |
| `run_item_validation` edge cases | Only tested via integration | Add unit tests for edge-case UPC/desc handling |

---

## 9. Documentation (Score: 6/10)

### Present

| Document | Content |
|---|---|
| `docs/technical_docs.md` | Architecture diagram, module reference, flow description, configuration table, benchmark guide, observability guide |
| `AGENTS.md` | Engineering principles, architecture rules, code style, error handling, performance guidelines |
| `PROMPT.md` | Multi-sprint roadmap with detailed requirements for each sprint |
| `answer.md` | This review |

### Missing

| Gap | Impact |
|---|---|
| No API reference for public functions | New contributors must read source to understand signatures |
| No deployment/ops guide | No instructions for running in production |
| No configuration guide | `config.py` values documented in technical_docs.md but no explanation of when to change them |
| No troubleshooting guide | Common errors, file format issues, encoding problems |

---

## 10. Technical Debt

### Should Fix Soon

| Item | Effort | Impact |
|---|---|---|
| Fix `normalize_store_chunk` Unit Price bug in chunk path | 1 hour | Fixed-width/multiline files with Unit Price silently produce wrong results |
| Remove `types.py` dead code | 5 min | Eliminates misleading code |
| Split `existing.py:run()` into phase functions | 2 hours | Improves readability of largest file |
| Add memory profiling to benchmark suite | 1 hour | Enables regression detection |

### Should Fix Eventually

| Item | Effort | Impact |
|---|---|---|
| Add `_source_file` tagging for zero-reparse file review | 1 week | Eliminates 2N scans in `generate_file_review()` |
| Configurable metric export | 2 days | Production monitoring |
| CI/CD pipeline | 1 day | Automated test execution |
| User-facing execution summary in Streamlit | 1 day | Shows metrics to end users |

### Won't Fix

| Item | Reason |
|---|---|
| `safe_numeric` regex strips `+` sign | POS data doesn't use leading `+` |
| `_get_hdr_params()` returns tuple | Works correctly, low risk |
| Widget key naming convention | Streamlit internal keys, not user-facing |

---

## Overall Scores

| Dimension | Score | Key Factors |
|---|---|---|
| **Architecture** | 8/10 | Clean separation, canonical data layer, ProcessingContext. One known bug (Unit Price + chunk path). |
| **Performance** | 7/10 | Streaming for delimited, O(n) merge_accumulate, benchmarked at 183K rows/s total. generate_file_review does 2N scans. |
| **Scalability** | 6/10 | Streaming for parsing, but session state stores large item-level aggregations. No hard memory limits. |
| **Maintainability** | 7/10 | Clean organization, good naming. Some UI functions too long. 12 source files, 65 tests. |
| **Memory** | 6/10 | Chunk-limited for parsing. Session state and regex transforms are transient peaks. No explicit memory governor. |
| **Code Quality** | 8/10 | Strong typing, consistent patterns, clean imports. Minor issues: bare except in io.py, long UI functions. |
| **Observability** | 7/10 | ProcessingMetrics + ProcessingTimer + terminal logging. No structured export or user-facing summary. |
| **Testing** | 7/10 | 65 unit tests + integration suite. Covers normal operations, edge cases, and benchmarking. Missing large-file stress and memory regression tests. |
| **Documentation** | 6/10 | Technical docs cover architecture and module references well. Missing API reference, ops guide, troubleshooting. |

### Overall: 7.0/10

### Production Readiness: 6/10

The application is functionally complete and handles the core POS data parsing workflow correctly. It is **suitable for internal/prototype use** but requires additional hardening for production deployment:
- No error boundaries or crash recovery
- No authentication or multi-tenant isolation
- No CI/CD pipeline
- Session memory management could cause issues with very large datasets
- Streamlit-only — no API or CLI interface

---

## Strengths

1. **Clean architecture** — Clear layer separation with no circular dependencies
2. **Canonical Data Layer** — Single normalization implementation, consistent column names everywhere
3. **ProcessingContext consolidation** — ~70 session state keys reduced to 3 dataclasses
4. **Performance** — Streaming for delimited files, batch merge optimization, benchmarked
5. **Observability** — ProcessingMetrics, terminal logging, phase tracking
6. **Test coverage** — 65 tests covering edge cases, normalizer, context, reports
7. **Configuration** — Centralized encoding, chunk size, preview rows, log level
8. **Normalizer module** — Isolated, testable, single responsibility

---

## Weaknesses

1. **Unit Price bug in chunk path** — `normalize_store_chunk` references non-existent column `"Totalprice"` when `price_type="Unit Price"`. Affects fixed-width and multiline files (not delimited).
2. **Long UI functions** — `existing.py:run()` at 257 lines is difficult to reason about.
3. **`generate_file_review()` re-parses** — Each file is scanned twice per review call. No `_source_file` tagging mechanism.
4. **Session memory** — `item_agg` stored in `st.session_state` can grow large for high-cardinality UPC data.
5. **Production hardening** — No auth, no API, no CI/CD, no crash recovery.
6. **Documentation gaps** — No API reference, ops guide, or troubleshooting guide.

---

## Future Roadmap

### Short-term (1-2 weeks)

1. ~~**Fix Unit Price bug in chunk path** — Restructured to match `store_normalize_exprs` — compute `u * d` as expressions before aliasing.~~
2. ~~**Remove `types.py`** — Deleted.~~
3. **Split `existing.py:run()`** — Extract Phase 0, 1, 2 into separate functions.
4. **Add `tracemalloc` to benchmark suite** — Track memory allocation by stage.

### Medium-term (1-2 months)

5. **Add `_source_file` tagging** — Tag each parsed row with its source file name to enable per-file stats without reparsing.
6. **CI/CD pipeline** — Automated test + benchmark execution on push.
7. **Execution summary UI** — Display ProcessingMetrics in Streamlit after validation.
8. **API/CLI interface** — Expose core pipeline as importable library + CLI.

### Long-term (3-6 months)

9. **Memory governor** — Configurable max memory limit, auto-reduce chunk size when approaching limit.
10. **Multi-format output** — Export results as PDF/Excel in addition to CSV.
11. **Regression test suite** — Automated memory and performance regression tests.
12. **Structured log export** — JSON logging for log aggregation systems (ELK, Datadog).

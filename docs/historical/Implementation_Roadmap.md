# Implementation Roadmap — DVA Platform RC1

**Date:** 2026-07-15
**Basis:** Verified audit findings (Audit_Verification.md) and bug reports (Bug_Reproduction.md)
**Note:** All estimates in person-days. "Already Fixed" and "Invalid" findings excluded.

---

## Sprint A — Production Blockers (Week 1)

**Goal:** Fix all critical bugs that prevent reliable production use.

| # | Task | Findings | Est. | Risk | Dependencies |
|---|------|----------|------|------|-------------|
| A1 | Fix `_completed_sections` serialization: save as `list`, load as `set` | CFG-1, B-CRIT-1 | 0.5d | Low | None |
| A2 | Replace `rename().select()` with `with_columns(...alias(...))` in all 3 normalize functions | CAN-1, B-CRIT-2 | 1d | Medium | Golden tests must validate output |
| A3 | Apply `fill_null(0.0)` only to non-key value columns in `full_join_with_coalesce` | PRC-1, B-CRIT-3 | 0.5d | Medium | Validation tests |
| A4 | Add `file_review_test` field to `ValidationResult`; store both reviews | B-CRIT-4 | 0.5d | Low | None |
| A5 | Return `None` for unmapped column roles in `smart_column_indices`; warn user in UI | CFG-2 | 0.5d | Low | None |
| A6 | Add `start_line == 0 and record_type is None` to fast-path guard | PRC-2, B-HIGH-1 | 0.5d | Medium | Aggregation tests |
| A7 | Add `detail_layout` to `run_file_review` call | PRC-4, B-HIGH-2 | 0.5d | Low | Report tests |
| A8 | Fix `_detect_encoding` to decode raw bytes for remote sources | DET-3, B-HIGH-3 | 1d | High | SSH E2E tests |
| A9 | Replace `exec_command("echo connected")` with `transport.is_active()` | SSH-2, B-HIGH-9 | 0.5d | Medium | SSH module |
| A10 | Close temp file handle in SSH `download_if_required`; add cleanup | SSH-1 | 0.5d | Low | None |
| A11 | Add `threading.Lock` to connection manager globals | MGR-1 | 0.5d | Low | None |

**Sprint A subtotal:** ~6.5 days

**P0 (must-do pre-RC1):** A1, A2, A3, A4, A5, A6, A7 — ~3.5 days
**P1 (should-do pre-RC1):** A8, A9, A10, A11 — ~3 days

---

## Sprint B — Workflow Stabilization (Week 2)

**Goal:** Eliminate data corruption paths, fix user-facing workflow issues, integrate missing layers.

| # | Task | Findings | Est. | Risk | Dependencies |
|---|------|----------|------|------|-------------|
| B1 | Use effective fields (`eff_type`, `eff_delimiter`) in processing phase | UI-10, B-HIGH-5 | 0.5d | Low | None |
| B2 | Reuse config-phase column mapping in processing phase by default | UI-5, B-HIGH-6 | 1d | Low | None |
| B3 | Fix `has_header` with multi-line sampling (2-3 lines) and higher threshold | DET-4, B-HIGH-4 | 1d | Medium | Detection tests |
| B4 | Fix `apply_implied_decimals` to copy dict before mutation | PRC-6, B-HIGH-7 | 0.5d | Low | None |
| B5 | Fix `get_preview` empty `header_prefix` handling | DET-7, B-HIGH-8 | 0.5d | Low | None |
| B6 | Fix `_detect_and_set` — separate detection logic from UI rendering | UI-9, B-HIGH-10 | 2d | Medium | Existing.py refactor |
| B7 | Fix `flatten_multiline` to propagate `file_paths` | DET-2 | 0.5d | Low | None |
| B8 | Fix `has_header` null-merge empty string handling | DET-7 | 0.5d | Low | None |
| B9 | Cache-bust column name cache on path change; include all params in key | UI-6 | 0.5d | Low | None |
| B10 | Fix `display_config_review` `asdict` NameError | UI-12 | 0.5d | Low | None |
| B11 | Move `st.rerun()` outside `st.spinner()` blocks | UI-13 | 0.5d | Low | None |
| B12 | Clear discovery results on workflow switch | UI-14 | 0.5d | Low | None |
| B13 | Fix cleanup_dataframes nested-attribute matching | FLH-2 | 0.5d | Low | None |

**Sprint B subtotal:** ~8.5 days

---

## Sprint C — Architecture Cleanup (Week 3)

**Goal:** Reduce duplication, formalize missing layers, improve code organization.

| # | Task | Findings | Est. | Risk | Dependencies |
|---|------|----------|------|------|-------------|
| C1 | Extract shared workflow logic from onboarding.py + existing.py into `ui/shared_workflow.py` | UI-1, UI-2 | 5d | High | Sprint A fixes applied first |
| C2 | Split `existing.py` into phase-specific modules (~5-6 files) | UI-2 | 3d | Medium | C1 |
| C3 | Replace manual `ParseOptions`/`ColumnMapping`/`ValidationOptions` construction with `from_context()` | UI-3 | 1d | Medium | None |
| C4 | Remove dead code (`_compare_stores`, `_generate_file_reviews`) | UI-4 | 0.5d | Low | None |
| C5 | Parameterize `_merge_accumulate` into single function | PRC-3 | 1d | Medium | Aggregation tests |
| C6 | Adopt single canonical naming convention (`UNITS_SOLD`, `TOTAL_DOLLARS` everywhere) | CAN-3 | 1.5d | Medium | Golden regression tests |
| C7 | Integrate Flush Layer (`flush()`) at end of both workflow pipelines | FLH-1 | 1d | Low | C1 |
| C8 | Wire operations framework into workflow via Requirement Layer | REQ-1, REQ-2, OPS-1 | 2d | Medium | C1 |
| C9 | Align `load_format_config` version default to 2 | CFG-3 | 0.5d | Low | None |
| C10 | Preserve validation_config and output_config in config_from_ctx | CFG-4 | 0.5d | Low | None |
| C11 | Validate layout file existence in validate_config | CFG-5 | 0.5d | Low | None |
| C12 | Validate weight_col for weight/mixed quantity types in validate_config | CFG-6 | 0.5d | Low | None |
| C13 | Centralize session state keys in dataclass | UI-8 | 1d | Low | C1 |

**Sprint C subtotal:** ~17.5 days

**Minimum viable:** C3, C4, C5, C7, C9, C10, C11, C12 — ~6 days
**Full:** C1, C2, C6, C8, C13 — ~11.5 days

---

## Sprint D — Performance & Optimizations (Week 4)

**Goal:** Improve performance polish, testing coverage, documentation.

| # | Task | Findings | Est. | Risk | Dependencies |
|---|------|----------|------|------|-------------|
| D1 | Remove per-chunk `gc.collect()` (keep only final aggregation GC) | PRC-5 (Invalid finding — but actually remove unnecessary GC calls) | 0.5d | Low | None |
| D2 | Add `run_file_review_canonical` for consistency | PRC-8 | 0.5d | Low | C5 |
| D3 | Sort all aggregation results consistently | PRC-7 | 0.5d | Low | None |
| D4 | Add unit tests for Flush Layer | Missing in testing report | 1d | Low | None |
| D5 | Add streaming edge case tests (start_line > 0, record_type, multiline) | Missing in testing report | 2d | Low | A6 |
| D6 | Add config save/load round-trip test (completed_sections preservation) | Missing in testing report | 1d | Low | A1 |
| D7 | Add column collision scenario tests (store_col == units_col) | Missing in testing report | 1d | Low | A2 |
| D8 | Add field-level comparison edge case tests for `full_join_with_coalesce` | Missing in testing report | 1d | Low | A3 |
| D9 | Add encoding detection tests for remote sources | Missing in testing report | 1d | Medium | A8 |
| D10 | Add large-file / memory automated tests | Missing in testing report | 2d | Medium | None |
| D11 | Formalize Output Layer as pipeline stage (`workflow/output.py`) | OUT-1 | 1.5d | Low | C1 |
| D12 | Pass precomputed aggregations to file review generation | OUT-2 | 1d | Low | C5 |
| D13 | Wire `ExportOperation` into output pipeline (parquet support) | OUT-3 | 1d | Low | D11 |
| D14 | Increase multiline flatten sample size (>10 rows) | CFG-7 | 0.5d | Low | None |
| D15 | Handle delimiter ties with preference ordering | DET-5 | 0.5d | Low | None |
| D16 | Split `helpers.py` into single-responsibility modules | UI tech debt | 2d | Medium | None |
| D17 | Gate `display_processing_history` behind dev mode | UI-16 | 0.5d | Low | None |
| D18 | Update `ARCHITECTURE.md` and `docs/technical_docs.md` to 8-layer pipeline | Documentation review | 1d | Low | None |
| D19 | Add `atexit` handler for connection cleanup | SSH-1 (supplementary) | 0.5d | Low | A10 |
| D20 | Standardize encoding to DEFAULT_ENCODING in `read_sample` | LOC-1 | 0.5d | Low | None |
| D21 | Use `WarningPolicy` instead of `AutoAddPolicy` | SSH-3 | 0.5d | Low | None |

**Sprint D subtotal:** ~19 days

---

## Summary Rollup

| Sprint | Focus | Min Viable | Full Scope |
|--------|-------|------------|------------|
| **A** | Production Blockers | 3.5d | 6.5d |
| **B** | Workflow Stabilization | 8.5d | 8.5d |
| **C** | Architecture Cleanup | 6d | 17.5d |
| **D** | Performance & Optimizations | 8d | 19d |
| **Total** | | **26d** | **51.5d** |

### Recommendations

**RC1 Gate (must complete before release):** Sprint A (all) + Sprint B (B1-B7) = ~15 days

**RC1 Stretch (should do before release):** Sprint B (B8-B13) + Sprint C minimum viable = ~11 days

**Post-RC1:** Sprint C full scope + Sprint D = ~30 days

---

## Dependency Map

```
A1 ──┐
A2 ──┼── B5 ──┐
A3 ──┤         │
A4 ──┤         │
A5 ──┤         │
A6 ──┤         ├── C1 ──┬── C2 ──┐
A7 ──┤         │        │        │
A8 ──┤         │        ├── C7 ──┤
A9 ──┘         │        ├── C8 ──┤
A10────┐       │        └── C13─┐│
A11────┘       │                ││
               ├── C3 ──────────┘│
               ├── C4 ───────────┤
               ├── C5 ───┬── D2 ─┤
               │         └──D12 ─┤
               ├── C6 ──────────┐│
               │                ││
               ├── D1 ─────────┐││
               ├── D3 ────────┐│││
               └── C9-C12 ───┐││││
                              │││││
               D4-D10 ───────┘││││
               D11 ───────────┘│││
               D13 ────────────┘││
               D14-D21 ────────┘│
                                │
               B1-B13 ─────────┘
```

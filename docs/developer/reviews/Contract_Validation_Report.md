# Layer Boundary Contract Validation Report

**Date:** 2026-07-23

---

## Executive Summary

8 issues found across layer boundaries: **0 Critical, 2 High, 4 Medium, 2 Low**.

---

## Findings

### 1. Detection → ProcessingContext: `generate_detection_summary` vs `apply_to_context`

| # | Issue | Risk |
|---|-------|------|
| 1.1 | `generate_detection_summary` does NOT return `schema` or `layout` keys. `apply_to_context` sets `ctx.schema = self.schema or self.columns` (line 132) but `detect_file` never populates `result.schema` or `result.layout` — they remain `None` from the `DiscoveryResult()` constructor. Consumers that read `ctx.schema` (e.g. `_phase4_processing`, `_phase5_validation` in onboarding) will silently fall back to `ctx.columns`, which may not reflect the intended canonical schema. | **Medium** |
| 1.2 | `detect_file()` does not set `detail_layout`, `header_layout`, `trailer_layout`, `suggested_joins`, or `candidate_columns` on `DiscoveryResult` (except explicit override at line 199 for `candidate_columns`). `apply_to_context` sets all of them anyway (lines 134-153), leaving them as `None`/`[]`/`{}`. These are consumed downstream — `header_layout`/`detail_layout`/`trailer_layout` are used by `apply_format_config` and the execution engine for multiline files. If a config is loaded from JSON these would be populated, but if the flow depends solely on detection they'll be missing. | **Medium** |
| 1.3 | `generate_detection_summary` returns `record_prefix` cast as `None` initially (line 862) but populated as a list later (line 933). `DiscoveryResult.__init__` defaults `record_prefix` to `None` but `apply_to_context` sets `ctx.record_prefix` to `None`. `ProcessingContext` has no `record_prefix` field — so it's silently dropped. No consumer reads `ctx.record_prefix`, so this is dead data. | **Low** |
| 1.4 | `generate_detection_summary` returns `date_columns`, `quantity_columns`, `weight_columns`, `uom_columns` but `DiscoveryResult` does not capture any of these. No consumer on `ProcessingContext` needs them currently, but this is a documentation gap: if a future downstream phase needs date column info, it would need re-detection. | **Low** |

**Recommended fixes:**
- 1.1: After calling `generate_detection_summary`, explicitly set `result.schema = summary.get("columns")` in `detect_file()` so that `schema` is never `None` when columns exist.
- 1.2: No fix needed immediately — these are populated from config load. Document that `apply_format_config` is the primary source for layout fields.
- 1.3: Remove `record_prefix` from `DiscoveryResult.__init__` and `apply_to_context` if no consumer uses it.
- 1.4: No action needed.

---

### 2. ProcessingContext → FormatConfig: `config_from_ctx` mapping

| # | Issue | Risk |
|---|-------|------|
| 2.1 | `config_from_ctx` (line 397) does NOT copy `header_layout`, `detail_layout`, or `trailer_layout` from context directly — it uses `getattr(ctx, 'header_layout', None)` etc. while most other fields use direct attribute access. These are correctly handled via `getattr`, but the inconsistency is a maintenance risk. | **Low** |
| 2.2 | `config_from_ctx` does NOT copy `encoding`, `has_header`, `layout_file`, `header_layout_file`, `detail_layout_file`, `trailer_layout_file`, `validation_config`, or `output_config`. These fields are set only when a `FormatConfig` is loaded from JSON. If `config_from_ctx` is used to save, those fields are lost. | **Medium** |
| 2.3 | `config_from_ctx` maps `ctx.quantity_type` → `cfg.quantity_type`. However `ProcessingContext.quantity_type` (line 67) is typed as `str` with default `"auto"`, while `FormatConfig.quantity_type` (line 185) has default `"units"`. On round-trip (save + load), `"auto"` would be silently accepted but may not be handled identically. | **Low** |
| 2.4 | `ProcessingContext` has `weight_qty_col`, `units_uom`, `quantity_strategy` fields (lines 69-72). `config_from_ctx` does NOT capture these. They are lost on save. | **Medium** |
| 2.5 | `ProcessingContext` has `storelist_path`, `storelist_delim`, `storelist_store_col`. `FormatConfig` has no equivalent fields — these are never saved/restored. | **Low** |

**Recommended fixes:**
- 2.2: Add `encoding`, `has_header`, and nested `validation_config`/`output_config` to `config_from_ctx`.
- 2.4: Add `weight_qty_col`, `units_uom`, `quantity_strategy` to `FormatConfig` and `config_from_ctx`.
- 2.5: Verify whether store list fields should be part of config; if not, document why.

---

### 3. FormatConfig → ProcessingContext: `apply_format_config` restoration

| # | Issue | Risk |
|---|-------|------|
| 3.1 | `apply_format_config` does NOT set `ctx.candidate_columns`, `ctx.candidate_layout`, `ctx.candidate_keys`, `ctx.suggested_joins`, `ctx.disclaimer_lines`, `ctx.record_prefix`, `ctx.confidence`, `ctx.warnings`, or `ctx.recommendations`. These are detection-only fields. Downstream phases should not rely on them after config load. | **Low** |
| 3.2 | `apply_format_config` does NOT set `ctx.weight_qty_col`, `ctx.units_uom`, or `ctx.quantity_strategy`. These are in `ProcessingContext` (lines 67, 69, 71) but `FormatConfig` has no corresponding fields to restore from. | **High** |
| 3.3 | `apply_format_config` does NOT set `ctx.eff_type`, `ctx.eff_delimiter`, `ctx.eff_record_type`, `ctx.eff_layout`. These are set manually in `existing.py` line 715-730 during mapping confirmation. If a config is loaded and the existing flow's `_phase4_processing` is entered, these `eff_*` fields remain unset. | **High** |
| 3.4 | `apply_format_config` sets `ctx.schema` from `config.canonical_schema` and `ctx.columns` from `config.physical_schema`. If `config.canonical_schema` is empty but `config.physical_schema` is set, only `ctx.columns` is set and `ctx.schema` stays None. This contradicts `ProcessingContext` defaults where `schema` is the authoritative canonical schema. | **Medium** |

**Recommended fixes:**
- 3.2: Add `weight_qty_col`, `units_uom`, `quantity_strategy` to `FormatConfig` and restore them in `apply_format_config`.
- 3.3: Either have `apply_format_config` set the `eff_*` fields, or have the existing flow compute them consistently from a single source.
- 3.4: When `config.canonical_schema` is empty, set `ctx.schema = ctx.columns` as a fallback in `apply_format_config`.

---

### 4. DiscoveryResult → ProcessingContext: Field coverage in `apply_to_context`

| # | Issue | Risk |
|---|-------|------|
| 4.1 | All 20 fields from `DiscoveryResult` are correctly mapped to `ProcessingContext` in `apply_to_context`. However, as noted in 1.1, `schema` is populated as `self.schema or self.columns`. DiscoveryResult's `schema` is always `None` because `detect_file` never sets it — so `schema` always equals `columns`. | **Medium** |
| 4.2 | `apply_to_context` does NOT set `ctx.discovery` to `self`. The callers (`onboarding.py` line 276, `existing.py` lines 156, 226, 993) separately assign `ctx.discovery = discovery`. This is fragile — if a new caller forgot to set `ctx.discovery`, downstream phases would have no reference to the original `DiscoveryResult`. | **Medium** |

**Recommended fix:**
- 4.1: Have `detect_file` explicitly populate `result.schema = columns` (same as columns during detection).
- 4.2: Add `ctx.discovery = self` inside `apply_to_context`, and remove the redundant assignments from callers.

---

### 5. UI → Workflow: Parameter passing consistency

| # | Issue | Risk |
|---|-------|------|
| 5.1 | `onboarding.py:_run_validation` (line 904) calls `run_onboarding_validation(ctx, ...)`. The orchestration signature at `orchestration.py:38` expects the same parameters. **All positional arguments match.** | ✅ OK |
| 5.2 | `existing.py:_execute_validation` (line 1266) calls `run_existing_validation(ctx, ...)`. The orchestration signature at `orchestration.py:93` expects the same parameters. **All positional arguments match.** | ✅ OK |
| 5.3 | `onboarding.py:_phase4_processing` calls `run_onboarding_processing(ctx, source=_onb_source)` (line 613). Orchestration signature: `run_onboarding_processing(ctx, source=None)`. **Matches.** | ✅ OK |
| 5.4 | `existing.py:_phase4_processing` calls `run_existing_processing(ctx, source=_ex_source)` (line 748). Orchestration signature: `run_existing_processing(ctx, source=None)`. **Matches.** | ✅ OK |
| 5.5 | **BUT:** `run_onboarding_validation` in orchestration (line 38) builds a `ParseOptions` with `column_names=ctx.schema` but does NOT include `detail_layout`. The `ParseOptions` constructor (line 55) does accept `detail_layout` — it's simply not passed. This means multiline HDR detail layout metadata is not forwarded to the validation options. | **Medium** |
| 5.6 | Similarly, `run_existing_validation` in orchestration (line 93) builds `ParseOptions` with `detail_layout=ctx.prod.detail_layout` (lines 120, 134). The onboarding path does not do this (line 55). Mitigated by 5.5. | **Medium** |

**Recommended fix:**
- 5.5: Add `detail_layout=ctx.detail_layout` to `ParseOptions` construction in `run_onboarding_validation`.

---

### 6. Type Consistency

| # | Issue | Risk |
|---|-------|------|
| 6.1 | `detect_file` at `discovery.py:159` — when called during the config-loaded path, `detect_file` may not be called at all. But `apply_to_context` sets `ctx.file_paths`, `ctx.file_type`, etc. These are `Optional[List[str]]` and `Optional[str]` types. The `validate_for_processing` method (line 106) checks `if not self.file_paths` and `if not self.file_type` — which would be `True` for an empty list or `None`. This is safe. | ✅ OK |
| 6.2 | `detect_file` returns `DiscoveryResult` with `error` populated on failure. In `onboarding.py` line 368-373, `discovery.error` is checked. If error is set but `discovery.file_type` is `"fixed"`, the code shows a warning instead of an error — this hides the actual error. But this is a UI logic issue, not a contract issue. | **Low** |
| 6.3 | `canonical_chunk_stream` (line 488) has 24 parameters, many with mismatched optionality vs callers. The `iter_chunks` helper (line 456) has 14 positional parameters. Both are called from the operation layer. No type enforcement — this is a fragility risk. | **Low** |

---

## Summary

| Boundary | Issues | Critical | High | Medium | Low |
|----------|--------|----------|------|--------|-----|
| Detection → ProcessingContext | 4 | 0 | 0 | 2 | 2 |
| ProcessingContext → FormatConfig | 4 | 0 | 0 | 2 | 2 |
| FormatConfig → ProcessingContext | 4 | 0 | 2 | 1 | 1 |
| DiscoveryResult → ProcessingContext | 2 | 0 | 0 | 2 | 0 |
| UI → Workflow | 2 | 0 | 0 | 2 | 0 |
| Type consistency | 0 | 0 | 0 | 0 | 0 |
| **Total** | **16** | **0** | **2** | **9** | **5** |

---

## Top Priority Fixes

1. **HIGH — 3.2**: `apply_format_config` misses `weight_qty_col`, `units_uom`, `quantity_strategy` — these are in `ProcessingContext` but lost on config round-trip. Add fields to `FormatConfig`.

2. **HIGH — 3.3**: `apply_format_config` does not set `eff_type`, `eff_delimiter`, `eff_record_type`, `eff_layout`. The existing flow sets these manually; config-loaded path leaves them unset. Either set them in `apply_format_config` or compute consistently.

3. **MEDIUM — 5.5**: `detail_layout` missing from `ParseOptions` construction in `run_onboarding_validation`. Add the parameter.

4. **MEDIUM — 1.1**: `detect_file` never populates `schema` on `DiscoveryResult` — consumers that expect `ctx.schema` get `ctx.columns` instead. Explicitly set `schema = columns` after detection.

5. **MEDIUM — 4.2**: `apply_to_context` should set `ctx.discovery = self` to avoid fragile manual assignments in callers.

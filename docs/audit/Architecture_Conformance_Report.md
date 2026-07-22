# DVA Platform — Architecture Conformance Report

**Date:** 2026-07-16
**Auditor:** Principal Software Architect
**Scope:** Full repository read-only audit
**Method:** Execution path tracing, dependency analysis, layer boundary mapping, responsibility analysis

**Note:** This report is distinct from the code-level bug audit (`Audit_Report_2026-07-15.md`). It focuses exclusively on **architectural conformance** against the 7-layer target architecture.

---

## Target Architecture

```
Connection Layer
    ↓
Detection Layer
    ↓
Canonical Layer
    ↓
Operation Layer
    ↓
Processing Layer
    ↓
Output Layer
    ↓
Flush Layer
```

**Principle:** Each layer has one responsibility, one input, one output. No layer knows implementation details of another layer.

---

## Architecture Score: 4/10

### Layer Scores

| Layer | Score | Rationale |
|-------|-------|-----------|
| Connection Layer | 7/10 | Clean IDataSource abstraction. Detection orchestration bleeds in from Connection Manager UI. |
| Detection Layer | 6/10 | DiscoveryResult is a good contract. Column propagation bug (`colums` typo). No formal output contract to Canonical Layer. |
| Canonical Layer | 5/10 | Three-layer schema model defined but not fully enforced downstream. Physical schema references still leak into processing. |
| Operation Layer | 2/10 | Operations framework exists but is completely disconnected from the main workflow. No user-facing path. |
| Processing Layer | 5/10 | Streaming and canonical pipeline exist but UI orchestrates processing directly, bypassing the layer boundary. |
| Output Layer | 2/10 | No formal Output layer. Reports, downloads, metrics embedded in UI functions. |
| Flush Layer | 2/10 | Flush service module exists but is not called from any workflow. No automatic resource cleanup. |

---

## Boundary Violations

### CRITICAL — BV-1: UI Layer orchestrates Processing, Validation, and Discovery directly

**Files:**
- `dav_tool/ui/onboarding.py` — calls `run_store_aggregation()`, `run_item_aggregation()`, `run_onboarding_validation()`, `detect_file()` directly
- `dav_tool/ui/existing.py` — calls 4 parallel aggregation threads, validation, discovery comparison, schema comparison, and migration report generation

**Violation:**
Per the architecture, the UI Layer should only handle rendering, user interaction, and session state. The `_phase4_processing` function in `onboarding.py:476-478` manually constructs `ParseOptions` and `ColumnMapping` from context fields and invokes aggregation engines. The `_detect_and_set` function in `existing.py:1041-1097` renders Streamlit widgets (`st.text_input`, `st.error`, `st.success`) inside a detection function.

**Impact:** Layer boundaries are aspirational, not enforced. Bug fixes must be duplicated across onboarding and existing (40-50% code duplication). Business logic cannot be tested independently of the UI.

**Recommended Fix:** Move all orchestration into `workflow/` service functions. UI files should call `workflow.run_phase(phase_name, ctx)` and receive results for display only.

### CRITICAL — BV-2: Connection Manager runs Detection

**File:** `dav_tool/ui/connection_manager.py:444` — `_show_path_preview` calls `detect_file()` and stores `DiscoveryResult` in session state.

**Violation:**
The Connection Layer should manage connections only. Detection is a separate concern that should be triggered by the Workflow Layer after connection is established. Currently, the Connection Manager both connects and detects, coupling two lifecycle stages.

**Impact:** Detection results are stored in session state before the workflow officially enters the Discovery phase. The workflow phase progression is out of sync with actual data readiness.

**Recommended Fix:** The Connection Manager should emit a "path selected" event. The Workflow Layer should react to this event and trigger detection when the workflow phase advances to Discovery.

### HIGH — BV-3: Validation Layer aggregates data

**Files:**
- `dav_tool/validation/store.py` — calls `stream_store_aggregate()` from `_aggregators`
- `dav_tool/validation/item.py` — calls `stream_item_aggregate()` from `_aggregators`

**Violation:**
The Validation Layer should apply business rules only. Aggregation is a Processing Layer responsibility. When validation re-aggregates data, it both violates layer separation AND performs duplicate work (aggregation already happened in the Processing phase).

**Impact:**
- Layer separation: Validation now knows about `_aggregators`, `IDataSource`, `ParseOptions`
- Performance: Re-aggregation for every validation call doubles processing time
- Coupling: Changes to the aggregation API require changes in validation modules

**Recommended Fix:** Validation should accept pre-computed aggregation results as input. The `storelevelvalidation` and `run_item_validation` functions should require pre-computed DataFrames and not fall back to calling `stream_store_aggregate`/`stream_item_aggregate` directly.

### HIGH — BV-4: No Operation Layer integration

**Files:**
- `dav_tool/operations/` — 7 operations exist (Aggregate, Filter, Sort, Sample, Statistics, Export, Preview)
- Zero integration points with `ui/onboarding.py`, `ui/existing.py`, or `workflow/*.py`

**Violation:**
The Operation Layer is defined in the architecture but is completely disconnected from every workflow path. The architecture specifies that processing executes operations selected by the user, but the actual code hard-codes store aggregation + item aggregation without any operation selection mechanism.

**Impact:**
- Users cannot select between "Raw Data Review", "Aggregate Only", or "Aggregate + Calculate" modes
- The operations framework represents investment with zero return
- Adding new operation types requires modifying core workflow code rather than plugging into the framework

**Recommended Fix:** Wire the `OutputMode` enum from `options.py` into the UI as a user-facing selection. Use it to select which operations execute. The processing phase should iterate over selected operations from the registry rather than hard-coding store and item aggregation calls.

### HIGH — BV-5: Output Layer is embedded in UI

**Files:**
- `ui/onboarding.py` — `_display_results()` renders reports inline
- `ui/existing.py` — `_display_results()` renders reports inline
- `_reports.py` — generates file review data but is called from `workflow/validation.py` not from a formal Output service

**Violation:**
The Output Layer has no formal existence as a service. Report generation, metrics display, download buttons, and summary display are mixed into UI rendering functions. There is no standalone `workflow/output.py` module that could produce outputs without a Streamlit context.

**Impact:**
- Outputs cannot be tested independently of the UI
- No reuse between onboarding and existing workflows (two copies of `_display_results`)
- No support for non-UI output modes (CLI, API)

**Recommended Fix:** Create `workflow/output.py` as a formal Output Layer service. It should produce output data (reports, metrics, export files) independent of the rendering layer. The UI should call the Output service and then render the results.

### HIGH — BV-6: Flush Layer is not integrated

**File:** `dav_tool/workflow/flush.py` — exists but is never called from any workflow path.

**Violation:**
The Flush Layer is defined in the architecture but has zero integration points. The `flush()` function, `_flush_session_state()`, and `cleanup_all()` are never invoked at the end of onboarding or existing workflows.

**Impact:**
- DataFrames remain in memory after workflow completion
- SSH connections may not be properly closed
- Temp files leak (especially SSH downloads via `NamedTemporaryFile(delete=False)`)
- Session state accumulates across workflow runs

**Recommended Fix:** Call `flush()` at the end of both onboarding and existing workflow pipelines. Register `atexit` handlers for unexpected shutdowns.

### MEDIUM — BV-7: Configuration Layer calls Parser preview functions

**File:** `dav_tool/format_config.py:341-354` — `apply_format_config()` calls `preview_flattened_multiline()` and `preview_flattened_multiline_fixed()` to flatten multiline data during config application.

**Violation:**
The Configuration Layer should manage configuration data only. Calling parser preview functions couples config application to parsing implementation details.

**Impact:** Changes to parser preview APIs require changes in format_config. The hardcoded `n_rows=10` limit is a parsing concern specified in configuration code.

**Recommended Fix:** The Configuration Layer should produce a configuration object. Parsing/preview should be triggered by the Workflow Layer after configuration is accepted, not during config application.

### MEDIUM — BV-8: Physical schema references downstream of Canonical Layer

**File:** `dav_tool/_aggregators.py` — aggregation consumes `ParseOptions.column_names` which may contain physical (non-canonical) column names in some code paths. The `canonical_chunk_stream()` function bridges parsing and normalization but the UI still passes raw column names in some paths.

**Trace:** `ui/onboarding.py:476-478` manually constructs `ParseOptions` with `column_names=ctx.columns` (physical) instead of `ctx.schema` (canonical).

**Violation:**
Per the architecture, all downstream processing (Processing, Validation, Reports) must consume canonical column names only. The manual construction of `ParseOptions` in the UI bypasses the canonical schema layer.

**Impact:** Data may be processed with physical column names leaked into aggregation results. Validation results use inconsistent naming.

**Recommended Fix:** All `ParseOptions` construction must go through `CanonicalContext.from_context()` which ensures canonical schema propagation. Remove manual `ParseOptions` construction from all UI files.

---

## Coupling Score: 4/10

| Metric | Score | Detail |
|--------|-------|--------|
| UI-to-Workflow coupling | 2/10 | UI imports and invokes workflow services directly (tight coupling) |
| Validation-to-Processing coupling | 3/10 | Validation calls aggregation functions directly |
| Configuration-to-Parser coupling | 5/10 | Config calls parser preview functions |
| Operations coupling | 8/10 | Operations framework is cleanly decoupled (but unused) |
| DataSource coupling | 8/10 | Clean IDataSource abstraction |
| Workflow-to-Service coupling | 6/10 | Workflow services import from _parsers, _aggregators, _normalizer |

---

## Cohesion Score: 5/10

| Module | Cohesion | Issue |
|--------|----------|-------|
| `ui/helpers.py` | 3/10 | 6 distinct responsibilities: file listing, column detection, config rendering, validation, phase progress, DataFrame cleanup |
| `_aggregators.py` | 5/10 | Triple-duplicated `_merge_accumulate` functions with hardcoded column names |
| `ui/existing.py` | 3/10 | 1720 lines, 5+ workflows (discovery, config, processing, validation, reports) in one file |
| `ui/onboarding.py` | 4/10 | 882 lines, same 5 workflows duplicated |
| `workflow/discovery.py` | 7/10 | Focused on detection orchestration |
| `operations/*.py` | 9/10 | Each operation is single-responsibility |

---

## Architecture Drift

| Target Architecture | Current Implementation | Drift Severity |
|--------------------|----------------------|----------------|
| Connection → Detection → Canonical → Operation → Processing → Output → Flush | UI orchestrates everything inline. No formal Operation/Output/Flush stage. | HIGH |
| Each layer: one input, one output, one responsibility | UI layer has many responsibilities (orchestration, rendering, state, routing). Validation does aggregation. CM does detection. | CRITICAL |
| Processing consumes Canonical Dataset only | Physical schema leaks in via manual Option construction in UI | HIGH |
| Operations framework is main processing path | Operations framework is completely disconnected from workflow | CRITICAL |
| Flush Layer releases resources automatically | Flush module exists but is never called | HIGH |
| Output Layer produces reports independently | Reports are embedded in UI rendering functions | HIGH |

---

## Technical Debt (Architecture-Related)

### Code Duplication (Architecture Impact)

| Area | Location | Architecture Impact |
|------|----------|-------------------|
| Pipeline orchestration | `onboarding.py` + `existing.py` (~300 lines duplicated) | Layer boundaries lost; changes must be mirrored |
| `_display_results` | Both UI files (~50 lines each) | Output Layer would eliminate both |
| `_merge_accumulate` × 3 | `_aggregators.py` | Cohesion reduced; canonical name changes require 3 edits |
| ParseOptions construction | 4+ locations (onboarding, existing, validation paths, UI helpers) | Canonical schema bypassed |

### Dead Code (Architecture Impact)

| Function | Location | Architecture Significance |
|----------|----------|--------------------------|
| `_compare_stores` | `existing.py` | Intended for Output Layer but never wired |
| `_generate_file_reviews` | `existing.py` | Intended for Output Layer but never wired |
| `ProcessingContext.validate_for_processing` | `processing_context.py` | Layer contract validation never used |
| Full operations framework | `operations/` | Unused architecture investment |

### Missing Abstractions

| Missing Abstraction | Impact |
|--------------------|--------|
| No `workflow/output.py` | Output Layer does not exist |
| No `workflow/operation_selector.py` | Operation Layer does not exist |
| No canonical schema enforcement point | Physical schema leaks into processing |
| No data access strategy selector | No automatic stream/copy/chunk decision |
| No formal layer contracts | Interfaces between layers are implicit, not enforced |

---

## Refactoring Priority

### Priority 1 — Architectural Integrity (Must Fix)

| # | Change | Impact | Complexity |
|---|--------|--------|------------|
| 1 | Extract all orchestration from UI into `workflow/` service functions | Restores UI → Workflow boundary. Eliminates 40-50% duplication. | High |
| 2 | Create `workflow/output.py` as formal Output Layer | Enables independent output testing, UI independence | Medium |
| 3 | Integrate `workflow/flush.py` into both workflow pipelines | Prevents resource leaks, enables cleanup | Low |
| 4 | Remove manual ParseOptions/ColumnMapping construction from UI | Enforces canonical schema everywhere | Low |
| 5 | Wire operations framework into workflow | Realizes Operation Layer investment | Medium |

### Priority 2 — Layer Boundary Enforcement

| # | Change | Impact | Complexity |
|---|--------|--------|------------|
| 6 | Stop validation from calling `_aggregators` | Enforces Processing→Validation boundary | Medium |
| 7 | Remove detection from Connection Manager | Enforces Connection→Detection boundary | Low |
| 8 | Remove parser calls from `format_config.py` | Enforces Config→Parser boundary | Low |
| 9 | Add canonical schema validation point in workflow | Prevents physical schema leaks | Low |

### Priority 3 — Cohesion and Coupling

| # | Change | Impact | Complexity |
|---|--------|--------|------------|
| 10 | Split `ui/helpers.py` into single-responsibility modules | Improves cohesion | Medium |
| 11 | Parameterize `_merge_accumulate` into single function | Improves cohesion, reduces duplication | Low |
| 12 | Add formal layer contract interfaces | Enables runtime enforcement of boundaries | Medium |

---

## Object Flow Analysis

### IDataSource
**Status:** ✅ Exists and flows correctly
- Defined in `datasource/base.py:IDataSource`
- Implementations: `LocalDataSource`, `SSHDataSource`
- Managed by `datasource/manager.py` singleton
- Consumed by: `detection.py`, `workflow/discovery.py`, `workflow/processing.py`, `workflow/validation.py`, `_parsers.py`, `_aggregators.py`, `_reports.py`, `config_builder.py`

### DiscoveryResult
**Status:** ⚠️ Exists but has propagation bug
- Defined in `workflow/discovery.py:DiscoveryResult`
- Produced by `detect_file()` in `workflow/discovery.py`
- **Bug:** `from_context()` at line 96 has `"colums"` typo — always returns `columns=None`
- Should flow: Connection → Detection → Configuration → Processing
- Actually flows: CM stores in session state → UI passes to workflow functions

### CanonicalDataset
**Status:** ⚠️ Conceptually exists but not formalized
- Produced by `canonical_chunk_stream()` in `_parsers.py`
- Consumed by `_aggregators.py`
- **Gap:** Not formalized as a typed object. The canonical stream is iterable of DataFrames with canonical column names, but there is no `CanonicalDataset` class or contract.

### OperationContext
**Status:** ❌ Does not exist
- No `OperationContext` object exists in the codebase
- The `CanonicalContext` in `options.py` is the closest analog, bundling `ParseOptions` + `ColumnMapping` + `canonical_schema`
- Operations receive raw DataFrames, not context objects

### OperationResult
**Status:** ✅ Exists but unused in main workflow
- Defined in `operations/base.py:OperationResult`
- Used within the operations framework
- **Gap:** Never consumed by the main workflow pipeline

---

## Summary

| Dimension | Score | Key Findings |
|-----------|-------|-------------|
| Architecture Score | 4/10 | Layer boundaries exist but are frequently violated |
| Layer Separation | 3/10 | UI orchestrates everything; validation aggregates; CM detects |
| Coupling | 4/10 | UI tightly coupled to all layers below |
| Cohesion | 5/10 | Large multi-responsibility files dominate |
| Architecture Drift | HIGH | Target architecture not realized for 3 of 7 layers |

The architecture has the right abstractions (`IDataSource`, `DiscoveryResult`, canonical pipeline, operations framework) but the actual code flow bypasses these abstractions. The largest architectural corrections needed are:

1. **Stop the UI from orchestrating business logic** — This single change would resolve the majority of boundary violations
2. **Wire the operations and flush layers into the workflow** — These modules exist but are disconnected
3. **Create the Output Layer** — Reports and exports need a formal service boundary

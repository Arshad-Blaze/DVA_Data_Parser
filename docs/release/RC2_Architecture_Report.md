# RC2 Architecture Report

## What Changed

### 1. Execution Engine (NEW — `workflow/execution.py`)

**What:** Created `ExecutionEngine` class that sits between Workflow Orchestration and Operation Layer.

**Why:** Workflow should only call `run()`. The engine determines which operations need execution, checks cached results, skips completed work, and dispatches through the Operation Layer.

**Files modified:**
- `dav_tool/workflow/execution.py` — NEW
- `dav_tool/workflow/orchestration.py` — Updated `run_onboarding_processing()` and `run_existing_processing()` to delegate to `ExecutionEngine`

**Benefits:**
- No logic duplication between onboarding and existing flows
- Cache-checking built in — future operations get automatic skip-if-done
- Single `run()` call replaces ad-hoc dispatch

### 2. CanonicalDataset (NEW — `workflow/canonical.py`)

**What:** Created `CanonicalDataset` class — the single input contract for Processing. Hides all file-format details behind a streaming iterator.

**Why:** Processing should never know about CSV, delimiter, encoding, fixed-width, multiline, HDR, record types. The `CanonicalDataset` wraps `ParseOptions` + `ColumnMapping` internally and yields pre-normalized canonical chunks.

**Files modified:**
- `dav_tool/workflow/canonical.py` — Added `CanonicalDataset` class with `iter_chunks()`, `from_parse_options()`, `from_context()` factories
- `dav_tool/workflow/processing.py` — Internal aggregation uses `CanonicalDataset` + `aggregate_dataset()` instead of passing 20+ format-specific parameters
- `dav_tool/_aggregators.py` — Added `aggregate_dataset()` function
- `dav_tool/options.py` — `CanonicalContext` now documents consolidation into `CanonicalDataset`, added `to_dataset()` conversion method

**Benefits:**
- Processing is completely format-independent
- Adding a new file format requires only a new parser — no processing changes
- Clear contract boundary between Parser and Processing layers

### 3. Operation Layer Registry (REFACTOR — `operations/`)

**What:** Replaced hard-coded if/elif branching in `OperationExecutor` with a `WorkflowOperation` registry dispatch.

**Files modified:**
- `dav_tool/operations/base.py` — Added `WorkflowOperation` protocol
- `dav_tool/operations/registry.py` — Added `register_workflow_op()`, `get_workflow_op()`, `list_workflow_ops()`
- `dav_tool/operations/workflow_ops.py` — NEW: `AggregateWorkflowOp`, `FormatChangeWorkflowOp`
- `dav_tool/operations/__init__.py` — Registers both workflow operations
- `dav_tool/operations/orchestration.py` — `OperationExecutor.execute()` now uses `get_workflow_op()` registry dispatch

**Benefits:**
- Adding a new operation requires zero changes to `OperationExecutor`
- New operations: create class + register — done
- Clear separation: data operations (`IDataOperation`) vs. workflow operations (`WorkflowOperation`)

### 4. BV-3 Fixed: Validation No Longer Aggregates

**What:** Removed fallback aggregation paths from `validation/store.py` and `validation/item.py`. Both functions now require pre-computed summaries and raise `ValueError` if not provided.

**Files modified:**
- `dav_tool/validation/store.py` — `storelevelvalidation()` raises if `prod_summary` or `test_summary` is None
- `dav_tool/validation/item.py` — `run_item_validation()` raises if `bau_summary` or `test_summary` is None
- `run_benchmarks.py` — Pre-computes summaries before calling validation

**Benefits:**
- Clear architectural boundary: Validation never performs aggregation
- Catch violations at call time with a clear error message

### 5. BV-7 Fixed: Config Routes Through Workflow Preview

**What:** Changed `config_builder.py` to import preview functions from `workflow/preview.py` instead of `_parsers` directly.

**Files modified:**
- `dav_tool/config_builder.py` — Imports from `workflow.preview` instead of `_parsers`
- `dav_tool/workflow/preview.py` — Added `scan_delimited()` wrapper

**Benefits:**
- Architecture boundary enforced: UI/Config → Workflow → Parser
- No direct `_parsers` imports outside the Workflow layer

### 6. BV-8 Fixed: Physical Schema No Longer Leaks

**What:** `CanonicalDataset` now handles all physical-to-canonical name mapping internally. Validation functions operate exclusively on canonical column names in pre-computed summaries.

**Files modified:**
- `dav_tool/workflow/canonical.py` — `CanonicalDataset` provides canonical schema + normalized chunks
- `dav_tool/workflow/processing.py` — Aggregation via `CanonicalDataset` ensures only canonical names reach downstream
- `dav_tool/validation/store.py` — Documented that format-specific params are unused when summaries are provided

**Benefits:**
- Downstream layers (Processing, Validation, Output) see only canonical names
- Physical column names never escape the Parser → Normalizer boundary

## Files Summary

### New Files
| File | Description |
|------|-------------|
| `dav_tool/workflow/execution.py` | ExecutionEngine — single `run()` dispatch |
| `dav_tool/operations/workflow_ops.py` | AggregateWorkflowOp, FormatChangeWorkflowOp |
| `Architecture_Bible.md` | Architecture reference document (this sprint) |

### Modified Files
| File | Change |
|------|--------|
| `dav_tool/workflow/orchestration.py` | Delegates to ExecutionEngine |
| `dav_tool/workflow/canonical.py` | Added CanonicalDataset |
| `dav_tool/workflow/processing.py` | Uses CanonicalDataset internally |
| `dav_tool/workflow/preview.py` | Added scan_delimited() |
| `dav_tool/operations/base.py` | Added WorkflowOperation protocol |
| `dav_tool/operations/registry.py` | Added workflow op registry |
| `dav_tool/operations/__init__.py` | Registers workflow operations |
| `dav_tool/operations/orchestration.py` | Registry-based dispatch |
| `dav_tool/options.py` | CanonicalContext → to_dataset() |
| `dav_tool/_aggregators.py` | Added aggregate_dataset() |
| `dav_tool/validation/store.py` | Removed fallback aggregation |
| `dav_tool/validation/item.py` | Removed fallback aggregation |
| `dav_tool/config_builder.py` | Routes through workflow/preview |
| `run_benchmarks.py` | Pre-computes summaries |

## Test Suite

- **234 tests pass** (all unit tests)
- No regressions in:
  - Delimited parsing
  - Fixed-width parsing  
  - Multiline parsing (HDR + delimited)
  - Onboarding workflow
  - Existing/format-change workflow
  - Streaming with Polars LazyFrame fast path
  - Validation (store + item)
  - File review reports
  - Output generation
  - Flush/cleanup

## Remaining Technical Debt

| Item | Priority | Description |
|------|----------|-------------|
| Validation function signatures still carry format params | Low | `storelevelvalidation()` and `run_item_validation()` accept ~30 params that are unused when summaries are provided. Cleanup deferred to avoid touching callers. |
| `CanonicalContext` still used internally | Low | Used in Operation Layer as construction helper. Could be fully replaced by `CanonicalDataset` in future RC. |
| `_reports.py` has direct `_aggregators` imports | Low | `generate_file_review()` calls `stream_store_aggregate()` and `stream_upc_summary()` directly. These are inside the Processing boundary but bypass the Operation Layer. |
| CanonicalSchema still references physical_schema | Low | Used only for schema rename display in UI. Not consumed by downstream logic. |

## Future RC3 Recommendations

1. **Clean up validation function signatures** — Remove unused format-specific parameters from `storelevelvalidation()` and `run_item_validation()` once all callers are updated
2. **MigrationOperation** — Add a new `WorkflowOperation` for the migration report phase, completing the registry coverage
3. **ValidationOperation** — Move validation dispatch into the Operation Layer registry
4. **Full `CanonicalDataset` adoption** — Replace all remaining `ParseOptions`/`ColumnMapping` direct consumption in downstream code with `CanonicalDataset`
5. **StatisticsOperation** — Register as a workflow operation for the stats-only OutputMode path

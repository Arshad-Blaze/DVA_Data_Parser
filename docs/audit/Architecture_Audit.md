# Architecture Audit

## Layer Separation

| Layer | Responsibility | Status | Finding |
|-------|---------------|--------|---------|
| UI | User interaction, rendering, session state | ✅ Clean | Minor: `get_column_names()` in helpers.py leaks detection logic |
| Workflow Orchestration | Thin API for UI, builds contracts | ✅ Clean | `orchestration.py` properly delegates to ExecutionEngine |
| ExecutionEngine | Determines pending operations, dispatches | ✅ Clean | Proper cache-check before dispatch |
| Operation Layer | Registry-dispatch via WorkflowOperation protocol | ✅ Clean | Plugin-based, extensible |
| Canonical Layer | CanonicalDataset — single processing contract | ⚠️ Minor | Schema is hardcoded, limited to 3-4 columns |
| Processing Layer | Aggregate via CanonicalDataset only | ✅ Clean | No physical schema references |
| Validation Layer | Compare pre-computed summaries | ✅ Clean | BV-3 fixed, no fallback aggregation |
| Output Layer | Pre-computed OutputResult | ✅ Clean | Proper separation |
| Flush Layer | Cleanup connections, DataFrames, session | ✅ Clean | Comprehensive |

## Data Flow

```
UI → Workflow → ExecutionEngine → OperationExecutor → CanonicalDataset → Processing → Validation → Output → Flush
```

The data flow matches the Architecture Bible. All RC2 violations (BV-1 through BV-8) are verified as fixed.

## Contract Compliance

| Contract | Provider | Consumer | Status |
|----------|----------|----------|--------|
| DiscoveryResult | workflow/discovery.py | UI, ProcessingContext | ✅ Proper |
| ParseOptions | options.py | CanonicalDataset, Processing | ✅ Proper |
| ColumnMapping | options.py | CanonicalDataset, Processing | ✅ Proper |
| CanonicalDataset | workflow/canonical.py | Processing Layer | ✅ Proper |
| OutputResult | workflow/output.py | UI | ✅ Proper |
| ValidationResult | workflow/validation.py | Workflow orchestration | ✅ Proper |

## Architecture Violations

1. **AA-1: Detection Logic in UI** — `ui/helpers.py:get_column_names()` reads files and parses data. Should be in `workflow/discovery.py`.
2. **AA-2: Reports Bypass Processing** — `_reports.py` imports directly from `_aggregators`, skipping the Canonical → Processing pipeline.
3. **AA-3: Hardcoded Canonical Schema** — `canonical.py:_build_schema_for_level()` returns hardcoded lists. Cannot be extended without code changes.
4. **AA-4: Orchestration Duplicates Contract Building** — `orchestration.py` builds `ParseOptions`/`ColumnMapping` manually in validation functions when `options.py` factories exist.

## Recommendations

1. Move `get_column_names()` to `workflow/discovery.py`
2. Make canonical schema dynamic/configurable
3. Route all report aggregation through `workflow/processing.py`
4. Refactor `orchestration.py` validation functions to use `ParseOptions.from_context()` / `ColumnMapping.from_context()`

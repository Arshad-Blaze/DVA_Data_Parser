# Architecture Bible — DVA Data Parser

## Layer Architecture

```
UI (Streamlit)
│
│  renders controls, collects input, shows progress, displays OutputResult
│
▼
Workflow Orchestration  (workflow/orchestration.py)
│
│  thin API: run_onboarding_processing(), run_existing_processing()
│
▼
ExecutionEngine  (workflow/execution.py)
│
│  run() → determines pending operations, checks cache, dispatches
│
▼
Operation Layer  (operations/)
│
│  OperationExecutor → registry-dispatch (WorkflowOperation protocol)
│  AggregateWorkflowOp, FormatChangeWorkflowOp
│
▼
Canonical Layer  (workflow/canonical.py)
│
│  CanonicalDataset — single contract for Processing
│  Hide file-format details (CSV, fixed-width, multiline, HDR, etc.)
│
▼
Processing Layer  (workflow/processing.py)
│
│  CanonicalDataset → aggregate_store_stream() / aggregate_item_stream()
│  Business calculations only — no format knowledge
│
▼
Validation Layer  (validation/)
│
│  Store-level: storelevelvalidation(prod_summary, test_summary)
│  Item-level:  run_item_validation(bau_summary, test_summary)
│  Pure comparison — no aggregation fallback (BV-3 fixed)
│
▼
Output Layer  (workflow/output.py)
│
│  OutputResult — pre-computed DataFrames + CSV bytes
│
▼
Flush Layer  (workflow/flush.py)
│
│  flush() — temp files, connections, DataFrames, session state
│
```

## Contracts Between Layers

| Layer | Produces | Consumes |
|-------|----------|----------|
| Connection | `IDataSource` | — |
| Detection | `DiscoveryResult` | raw file bytes |
| Canonical | `CanonicalDataset` | `ParseOptions` + `ColumnMapping` (internal) |
| Operation | results on `ctx` | `OperationContext` |
| Processing | `pl.DataFrame` (agg) | `CanonicalDataset` |
| Validation | `ValidationResult` | pre-computed agg DataFrames |
| Output | `OutputResult` | agg DataFrames + validation results |
| Flush | — (cleanup) | `ctx` objects |

## Execution Flow

### Onboarding (single-side)

```
UI Phase 4 (Processing)
  → orchestration.run_onboarding_processing(ctx, source)
    → ExecutionEngine.run(ctx, source)
      → checks ctx.store_agg / ctx.item_agg — skips if cached
      → AggregateWorkflowOp.execute(op_ctx)
        → ParseOptions.from_context(ctx) + ColumnMapping.from_context(ctx)
        → CanonicalDataset.from_parse_options(...) for level="store"
        → CanonicalDataset.from_parse_options(...) for level="item"
        → aggregate_dataset(dataset) via _aggregate_store_stream / _aggregate_item_stream
        → ctx.store_agg, ctx.item_agg stored

UI Phase 5 (Validation)
  → orchestration.run_onboarding_validation(ctx, ...)
    → workflow.validation.run_onboarding_validation(...)
      → storelevelvalidation(prod_summary=ctx.store_agg, ...)
      → generate_file_review(...)  [calls aggregator only if no pre-computed summaries]
    → results stored on ctx

UI Phase 6 (Reports)
  → output.generate_onboarding_output(ctx)
    → OutputResult populated from ctx fields

UI Phase "Start Over"
  → _reset_phase() → workflow.flush.flush()
```

### Existing / Format Change (two-sided)

```
UI Phase 4 (Processing)
  → orchestration.run_existing_processing(ctx, source)
    → ExecutionEngine.run(ctx, source)
      → checks all 4 aggs — skips if cached
      → FormatChangeWorkflowOp.execute(op_ctx)
        → 2× ParseOptions + 2× ColumnMapping
        → ThreadPoolExecutor(4) — BAU store, Test store, BAU item, Test item
        → results on ctx.prod.store_agg, ctx.test.store_agg, ctx.prod.item_agg, ctx.test.item_agg

UI Phase 5 (Validation)
  → orchestration.run_existing_validation(ctx, ...)
    → workflow.validation.run_existing_validation(...)
      → storelevelvalidation(prod_summary=ctx.prod.store_agg, test_summary=ctx.test.store_agg, ...)
      → run_item_validation(bau_summary=ctx.prod.item_agg, test_summary=ctx.test.item_agg, ...)
      → generate_file_review(...)
    → results stored on ctx
```

## Dependency Diagram

```
workflow/
  orchestration.py  ───→ operations/orchestration.py ───→ workflow/execution.py
  execution.py      ───→ operations/orchestration.py
  canonical.py      ───→ _parsers.py
  processing.py     ───→ _aggregators.py, workflow/canonical.py
  validation.py     ───→ validation/store.py, validation/item.py, _reports.py
  output.py         ───→ workflow/schema_comparison.py, workflow/migration_report.py
  flush.py          ───→ datasource/manager.py, _observability.py

operations/
  base.py           ───→ polars
  registry.py       ───→ operations/base.py
  orchestration.py  ───→ operations/registry.py
  workflow_ops.py   ───→ workflow/processing.py

_parsers.py         ───→ datasource/base.py, config.py
_aggregators.py     ───→ _parsers.py, workflow/canonical.py

validation/
  store.py          ───→ calculations/core.py
  item.py           ───→ calculations/core.py
```

## Object Lifecycle

1. **ProcessingContext** / **ExistingContext** — created in `st.session_state`, lives for one workflow execution
2. **DiscoveryResult** — created once in `_phase1_discovery()`, applied to context
3. **CanonicalDataset** — created per operation level, streamed, not held in memory
4. **ParseOptions** / **ColumnMapping** — built from context, passed through Operation Layer
5. **store_agg** / **item_agg** DataFrames — held on context, consumed by Validation and Output
6. **OutputResult** — built once, rendered by UI, discarded after render
7. **Flush** — called on "Start Over" or phase reset, releases all DataFrames + connections

## ExecutionEngine

Location: `workflow/execution.py`

```python
class ExecutionEngine:
    def run(self, ctx, source=None):
        # Determine workflow type from context shape
        # Check cached results (store_agg, item_agg)
        # Dispatch pending operations via OperationExecutor
```

The Engine replaces hard-coded orchestration functions. Workflow calls only `run()`.

## Plugin Registry

Location: `operations/registry.py`

Two registries:
- **Data Operations** (`IDataOperation`): Filter, Sort, Sample, Statistics, Export, Preview, Aggregate
- **Workflow Operations** (`WorkflowOperation`): AggregateWorkflowOp, FormatChangeWorkflowOp

Adding a new workflow operation:
1. Create class implementing `WorkflowOperation` protocol
2. Register via `register_workflow_op()`
3. No `OperationExecutor` changes needed

## Processing Pipeline

```
CanonicalDataset.iter_chunks()
  → _parsers.canonical_chunk_stream()
    → raw chunk (file-format-specific parser)
    → apply_column_names()
    → normalize_*_chunk() → canonical names
  → _aggregate_*_stream() → group_by + sum
```

Processing never references: CSV, delimiter, encoding, fixed-width, multiline, HDR, layout, record types.

## Violation Status (RC2)

| Violation | Status | Fix |
|-----------|--------|-----|
| BV-1: UI orchestrates business logic | ✅ Fixed (RC1) | UI calls `workflow/orchestration` |
| BV-2: CM performs Detection | ✅ Fixed (RC1) | CM uses only `IDataSource` |
| BV-3: Validation aggregates data | ✅ Fixed (RC2) | Fallback paths removed; validation requires pre-computed summaries |
| BV-4: No Operation Layer | ✅ Fixed (RC1) | `OperationExecutor` is mandatory |
| BV-5: No Output Layer | ✅ Fixed (RC1) | `workflow/output.py` |
| BV-6: Flush Layer never executed | ✅ Fixed (RC1) | Called from `_reset_phase()` |
| BV-7: Config calls parser preview | ✅ Fixed (RC2) | Routed through `workflow/preview.py` |
| BV-8: Physical schema leaks downstream | ✅ Fixed (RC2) | `CanonicalDataset` hides format details; validation uses canonical names only |

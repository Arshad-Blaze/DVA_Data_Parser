# Aggregation Architecture

Store, Item, and UPC aggregation; the two-phase map-reduce algorithm; the Operations
layer dispatch; business rules; and performance characteristics.

---

## 1. Entry Points

### Production path

```
workflow/orchestration.run_onboarding_processing / run_existing_processing
  → ExecutionEngine.run(ctx, source)
  → OperationExecutor.execute(OperationContext(operation_type, ctx, source))
  → AggregateWorkflowOp | FormatChangeWorkflowOp (operations/workflow_ops.py)
  → workflow.processing.run_store_aggregation / run_item_aggregation
  → CanonicalDataset.from_parse_options → _aggregators.aggregate_dataset(dataset)
```

### `aggregate_dataset(dataset, source)` (_aggregators.py:151)

- Requires a `CanonicalDataset` (raises `TypeError` otherwise).
- `stream = dataset.iter_chunks()`, dispatch by `dataset.level`:
  - `store` → `_aggregate_store_stream`
  - `item` → `_aggregate_item_stream`
  - `upc` → `_aggregate_upc_stream`
  - else `ValueError`.

### Legacy entry points

`aggregate(file_paths, file_type, level, ...)` (:25), `stream_store_aggregate` (:325),
`stream_item_aggregate` (:333), `stream_upc_summary` (:342) — used by `_reports.py`
fallback, tests, benchmarks, and golden generation. `aggregate_with_options` (:104) and
`aggregate_with_config` (:171) are **dead code** (no callers).

---

## 2. The Two-Phase Map-Reduce Algorithm

All three level aggregators share the identical shape:

**Phase 1 — per-chunk aggregation:**
```python
for chunk in stream:
    if required_key not in chunk.columns: skip
    base = [pl.sum("Units"), pl.sum("Totalprice")]      # store
    base = [pl.sum("UNITS_SOLD"), pl.sum("TOTAL_DOLLARS")]  # item/upc
    agg = chunk.group_by(keys).agg(base + _extra_agg_exprs(chunk))
    aggs.append(agg); del chunk
```

**Phase 2 — merge and re-aggregate:**
```python
merged = pl.concat(aggs)
rebuilt = [sum expr for cols present in merged]
result = merged.group_by(keys).agg(rebuilt).sort(...)
del merged; gc.collect()
```

Empty stream → empty DataFrame.

`_extra_agg_exprs` (:_220) passes through `QuantityType`, `UOM`, `Date`, `Brand`,
`Category` via `pl.first(...)` when present (standard/enriched templates).

---

## 3. The Three Levels

| Level | Grouping keys | Measures | Sort |
|-------|---------------|----------|------|
| Store (`_aggregate_store_stream`, :229) | `STORE_NUMBER` | `Units`, `Totalprice` | `STORE_NUMBER` |
| Item (`_aggregate_item_stream`, :261) | `[UPC_CODE, PRODUCT_DESCRIPTION]` | `UNITS_SOLD`, `TOTAL_DOLLARS` | `[UPC_CODE, PRODUCT_DESCRIPTION]` |
| UPC (`_aggregate_upc_stream`, :293) | `UPC` | `UNITS_SOLD`, `TOTAL_DOLLARS` | `UPC` |

### Business rules

- **Store aggregation** sums resolved quantity and parsed price per store.
- **Item aggregation** keys on UPC **+ description**; a UPC whose description differs
  between files becomes two rows in comparison.
- **Category / Brand aggregation levels do NOT exist** in the aggregation engine.
  Brand/Category are only pass-through attributes (`pl.first`) on enriched templates,
  and category/brand **rollups** are computed later in the Reporting layer
  (`workflow/output.py::generate_summary_sheets` — `top_brands`, `category_summary`
  grouped by `PRODUCT_DESCRIPTION`).

---

## 4. Parallel Dispatch

| Operation | Workers | Work submitted |
|-----------|---------|----------------|
| `AggregateWorkflowOp` (onboarding) | `ThreadPoolExecutor(max_workers=2)` | store agg + item agg |
| `FormatChangeWorkflowOp` (existing) | `ThreadPoolExecutor(max_workers=4)` | prod store, test store, prod item, test item |

Each future has a **600-second timeout** in FormatChangeWorkflowOp. Results assigned to
`ctx.store_agg` / `ctx.item_agg` (per side for existing). Metric labels are stale
("stream_store_aggregate" etc. — actual path is `aggregate_dataset`).

---

## 5. Operations Layer Dispatch

- `OperationContext(operation_type, ctx, source)` — `operation_type` ∈ `aggregate`,
  `format_change`.
- `OperationExecutor.execute(op_ctx)` → `registry.get_workflow_op(operation_type)` →
  `WorkflowOperation.execute(op_ctx)`. No hard-coded if/elif.
- Registered at import time in `operations/__init__.py`.

The ExecutionEngine only checks **cache state** (`store_agg is None or item_agg is
None`) to decide whether to dispatch — it never decides *what* to compute.

**Finding:** Data operations `Statistics/Filter/Sort/Sample/Export/Preview` are
registered but **not invoked in any production workflow**; only `tests/test_operations.py`
and `validation/store.py:114` (AggregateOperation in `storelevelvalidation_from_df`)
exercise them.

---

## 6. Performance Characteristics

- `_aggregators.py` is **eager-only**; the LazyFrame/streaming lives in
  `_parsers.canonical_chunk_stream`:
  - **Fast path** (delimited + direct-path source): `pl.scan_csv(infer_schema_length=0,
    low_memory=True)` → lazy `with_columns` normalization → single
    `lazy.collect(engine="streaming")`. This is the intended 500 MB+ route.
  - **General/chunk path**: per-type chunk readers, `normalize_*_chunk`, then the
    two-phase map-reduce above.
- Memory: `del chunk`, `del merged`, explicit `gc.collect()`; `print_memory_snapshot`
  before/after; `register_df` per result.
- Remote (SSH): `supports_direct_path` False disables the fast path; rows stream over
  SFTP via `_open_text_stream` in `DEFAULT_CHUNK_SIZE` batches.

---

## 7. Known Defects

| # | Severity | Finding |
|---|----------|---------|
| 1 | Medium | `ParseOptions.chunk_size` is not plumbed into `canonical_chunk_stream` — chunk size always uses module default 100k. |
| 2 | Medium | No category/brand aggregation level despite declared scope; category is modeled as product description in reports. |
| 3 | Medium | `OutputMode` variants (STATISTICS, EXPORT, AGGREGATE_CALCULATE, RAW_REVIEW) are declared but the ExecutionEngine never branches on them. |
| 4 | Medium | Data-operation framework (statistics/export/filter/sort/sample/preview) is unwired production dead code. |
| 5 | Low | `aggregate_with_options` / `aggregate_with_config` dead code. |
| 6 | Low | Stale metric labels in workflow_ops.py. |
| 7 | Low | Near-identical store/item/upc stream aggregators (duplication). |
| 8 | Low | `capabilities` on CanonicalDataset defaults to `{"store","item"}` — no "upc". |

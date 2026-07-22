# Processing Audit

## Layer Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Consumes only CanonicalDataset | ✅ Yes | `processing.py` imports `CanonicalDataset` only |
| No physical column references | ✅ Yes | All columns mapped through mapping object |
| No record type references | ✅ Yes | Record types resolved in parser |
| No delimiter logic | ✅ Yes | Handled in `ParseOptions` → `_parsers` |
| No layout logic | ✅ Yes | Layout used only in parser |
| Chunk processing | ✅ Yes | `iter_chunks()` yields chunks |
| Pre-computed summaries to Validation | ✅ Yes | Store/item aggs passed to validation |

## Aggregation Pipeline

```
CanonicalDataset.iter_chunks()
  → canonical_chunk_stream() in _parsers.py
    → file-format-specific parser
    → apply_column_names()
    → normalize_*_chunk() → canonical names
  → _aggregate_*_stream() → group_by + sum
```

## Data Operations Framework

The `operations/` layer provides:
- `AggregateOperation` — configurable group-by + aggregation functions
- `FilterOperation` — column-based filtering
- `SortOperation` — multi-column sorting
- `SampleOperation` — row sampling
- `StatisticsOperation` — descriptive statistics
- `ExportOperation` — CSV/Excel export
- `PreviewOperation` — data preview

These operate on canonical DataFrames only.

## Workflow Operations

- `AggregateWorkflowOp` — single-side store+item aggregation (onboarding)
- `FormatChangeWorkflowOp` — two-sided 4-way parallel aggregation

## Quantity Resolution Integration

Quantity resolution happens inside the normalizer (`_normalizer.py`) via `_effective_qty_expr()`. This:
- Resolves units vs weight precedence
- Converts weight to pounds
- Applies implied multipliers
- Handles Unit Price → Total Price calculation

## Findings

1. **PA-1: Missing QuantityType in aggregation output** — Aggregators sum Units/Totalprice but don't preserve QuantityType or UOM. This metadata is lost.

2. **PA-2: File review bypasses processing layer** — `_reports.py:generate_file_review()` calls `stream_store_aggregate()` and `stream_upc_summary()` directly. When pre-computed summaries are absent, this re-parses the data.

3. **PA-3: Aggregation levels are fixed** — Only store/item/upc are supported. Adding a new level (e.g., category, brand) requires new aggregator functions.

## Recommendations

1. Add QuantityType and UOM to aggregation pipeline — group by these dimensions or store as metadata
2. Route all aggregation through `workflow/processing.py` — enforce that reports never parse
3. Make aggregation levels configurable — allow user-defined group-by columns

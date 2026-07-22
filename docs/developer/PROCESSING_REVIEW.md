# Processing Layer Review — Sprint 5

## Architecture

The Processing Layer now consumes ONLY a **Canonical Dataset** (pre-normalized
DataFrames with canonical column names) and an **Operation Context** (which
operation to perform and with what parameters).

All file-format details (delimiter, encoding, header, fixed-width, multiline,
retailer schema) are encapsulated behind `canonical_chunk_stream()` in
`dav_tool/_parsers.py`. The Processing Layer (`dav_tool/_aggregators.py`,
`dav_tool/workflow/processing.py`) never sees them.

```
  Parsing Layer                    Processing Layer
  ─────────────                    ────────────────
  _parsers.py                      _aggregators.py
    iter_chunks() ──► raw chunks      _aggregate_store_stream()
    canonical_chunk_stream() ──►      _aggregate_item_stream()
      canonical chunks ──────────►    _aggregate_upc_stream()
                                        │
                                   workflow/processing.py
                                     run_store_aggregation()
                                     run_item_aggregation()
                                     run_raw_review()
                                     run_file_review()
```

## Operation Modes

| Mode | Description | Functions Called |
|------|-------------|-----------------|
| `RAW_REVIEW` | Preview raw canonical data | `canonical_chunk_stream()` → head(n) |
| `AGGREGATE_ONLY` | Store + item aggregation | `stream_store_aggregate()`, `stream_item_aggregate()` |
| `AGGREGATE_CALCULATE` | Aggregation + statistics/calculations | Aggregation + stats operations |
| `VALIDATE` | Full pipeline with validation + reports | Aggregation + validation + file review |
| `STATISTICS` | Aggregation → statistics only | Aggregation + stats, skip reports |
| `EXPORT` | Aggregation → export only | Aggregation + export |

## Duplicate Processing Removed

| Removed Function | Reason | Replacement |
|-----------------|--------|-------------|
| `run_store_aggregation_canonical()` | Dead code — zero callers | Use `run_store_aggregation()` directly |
| `run_item_aggregation_canonical()` | Dead code — zero callers | Use `run_item_aggregation()` directly |
| `_iter_chunks()` in `_aggregators.py` | Moved to `_parsers.py` | `iter_chunks()` in parsers layer |
| `stream_store_aggregate()` 500-line body | Replaced with thin alias | Delegates to `aggregate(level="store")` |
| `stream_item_aggregate()` 500-line body | Replaced with thin alias | Delegates to `aggregate(level="item")` |
| `stream_upc_summary()` 500-line body | Replaced with thin alias | Delegates to `aggregate(level="upc")` |

## Streaming Improvements

- **Canonical chunk stream** replaces the duplicated parsing+normalization+aggregation loops that previously existed in each of the three streaming functions.
- **Fast path** (delimited + simple) still uses `scan_delimited()` + `collect(engine="streaming")` for maximum throughput, embedded inside `canonical_chunk_stream()`.
- **Chunk path** (fixed-width, multiline, remote) uses `iter_chunks()` → `apply_column_names()` → normalizer → yields canonical chunks.
- All `gc.collect()` calls preserved for memory management in chunked mode.

## File Boundary

```
  Before (Sprint 4)                     After (Sprint 5)
  ────────────────                      ────────────────
  _aggregators.py                       _parsers.py
    - file format params                  - iter_chunks()
    - _iter_chunks()                      - canonical_chunk_stream()
    - scan_delimited()                    - (all parser functions)
    - parse_delimited_chunks()
    - parse_fixed_width_chunks()         _aggregators.py
    - flatten_multiline_*()                - _aggregate_*_stream()
    - normalize + aggregate in one         - thin backward-compat aliases
      tightly-coupled function
```

## Measurement

CPU and RAM measurement fields already exist in `ProcessingMetrics`:
- `peak_memory`, `current_memory`
- `peak_cpu`, `current_cpu`
- `aggregation_time`, `parse_time`, `validation_time`, `report_time`

These are populated by the UI layer via `ctx.metrics.record()` and the
Processing Layer emits `register_df()` / `release_df()` calls.

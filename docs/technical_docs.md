# DAV Tool — Technical Documentation

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     UI Layer                         │
│  dav_tool/ui/app.py  (Streamlit entry point)        │
│  dav_tool/ui/onboarding.py                          │
│  dav_tool/ui/existing.py                            │
│  dav_tool/ui/helpers.py                             │
├─────────────────────────────────────────────────────┤
│                   Validation Layer                    │
│  dav_tool/validation/store.py                       │
│  dav_tool/validation/item.py                        │
├─────────────────────────────────────────────────────┤
│                Aggregation Layer                     │
│  dav_tool/_aggregators.py                           │
│  (stream_store_aggregate, stream_item_aggregate,    │
│   stream_upc_summary)                               │
├─────────────────────────────────────────────────────┤
│                   Reports Layer                      │
│  dav_tool/_reports.py                               │
│  (generate_file_review)                             │
├─────────────────────────────────────────────────────┤
│                   Parser Layer                       │
│  dav_tool/_parsers.py                               │
│  (parse_fixed_width_chunks, scan_delimited,         │
│   flatten_multiline_chunks, preview_raw,            │
│   preview_flattened_multiline, load_layout,         │
│   safe_numeric)                                     │
├─────────────────────────────────────────────────────┤
│              Observability Layer                     │
│  dav_tool/_observability.py                         │
│  (ProcessingMetrics, ProcessingTimer)               │
├─────────────────────────────────────────────────────┤
│              Support Modules                         │
│  dav_tool/detection.py    dav_tool/io.py            │
│  dav_tool/config.py       dav_tool/types.py         │
│  dav_tool/processing_context.py                     │
│  dav_tool/_normalizer.py                            │
│  dav_tool/format_config.py                          │
└─────────────────────────────────────────────────────┘
```

### Flow

```
File(s) → Parser Layer (chunked generators)
         → Aggregation Layer (Polars group_by / streaming collect)
         → Validation Layer (join / diff / merge)
         → Reports Layer (per-file summary)
         → UI Layer (Streamlit display)
```

No intermediate files are written. The entire pipeline streams from raw files to results.

---

## Core Modules

### `dav_tool/_parsers.py` — Parser Layer

| Function | Input | Output | Description |
|---|---|---|---|
| `safe_numeric(column)` | Column name | `pl.Expr` | Strips non-numeric chars, casts to Float64, fills nulls with 0 |
| `load_layout(layout_file)` | CSV path | `List[Dict]` | Reads layout CSV and computes 0-indexed start/end positions |
| `parse_fixed_width_chunks(...)` | File paths, layout | `Iterator[pl.DataFrame]` | Reads fixed-width files in chunks, applies record-type filtering |
| `scan_delimited(...)` | File paths, delimiter | `pl.LazyFrame` | Scans delimited files with Polars lazy API, concatenates multiple files |
| `flatten_multiline_chunks(...)` | File paths, record types | `Iterator[pl.DataFrame]` | Strips record-type prefixes from lines, splits by delimiter, yields DataFrames |
| `flatten_multiline_fixed_width(...)` | File paths, header_prefix, header_layout, detail_layout | `Iterator[pl.DataFrame]` | Parses HDR fixed-width files: extracts header fields via header_layout, merges into detail rows via detail_layout, carries header forward to subsequent detail rows |
| `_fields_to_df(buffer)` | `List[List[str]]` | `pl.DataFrame` | Converts list-of-lists to DataFrame with `Column_N` headers |
| `preview_raw(...)` | File paths, type | `pl.DataFrame` | Returns first N rows as-is (delimited splits, fixed-width parses, multiline wraps raw) |
| `preview_flattened_multiline(...)` | File paths, record types | `pl.DataFrame` | Returns first N rows of flattened multiline (delimited) data |
| `preview_flattened_multiline_fixed(...)` | File paths, header_prefix, header_layout, detail_layout | `pl.DataFrame` | Returns first N rows of flattened HDR fixed-width data |

### `dav_tool/_aggregators.py` — Aggregation Layer

Three streaming aggregate functions follow the same pattern:

1. **Delimited path** — uses `scan_delimited` → lazy `with_columns` / `group_by` / `collect(streaming=True)`
2. **Fixed-width path** — iterates `parse_fixed_width_chunks` → rename → numeric cast → group_by → accumulate via `_merge_accumulate*`
3. **Multiline path** — iterates `flatten_multiline_chunks` (delimited) or `flatten_multiline_fixed_width` (HDR fixed-width) → optional column_names rename → same pipeline as fixed-width

All aggregate functions (`stream_store_aggregate`, `stream_item_aggregate`, `stream_upc_summary`) accept optional `header_prefix` and `header_layout` params. When provided for a multiline file, `_iter_chunks` dispatches to `flatten_multiline_fixed_width` instead of `flatten_multiline_chunks`.

| Function | Grouping | Output Columns |
|---|---|---|
| `stream_store_aggregate` | `STORE_NUMBER` | STORE_NUMBER, Units, Totalprice |
| `stream_item_aggregate` | `UPC_CODE, PRODUCT_DESCRIPTION` | UPC_CODE, PRODUCT_DESCRIPTION, UNITS_SOLD, TOTAL_DOLLARS |
| `stream_upc_summary` | `UPC` | UPC, UNITS_SOLD, TOTAL_DOLLARS |

**Helper functions:**

- (Normalization now handled by `dav_tool/_normalizer.py` — `store_normalize_exprs`, `normalize_store_chunk`, `item_normalize_exprs`, `normalize_item_chunk`, `upc_normalize_exprs`, `normalize_upc_chunk`)
- `_merge_accumulate()` — concat + group_by re-accumulation across chunks
- `_iter_chunks()` — dispatches to the correct chunk iterator based on file_type; when `header_prefix` + `header_layout` are provided for multiline, uses `flatten_multiline_fixed_width`

---

## Reports Layer

### `dav_tool/_reports.py`

| Function | Description |
|---|---|
| `generate_file_review(...)` | Iterates each file individually, calls `stream_store_aggregate` and `stream_upc_summary` once per file, and collects per-file stats (store_count, upc_count, total_units, total_dollars) into a DataFrame. |

---

## Validation Layer

### `dav_tool/validation/store.py`

| Function | Description |
|---|---|
| `compare_files(prod, test, col1, col2)` | Returns sets of stores missing in each file (case-insensitive, stripped) |
| `storelevelvalidation(...)` | Streams both BAU and Test through `stream_store_aggregate`, joins on `STORE_NUMBER`, computes diff columns |
| `storelevelvalidation_from_df(...)` | Same logic but accepts pre-loaded DataFrames instead of file paths |

**Percentage formula (`_pct_expr`):**

```
if base == 0 and comp == 0:  0%
if base == 0:               -100%   (all test value is "extra")
if comp == 0:                100%   (all base value is "missing")
otherwise:            (base - comp) / base * 100
```

### `dav_tool/validation/item.py`

| Function | Description |
|---|---|
| `run_item_validation(...)` | Streams both BAU and Test through `stream_item_aggregate`, calls `create_comparison`, returns (comparison_df, summary_df) |
| `create_comparison(bau_df, test_df)` | Full outer join on UPC+Description, classifies rows as "Present in Both", "Present only in BAU", or "Present only in TEST", computes diff columns |

---

## Detection Module

### `dav_tool/detection.py`

| Function | Method |
|---|---|
| `detect_file_type(path)` | Counts delimiter occurrences (comma, pipe, tab, semicolon) across first 5 lines; picks the most frequent |
| `is_multiline_record(path)` | Checks for 2+ different single-letter prefixes (H, D, etc.), 5+ backslash-continuation lines, **or** multi-character alphabetic prefix (e.g. `HDR`) followed by digits in first 10 lines |
| `detect_hdr_prefix(path)` | Scans first 20 lines for multi-character alphabetic prefixes (2+ letters) followed by a digit; returns sorted by length descending |
| `detect_record_types(path)` | Collects unique first-character letters found before a delimiter in first 50 lines |
| `has_header(path)` | If more than half the first-row fields contain alphabetic characters, it's a header |

---

## IO Module

### `dav_tool/io.py`

`safe_read_csv(path)` — tries `pl.read_csv` with UTF-8 first; falls back to Python `csv.reader` with cp1252 encoding.

---

## UI Layer

### `dav_tool/ui/app.py`

Thin entry point that renders the page toggle and dispatches to onboarding or existing page modules.

### State management

All user choices are stored in `st.session_state`:

| Key | Purpose |
|---|---|
| `page` | `"onboarding"` or `"existing"` |
| `onb_ml_rt` | List of record-type prefixes for onboarding multiline |
| `onb_ml_delim` | Multiline delimiter for onboarding |
| `onb_ml_flattened` | Whether multiline flattening has been applied |
| `onb_schema` | Renamed column names |
| `onb_header_prefix` | HDR prefix detected for HDR fixed-width (onboarding) |
| `onb_header_layout` | Loaded header layout for HDR fixed-width (onboarding) |
| `onb_detail_layout` | Loaded detail layout for HDR fixed-width (onboarding) |
| `onb_compare`, `onb_upc`, `onb_file_review` | Validation results |
| `ex_ml_*` | Same as `onb_ml_*` but for existing page |
| `ex_schema_prod`, `ex_schema_test` | Renamed column names for BAU and Test |
| `ex_hdr_prefix_{side}` | HDR prefix for BAU (prod) or Test |
| `ex_hdr_header_layout_{side}` | Header layout for BAU or Test |
| `ex_hdr_detail_layout_{side}` | Detail layout for BAU or Test |
| `store_df`, `comparison_df`, `summary_df`, `compare_result`, `fr_prod`, `fr_test` | Validation results |

---

## Running Tests

```bash
# Unit tests (18 tests)
pytest tests/ -v

# Full integration test (all formats + edge cases)
python full_test.py

# Output
cat /tmp/dav_test_results/full_test_report.txt
```

### Test coverage

- **Delimited** — single file, multi-file, store/item/UPC aggregation
- **Fixed-width** — single file, multi-file, store/item/UPC aggregation, record-type filtering
- **Multiline delimited** — single file, multi-file, H/D record types, schema renaming
- **Multiline fixed-width** — single file, multi-file, record-type filtering, store/item/UPC aggregation
- **HDR fixed-width** — single file, multi-file, header+detail layouts, store/item aggregation, file review
- **File review report** — all file types including HDR fixed-width
- **Implied decimal** — units/100 and dollars/100
- **Unit price mode** — units × unit_price
- **Store validation** — basic, units mismatch, price mismatch
- **Compare files** — perfect match, missing in test, missing in prod, normalization
- **Data loader** — UTF-8, cp1252 fallback
- **Detection** — all delimiter types, fixed-width, excel, multiline, HDR prefix detection, header detection

---

## Extending

### Adding a new file format

1. Add a parser function in `_parsers.py` that yields `pl.DataFrame` chunks
2. Add a branch in `_iter_chunks()` in `_aggregators.py` — or extend the multiline branch to detect new params
3. Add detection logic in `detection.py` (e.g. add a new `detect_*` function and update `is_multiline_record`)
4. Add preview handling in `preview_raw()` in `_parsers.py` and a dedicated `preview_*` function
5. Wire into UI (`onboarding.py` / `existing.py`) with per-side inputs and session state keys
6. Add test data generation and test cases to `full_test.py`

### Adding a new validation

1. Add aggregation logic to `_aggregators.py` or reuse existing `stream_store_aggregate`
2. Add validation/comparison function in `validation/`
3. Wire into `ui/onboarding.py` or `ui/existing.py` with checkbox + results display

---

## Configuration Layer

### `dav_tool/format_config.py`

| Function | Description |
|---|---|
| `FormatConfig` | Dataclass with all parsing settings: file_type, delimiter, layout paths, multiline/HDR/TRL config, column mapping |
| `load_format_config(path)` | Loads a `FormatConfig` from JSON file |
| `save_format_config(config, path)` | Saves a `FormatConfig` to JSON file |
| `apply_format_config(config, ctx, config_dir, file_paths)` | Applies config to a `ProcessingContext` — sets fields, loads layout CSVs (resolved relative to config dir), flattens multiline data, auto-applies schema |
| `config_from_ctx(ctx)` | Builds a `FormatConfig` from a configured `ProcessingContext` (used for saving) |

Layout file paths in the config are resolved relative to the config file's directory (or kept absolute). `apply_format_config` is purely additive — it modifies `ProcessingContext` fields without touching parser/aggregator/validation code.

### Usage flow

```
User provides config JSON → load_format_config() → apply_format_config() → ctx populated
                                                                              ↓
                                                              For multiline: flatten + schema auto-applied
                                                                              ↓
                                                              UI shows preview → user proceeds to column mapping
```

---

## Observability Layer

### `dav_tool/_observability.py`

| Component | Purpose |
|---|---|
| `ProcessingMetrics` | Dataclass with 19 fields: files/rows/chunks/stores/upcs processed, parse/aggregation/validation/report time, peak/current memory, peak/current CPU, warnings, errors |
| `ProcessingTimer` | Context manager that logs STARTED/COMPLETED to terminal, times execution, tracks peak RSS via polling thread, updates `ProcessingMetrics` |
| `setup_logging()` | Configures Python `logging` with `[DVA] [HH:MM:SS] [Phase] message` format to `stderr` |
| `log_phase()` | Structured log line at phase transitions |

### Integration

`ProcessingMetrics` is exposed through `ProcessingContext` (and `ExistingContext`). The UI layer wraps each pipeline call:

```python
with ProcessingTimer(ctx.metrics, "aggregation", "stream_store_aggregate"):
    store_agg = stream_store_aggregate(...)
```

Terminal output:
```
[DVA] [14:30:00] [Phase] stream_store_aggregate STARTED
[DVA] [14:30:04] [Phase] stream_store_aggregate COMPLETED (4.23s, peak=142.1MB)
```

Phase group maps to the tracked time field:
| Phase group | Metric field |
|---|---|
| `aggregation` | `aggregation_time` |
| `validation` | `validation_time` |
| `report` | `report_time` |
| `parse` | `parse_time` |

---

## Benchmark Suite

Located in `benchmarks/`.

| Module | Purpose |
|---|---|
| `benchmarks/data_gen.py` | Generates CSV test data at target byte sizes (100 MB, 500 MB, etc.) |
| `benchmarks/runner.py` | Times execution and tracks peak RSS via polling thread |
| `benchmarks/report.py` | Formats `StageResult` into tables |

### Running

```bash
python3 run_benchmarks.py          # Full suite (100 MB, 500 MB)
python3 run_benchmarks.py --size 100  # Single size
python3 run_benchmarks.py --quick     # Quick smoke test (50 MB)
```

### Measured stages

- `stream_store_aggregate`
- `stream_item_aggregate`
- `generate_file_review`
- `storelevelvalidation`

### Metrics

| Metric | Source |
|---|---|
| Elapsed time | `time.perf_counter()` |
| Peak RSS | `psutil.Process().memory_info().rss` (10 ms polling) |
| Rows/sec | Total rows / elapsed time |

---

### Configuration

Centralized in `dav_tool/config.py`:

| Variable | Default | Used By |
|---|---|---|
| `DEFAULT_ENCODING` | `"cp1252"` | `detection.py`, `io.py` |
| `FALLBACK_ENCODING` | `"utf8-lossy"` | `_parsers.py`, `io.py`, `ui/helpers.py` |
| `DEFAULT_CHUNK_SIZE` | `100_000` | `_parsers.py` |
| `DEFAULT_PREVIEW_ROWS` | `20` | `_parsers.py` (preview functions) |
| `DELIMITERS` | `[",", "\|", "\t", ";"]` | `detection.py` |
| `MULTILINE_CHARS` | `",\|\t;"` | (reserved) |
| `DEFAULT_LOG_LEVEL` | `"INFO"` | `_observability.py` |

### Polars version compatibility

- Uses `.str.strip_chars()` (Polars 1.x) — not `.str.strip()`
- Uses `how="full"` for joins — not `how="outer"`
- Streaming: `collect(engine="streaming")` on `LazyFrame`

---

## Large Dataset Validation

Benchmarked on a machine with 3.7 GB RAM (1 GB available). Tests at 50 MB, 100 MB, 200 MB, and 500 MB.

### Single File Results

| Size | Rows | Store Agg | Item Agg | File Review | Validation | Total | Peak RSS | Rows/s |
|------|------|-----------|----------|-------------|------------|-------|----------|--------|
| 50 MB | 806,597 | 0.66s | 0.95s | 1.19s | 1.22s | 4.02s | 148.6 MB | 200,796 |
| 100 MB | 1,613,194 | 1.24s | 2.01s | 2.21s | 2.06s | 7.51s | 219.2 MB | 214,778 |
| 200 MB | 3,226,388 | 2.28s | 4.25s | 4.74s | 4.68s | 15.95s | 370.5 MB | 202,281 |
| 500 MB | 8,065,970 | 8.03s | 15.23s | 11.81s | 11.79s | 46.86s | 799.1 MB | 172,140 |

### Folder (multi-file) Results

| Size | Files | Store Agg | File Review | Total | Peak RSS | Rows/s |
|------|-------|-----------|-------------|-------|----------|--------|
| 50 MB | 8 | 0.58s | 1.45s | 2.02s | 112.2 MB | 398,713 |
| 100 MB | 16 | 1.15s | 3.22s | 4.37s | 147.1 MB | 369,152 |
| 200 MB | 20 | 2.76s | 8.13s | 10.88s | 311.5 MB | 296,434 |
| 500 MB | 20 | 5.91s | 13.01s | 18.92s | 497.2 MB | 426,320 |

### Observations

- **Scales linearly** with dataset size — throughput stays at ~180K–200K rows/s for single files.
- `stream_item_aggregate` is the bottleneck (~55% of total time), driven by high-cardinality UPC grouping.
- **Peak memory grows sub-linearly** — 50 MB → 148 MB, 500 MB → 799 MB (item_agg peaks at ~1.6× file size).
- **Folder mode is faster** than single-file for equivalent total size (parallel file reads, same streaming).
- **Practical limit** for 3.7 GB RAM machine is ~600–700 MB input (item_agg peaks near 1 GB). Larger datasets require chunking or more RAM.

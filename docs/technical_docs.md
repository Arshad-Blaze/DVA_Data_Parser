# DAV Tool — Technical Documentation

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     UI Layer                         │
│  dav_tool/ui/app.py  (Streamlit entry point)        │
│  dav_tool/ui/connection_manager.py                  │
│  dav_tool/ui/onboarding.py                          │
│  dav_tool/ui/existing.py                            │
│  dav_tool/ui/helpers.py                             │
├─────────────────────────────────────────────────────┤
│                   Workflow Layer                     │
│  dav_tool/workflow/__init__.py (WorkflowPhase,      │
│    WorkflowState, Workflow protocol)                 │
│  dav_tool/workflow/discovery.py (file detection)    │
│  dav_tool/workflow/processing.py (aggregation)      │
│  dav_tool/workflow/validation.py (validation)       │
│  dav_tool/options.py (ParseOptions, ColumnMapping,  │
│    AggregationOptions, ValidationOptions)            │
├─────────────────────────────────────────────────────┤
│                   Datasource Layer                   │
│  dav_tool/datasource/base.py (IDataSource)          │
│  dav_tool/datasource/local.py (LocalDataSource)     │
│  dav_tool/datasource/ssh.py (SSHDataSource)         │
│  dav_tool/datasource/manager.py (singleton)         │
├─────────────────────────────────────────────────────┤
│                   Validation Layer                   │
│  dav_tool/validation/store.py                       │
│  dav_tool/validation/item.py                        │
│  dav_tool/calculations/core.py                      │
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
│  (ProcessingMetrics, ProcessingTimer,               │
│   DataFrame registry)                               │
├─────────────────────────────────────────────────────┤
│              Support Modules                         │
│  dav_tool/detection.py    dav_tool/io.py            │
│  dav_tool/config.py       dav_tool/types.py         │
│  dav_tool/processing_context.py                     │
│  dav_tool/_normalizer.py                            │
│  dav_tool/format_config.py                          │
│  dav_tool/config_validator.py                       │
│  dav_tool/config_builder.py                         │
└─────────────────────────────────────────────────────┘
```

### Flow

```
Connection → Discovery → Configuration → Config Validation →
Processing → Validation → Reports
```

Each phase has a single responsibility. The Workflow layer orchestrates.
The UI only renders workflow state.

No intermediate files are written. The pipeline streams from raw files to results.

---

## Workflow Layer

The workflow layer owns the lifecycle. UI pages only render workflow state.

| Module | Purpose |
|--------|---------|
| `workflow/__init__.py` | `WorkflowPhase` enum, `WorkflowState` class, `Workflow` protocol |
| `workflow/discovery.py` | File detection, preview, column extraction |
| `workflow/processing.py` | Aggregation orchestration, file review |
| `workflow/validation.py` | Validation orchestration |
| `options.py` | `ParseOptions`, `ColumnMapping`, `AggregationOptions`, `ValidationOptions` |

### WorkflowState

Tracks current phase and provides advance/reset operations:

```python
from dav_tool.workflow import WorkflowState, WorkflowPhase

state = WorkflowState()
state.current_phase  # WorkflowPhase.CONNECTION
state.advance()      # → DISCOVERY
state.advance()      # → CONFIGURATION
state.goto(WorkflowPhase.PROCESSING)
state.reset()        # → CONNECTION
```

---

## Option Dataclasses

Replace parameter explosion with structured configuration:

| Dataclass | Fields | Purpose |
|-----------|--------|---------|
| `ParseOptions` | file_type, delimiter, start_line, record_type, layout, column_names, header/trailer config, multiline config | File parsing configuration |
| `ColumnMapping` | store, upc, description, units, price, price_type, implied_dollars, implied_units | Column name mapping |
| `AggregationOptions` | run_store, run_item, run_upc_summary | What to compute |
| `ValidationOptions` | run_store_validation, run_item_validation, run_compare_store_list, run_summary, run_file_review, store_list_* | What to validate |

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

| Function | Group By | Aggregates | Output Columns |
|---|---|---|---|
| `stream_store_aggregate(paths, file_type, store_col, units_col, price_col, ...)` | `STORE_NUMBER` | `Units = sum(units_col)`, `Totalprice = sum(price_col)` | `STORE_NUMBER`, `Units`, `Totalprice` |
| `stream_item_aggregate(paths, file_type, upc_col, desc_col, units_col, price_col, ...)` | `UPC_CODE`, `PRODUCT_DESCRIPTION` | `UNITS_SOLD = sum(units_col)`, `TOTAL_DOLLARS = sum(price_col)` | `UPC_CODE`, `PRODUCT_DESCRIPTION`, `UNITS_SOLD`, `TOTAL_DOLLARS` |
| `stream_upc_summary(paths, file_type, upc_col, desc_col, units_col, price_col, ...)` | `UPC_CODE`, `PRODUCT_DESCRIPTION` | same as item | same as item (alias) |

**Streaming pattern (shared across all three):**
1. **Fast path** — `source is None or source.supports_direct_path`: `pl.scan_csv()` → LazyFrame → `streaming collection` → single `pl.concat()` → `group_by().agg()`
2. **Chunked fallback** (SSH/remote): `_iter_chunks(paths, file_type, ...)` → each chunk is aggregated in-memory → accumulated via `pl.concat().group_by().agg()`

`aggregate_with_options()` wraps `aggregate()` using `AggregationOptions` to select which aggregations to run.

---

### `dav_tool/validation/store.py` — Store Validation Layer

| Function | Input | Output | Description |
|---|---|---|---|
| `storelevelvalidation(prod_summary, test_summary, ...)` | Two DataFrames (prod, test) | `store_df`, `comparison_df` | Computes store-level diffs, diffs %, tolerance, passes/fails |
| `compare_files(prod, test, prod_col, test_col)` | Two DataFrames + column names | `result` dict | Returns `missing_in_test` and `missing_in_prod` as newline-separated strings |

### `dav_tool/validation/item.py` — Item Validation Layer

| Function | Input | Output | Description |
|---|---|---|---|
| `run_item_validation(prod_item, test_item, ...)` | Two DataFrames (prod, test) | `pl.DataFrame` | Merges BAU/TEST, computes diffs, diff %, tolerance, passes/fails |

---

### `dav_tool/calculations/core.py` — Calculation Engine

Pure functions on Polars DataFrames:

| Function | Purpose |
|---|---|
| `pct_diff(base_col, comp_col)` | Percentage difference with zero-division handling |
| `abs_diff(a_col, b_col, result_col)` | Absolute difference |
| `classify_presence(bau_col, test_col, ...)` | Classify rows as present in BAU, TEST, or Both |
| `full_join_with_coalesce(left, right, on, suffix, fill_value)` | Full outer join with null-fill |
| `store_diffs(prod, test)` | Store-level diffs between prod/test summaries |
| `item_comparison(bau, test)` | Item-level comparison between BAU/test summaries |

---

### `dav_tool/_reports.py` — Reports Layer

| Function | Input | Output | Description |
|---|---|---|---|
| `generate_file_review(paths, file_type, store_col, upc_col, units_col, price_col, ...)` | Config + precomputed aggregates | `pl.DataFrame` | Per-file: rows, stores, UPCs, units, sales, anomalies |

---

## Datasource Layer

| Module | Class | Purpose |
|---|---|---|
| `datasource/base.py` | `IDataSource` (ABC) | Interface: `open_stream()`, `list_dir()`, `exists()`, `is_file()`, `is_dir()`, `download_if_required()` |
| `datasource/local.py` | `LocalDataSource` | Local filesystem access |
| `datasource/ssh.py` | `SSHDataSource` | SFTP over paramiko |
| `datasource/manager.py` | `get_active_source()`, `connect_local()`, `connect_ssh()`, `disconnect()` | Singleton manager for current source |

---

## Observability

### ProcessingMetrics

Tracks per-run stats: files, rows, stores, UPCs, chunks, timing (parse/aggregation/validation/report), memory (peak/current), CPU, warnings, errors.

### ProcessingTimer

Context manager that starts a memory-monitoring thread and records elapsed time + peak memory to `ProcessingMetrics`.

### DataFrame Registry

Tracks all DataFrames created during processing:

```python
from dav_tool._observability import register_df, release_df, log_dataframe_summary

register_df(df, "store_agg", owner="processing", phase="aggregation")
log_dataframe_summary()  # prints current registry
release_df(df, name="store_agg")  # unregisters + GC
```

---

## Configuration

### FormatConfig

Serializable file format description. Sections: General, File, Schema, Business Rules, Validation, Output.

### ValidationConfig

Per-validation settings: `store_validation`, `item_validation`, `compare_store_list`, `file_review`. Each has `required_columns`, `group_by_columns`, `aggregation_columns`.

### ConfigValidator

Progressive validation of config completeness.

---

## Test Suite

```
tests/
├── unit/           # 120+ unit tests (fast, isolated)
├── integration/    # Integration tests (file I/O, real data)
├── e2e/            # End-to-end workflow tests
└── conftest.py     # Shared fixtures
```

Run: `pytest tests/unit tests/integration -q` (fast)
Run: `pytest tests/ --ignore=tests/e2e -q` (all non-e2e)

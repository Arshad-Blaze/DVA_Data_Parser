# Flow Summary — DVA Data Parser

## Architecture Layers

```
Presentation Layer (Streamlit UI)
        ↓
Workflow Engine (onboarding.py / existing.py)
        ↓
Data Source Layer (datasource/{base,local,ssh,manager}.py)
        ↓
Discovery Engine (detection.py)
        ↓
Configuration Builder (config_builder.py → format_config.py)
        ↓
Configuration Validator (config_validator.py)
        ↓
Streaming Parser (_parsers.py)
        ↓
Canonical Normalizer (_normalizer.py)
        ↓
Aggregation Engine (_aggregators.py)
        ↓
Validation Layer (validation/store.py, validation/item.py)
        ↓
Calculation Engine (calculations/core.py)
        ↓
Reports (_reports.py)
        ↓
Observability (_observability.py)  ← cross-cutting
```

---

## Entry Point

| Layer | File | Input | Output |
|-------|------|-------|--------|
| CLI | `__main__.py` | `python -m dav_tool` | Launches `streamlit run dav_tool/ui/app.py` |
| UI Router | `ui/app.py` | Streamlit render | Connection Manager + Onboarding/Existing buttons |

---

## Data Source Layer

### Interface: `datasource/base.py`

| Method | Input | Output |
|--------|-------|--------|
| `connect()` | connection params | `bool` |
| `disconnect()` | — | `None` |
| `list_directory(path)` | remote/local path | `List[DataSourceEntry]` |
| `list_files(path)` | remote/local path | `List[str]` of file paths |
| `read_sample(path, n)` | path + row count | `str` (raw text, n lines) |
| `open_stream(path)` | path | `BinaryIO` (remote streaming) |
| `download_if_required(path)` | path | local `str` path |
| `exists(path)` | path | `bool` |
| `stat(path)` | path | `dict` (size, modified) |
| `get_server_info()` | — | `dict` (platform, hostname) |

### Local Implementation: `datasource/local.py`

| Method | Mechanism |
|--------|-----------|
| `supports_direct_path` | `True` — enables Polars native streaming |
| `list_files()` | `glob.glob()` |
| `read_sample()` | `open()` first N lines |
| `open_stream()` | `open(path, "rb")` |

### Remote Implementation: `datasource/ssh.py`

| Method | Mechanism |
|--------|-----------|
| `supports_direct_path` | `False` — forces chunked streaming |
| `connect()` | `paramiko.SSHClient.connect()` |
| `list_directory()` | `sftp.listdir_attr()` |
| `open_stream()` | `sftp.open(path, "rb")` — no local download |
| `read_sample()` | `sftp.open()` → read N lines → close |
| `download_if_required()` | `sftp.get()` → `tempfile.NamedTemporaryFile` |

### Manager: `datasource/manager.py`

- Singleton: `_ACTIVE_SOURCE: Optional[IDataSource]`
- `connect_local()` → creates `LocalDataSource`, stores globally
- `connect_ssh(host, port, username, password/key)` → creates `SSHDataSource`, stores globally
- `get_active_source()` → returns current source (used by every downstream layer)
- `is_connected()` → bool

---

## Discovery Engine: `detection.py`

| Function | Input | Output |
|----------|-------|--------|
| `detect_file_type(path)` | file path | `("delimited", ",")` or `("fixed", None)` or `("excel", None)` |
| `is_multiline_record(path)` | file path | `bool` — checks 3 patterns (single-letter prefixes, backslash continuations, HDR alpha+digit) |
| `detect_hdr_prefix(path, sample_lines=20)` | file path | `List[str]` of HDR prefixes sorted by length desc |
| `detect_record_types(path, delimiter, sample_lines=50)` | file path + optional delim | `List[str]` of unique first-character prefixes |
| `has_header(path, delimiter)` | file path + delimiter | `bool` — `True` if >50% of first-row fields contain alpha chars |

**Only reads first 5–50 lines. No full file scan.**

---

## Configuration Builder: `config_builder.py`

### `build_config(file_paths, file_type, delimiter, ...)` → `FormatConfig`

**Input:**
- Source file paths
- Optional overrides (file_type, delimiter, layouts)
- `source: Optional[IDataSource]` (uses `get_active_source()` if None)

**Process:**
1. If remote source: download sample (100 rows) to local temp file
2. `_detect_encoding()` — tries `[cp1252, utf-8, utf8-lossy, latin-1]`
3. Detect file type via `detection.py` functions
4. For multiline: detect HDR prefix or record types
5. Load sample data via parser (Polars `read_csv(n_rows=100)` or `preview_raw`)
6. `_infer_data_types()` — map column → Polars dtype string
7. `smart_column_indices()` — find best column mapping by synonym matching
8. Set suggested mapping (store_col, upc_col, desc_col, units_col, price_col)

**Output:** `FormatConfig` with detected fields populated

### Progressive Stage Builders

| Builder | Stage | What it detects |
|---------|-------|-----------------|
| `build_file_info_section()` | A | file_type, delimiter, encoding, has_header |
| `build_record_info_section()` | B | multiline record types, HDR prefix |
| `build_schema_section()` | C | column names, data types, suggested column mapping |
| `build_business_rules_section()` | D | store_col, upc_col, desc_col, units_col, price_col, price_type |

### `FormatConfig` Dataclass: `format_config.py`

**6 Sections:**

| Section | Key Fields |
|---------|------------|
| GENERAL | `version`, `name` |
| FILE | `file_type`, `encoding`, `has_header`, `delimiter`, `start_line`, `record_type`, `layout_file`, `header_prefix`, `header_layout_file`, `detail_layout_file`, `trailer_prefix`, `trailer_layout_file`, `ml_record_types`, `ml_delimiter` |
| SCHEMA | `schema`, `detected_columns`, `detected_data_types`, `suggested_mapping` |
| BUSINESS_RULES | `store_col`, `upc_col`, `desc_col`, `units_col`, `price_col`, `price_type`, `implied_dollars`, `implied_units` |
| VALIDATION | `validation_config` (store_validation, item_validation, compare_store_list, file_review — each with enabled, group_by_columns, aggregation_columns) |
| OUTPUT | `output_config` (format, include_file_review, include_validation_details) |

**Methods:**
- `mark_section_complete(section)` / `section_complete(section)` — tracks progressive stages
- `next_incomplete_section()` → returns the next section to configure
- `is_config_complete()` → bool
- `save_format_config(cfg, path)` → JSON
- `load_format_config(path)` → FormatConfig from JSON
- `apply_format_config(config, ctx, config_dir)` → populates `ProcessingContext` from config

---

## Configuration Validator: `config_validator.py`

| Function | Input | Output |
|----------|-------|--------|
| `validate_config(cfg)` | `FormatConfig` | `List[str]` (empty = valid) |
| `validate_section(cfg, section)` | `FormatConfig` + `ConfigSection` | `List[str]` (section-specific errors) |
| `assert_config_valid(cfg)` | `FormatConfig` | Raises `ConfigValidationError` if invalid |

**Validation rules:**
- GENERAL: `file_type` required
- FILE: fixed-width requires `layout_file`; multiline requires header+detail layouts or `ml_record_types`
- SCHEMA: at least one of `schema` or `detected_columns` must exist
- BUSINESS_RULES: all 5 column mappings required, must exist in schema
- Checks mapped columns exist in detected columns

---

## Streaming Parser: `_parsers.py`

| Function | Input | Output | Mechanism |
|----------|-------|--------|-----------|
| `scan_delimited(paths, delimiter)` | file paths + delimiter | `pl.LazyFrame` | Polars `scan_csv()` — lazy, never materializes |
| `parse_delimited_chunks(paths, delimiter, chunk_size)` | file paths + delimiter + source | `Iterator[pl.DataFrame]` | `csv.reader` 100K-row chunks; opens remote stream if source provided |
| `parse_fixed_width_chunks(paths, layout, start_line, record_type, chunk_size)` | paths + layout spec + source | `Iterator[pl.DataFrame]` | Line-by-line, extract by start/end positions, 100K-row chunks |
| `flatten_multiline_chunks(paths, record_types, delimiter, chunk_size)` | paths + record type prefixes + source | `Iterator[pl.DataFrame]` | Strip prefix, split by delimiter, 100K-row chunks |
| `flatten_multiline_fixed_width(paths, header_prefix, header_layout, detail_layout, chunk_size, trailer_prefix)` | paths + HDR layouts + optional trailer + source | `Iterator[pl.DataFrame]` | Header fields carried forward → merged into detail rows; trailer flushes buffer |

**Preview functions** (first N rows, no streaming):
- `preview_raw()` — reads N rows of raw file (delimited/fixed/multiline)
- `preview_flattened_multiline()` — flattens N rows of multiline delimited
- `preview_flattened_multiline_fixed()` — flattens N rows of HDR fixed-width

**Streaming via `_open_text_stream()`:**
- If `source` is provided: `source.open_stream(path)` → `TextIOWrapper` (no download)
- If local fallback: `open(path, "r")`

---

## Canonical Normalizer: `_normalizer.py`

### Store Level

| Function | Input Columns | Output Columns |
|----------|---------------|----------------|
| `store_normalize_exprs(store_col, units_col, price_col, implied_units, implied_dollars, price_type)` | source columns | `STORE_NUMBER` (str), `Units` (f64), `Totalprice` (f64) |
| `normalize_store_chunk(chunk, ...)` | chunk DataFrame | same canonical columns |

Transformations:
- `safe_numeric()` strips non-numeric chars, casts to f64
- `implied_units/implied_dollars`: divide by 100
- `price_type == "Unit Price"`: multiply Units × Unit Price → Total Price

### Item Level

| Function | Input Columns | Output Columns |
|----------|---------------|----------------|
| `item_normalize_exprs(upc_col, desc_col, units_col, dollars_col, implied_units, implied_dollars)` | source columns | `UPC_CODE` (str), `PRODUCT_DESCRIPTION` (str), `UNITS_SOLD` (f64), `TOTAL_DOLLARS` (f64) |

### UPC Level

| Function | Input Columns | Output Columns |
|----------|---------------|----------------|
| `upc_normalize_exprs(upc_col, units_col, dollars_col, implied_units, implied_dollars)` | source columns | `UPC` (str), `UNITS_SOLD` (f64), `TOTAL_DOLLARS` (f64) |

### General
- `apply_column_names(df, column_names)` — renames positional columns to schema names (used for multiline flattened data)

---

## Aggregation Engine: `_aggregators.py`

### Entry Points

| Function | Input | Output |
|----------|-------|--------|
| `aggregate(file_paths, file_type, level, column_mappings..., config...)` | all parsing params + aggregation level (`"store"`/`"item"`/`"upc"`) | `pl.DataFrame` with canonical aggregated columns |
| `aggregate_with_config(file_paths, file_type, config, level, source)` | paths + type + FormatConfig-like object + level | same (convenience wrapper reads mapping from config) |

### Three Aggregation Levels

| Level | Group-By Columns | Aggregation Columns | Output Columns |
|-------|-----------------|--------------------|----------------|
| `stream_store_aggregate()` | `STORE_NUMBER` | `Units`, `Totalprice` | `STORE_NUMBER, Units, Totalprice` |
| `stream_item_aggregate()` | `UPC_CODE, PRODUCT_DESCRIPTION` | `UNITS_SOLD`, `TOTAL_DOLLARS` | `UPC_CODE, PRODUCT_DESCRIPTION, UNITS_SOLD, TOTAL_DOLLARS` |
| `stream_upc_summary()` | `UPC` | `UNITS_SOLD`, `TOTAL_DOLLARS` | `UPC, UNITS_SOLD, TOTAL_DOLLARS` |

### Dual Path Strategy (per-aggregator)

**Fast Path** (delimited + `source.supports_direct_path == True`):
1. `scan_delimited()` → `pl.LazyFrame`
2. `.with_columns(normalize_exprs)` — column-level expressions
3. `.group_by(...).agg([pl.sum(...)])`
4. `.collect(engine="streaming")` — Polars streaming engine, memory constant

**Chunked Path** (fixed/multiline/remote):
1. `_iter_chunks()` → dispatches to correct chunked parser based on `file_type`
2. For each chunk: `apply_column_names()` → `normalize_*_chunk()` → `group_by().sum()`
3. `_merge_accumulate()` — concatenates all per-chunk aggregations, re-group-bys
4. Calls `del chunk; gc.collect()` on each iteration

### Internal Helpers

| Function | Purpose |
|----------|---------|
| `_iter_chunks(file_paths, file_type, ...)` | Dispatches to correct chunk generator by file type |
| `_merge_accumulate(aggs, group_cols)` | `pl.concat()` + `group_by().sum()` + `del merged; gc.collect()` |
| `_merge_accumulate_item(aggs)` | Same with hardcoded `["UPC_CODE", "PRODUCT_DESCRIPTION"]` |
| `_merge_accumulate_upc(aggs)` | Same with hardcoded `["UPC"]` |

---

## Calculation Engine: `calculations/core.py`

**Pure functions — no I/O, no aggregation, no parsing.**

| Function | Input | Output |
|----------|-------|--------|
| `store_diffs(prod_summary, test_summary)` | Two DataFrames: `STORE_NUMBER, Units, Totalprice` | DataFrame: `STORE_NUMBER, Units_Prod, Totalprice_Prod, Units_Test, Totalprice_Test, Units_Diff, Sales_Diff, Units_Diff_%, Sales_Diff_%` |
| `item_comparison(bau_df, test_df)` | Two DataFrames: `UPC_CODE, PRODUCT_DESCRIPTION, UNITS_SOLD, TOTAL_DOLLARS` | Full outer join + classify_presence + diffs → `UPC_CODE, PRODUCT_DESCRIPTION, BAU Units, TEST Units, BAU Dollars, TEST Dollars, Present In, Units Difference, Dollar Difference, Unit % Difference, Dollar % Difference` |
| `item_summary(comparison_df)` | Item comparison DataFrame | Grouped by `Present In`, sums of diffs |
| `pct_diff(base_col, comp_col)` | Column name strings | Expression: `(base - comp) / base * 100` with zero-division handling (both 0→0, only base 0→-100, only comp 0→100) |
| `abs_diff(a_col, b_col, result_col)` | Column name strings | Expression: `a - b` |
| `classify_presence(bau_col, test_col)` | Column name strings | Expression: `"Present only in BAU"` / `"Present only in TEST"` / `"Present in Both"` |
| `sort_by_diff(df, sort_col, ascending)` | DataFrame + column | Sorted DataFrame |
| `rank_by_diff(df, rank_col, rank_name, ascending)` | DataFrame + column | DataFrame with `Rank` column |
| `apply_tolerance(df, diff_col, tolerance, status_col)` | DataFrame + tolerance threshold | DataFrame with `Status: "Pass"/"Fail"` |

---

## Validation Layer: `validation/store.py`, `validation/item.py`

### `storelevelvalidation()`

**Input:**
- prod/test file paths, types, delimiters, layouts
- Column mappings (store, units, price)
- Price settings (implied dollars/units, price type)
- Optional pre-computed `prod_summary`, `test_summary` DataFrames
- Optional `aggregation_source: IDataSource`

**Process:**
1. If summaries not provided: calls `stream_store_aggregate()` for each side
2. Calls `store_diffs()` from Calculation Engine
3. Records timing

**Output:** Comparison DataFrame with store-level diffs

### `run_item_validation()`

**Input:** Same pattern as store — BAU/Test paths + column mappings + optional pre-computed summaries

**Process:**
1. If summaries not provided: calls `stream_item_aggregate()` for each side
2. `create_comparison()` → `item_comparison()` from Calculation Engine
3. `item_summary()` from Calculation Engine

**Output:** `(comparison_df, summary_df)` tuple

### `compare_files()` (utility)
**Input:** Two DataFrames + column names
**Output:** `{"missing_in_test": "...", "missing_in_prod": "..."}`

---

## Reports: `_reports.py`

### `generate_file_review()`

**Input:**
- file_paths, file_type, column mappings
- File format params (delimiter, layout, etc.)
- Optional `precomputed_store_agg` + `precomputed_upc_summary` DataFrames
- Optional `source: IDataSource`

**Output:** `pl.DataFrame` with columns:
- `filename` — basename of file (or "N files (aggregated)")
- `store_count` — distinct stores
- `upc_count` — distinct UPCs
- `total_units` — sum of units sold
- `total_dollars` — sum of total dollars (rounded to 2dp)

**Two modes:**
1. **Pre-computed** (when store_agg + upc_summary available): single consolidated row, no re-parse
2. **Streaming** (when no pre-computed data): iterates each file, calls `stream_store_aggregate()` + `stream_upc_summary()` per file, releases each after use

---

## Observability: `_observability.py`

### `ProcessingMetrics` Dataclass

| Field | Type | Description |
|-------|------|-------------|
| `parse_time` | float | seconds |
| `aggregation_time` | float | seconds |
| `validation_time` | float | seconds |
| `report_time` | float | seconds |
| `total_execution_time` | float | seconds |
| `files_processed` | int | count |
| `rows_processed` | int | count |
| `stores_processed` | int | count |
| `upcs_processed` | int | count |
| `peak_memory` | float | MB |
| `current_memory` | float | MB |
| `peak_cpu` | float | % |
| `memory_released_mb` | float | MB |
| `chunks_processed` | int | count |
| `warnings` | List[str] | — |
| `errors` | List[str] | — |

### DataFrame Registry
- `register_df(df, name, owner, phase)` — tracks DataFrame for memory debugging
- `unregister_df(name, owner)` — removes from registry
- `release_df(df, name, owner)` — `del df` + `unregister` + `gc.collect()`
- `log_dataframe_summary()` — prints registry snapshot

---

## UI ↔ Backend Sync (Per Phase)

```
PHASE 1 — DISCOVERY
────────────────────────────────────────────────────────────────
UI (onboarding.py)               │ Backend
────────────────────────────────────────────────────────────────
st.text_input("Folder Path")     │
  → get_file_list(path, source)  → datasource/manager.get_active_source()
                                 → IDataSource.list_files(path)
  → is_multiline_record(fp)      → detection.py (reads 10 lines)
  → detect_file_type(fp)         → detection.py (reads 5 lines, scores delimiters)
  → detect_record_types(fp)      → detection.py (reads 50 lines)
  → detect_hdr_prefix(fp)        → detection.py (reads 20 lines)
  → has_header(fp, delim)        → detection.py (reads 1 line)
  → preview_raw(fp, ...)         → _parsers.py (reads 20 rows)
  → build_config(fp, ...)        → config_builder.py (reads 100 rows)
                                 → returns FormatConfig
st.dataframe(preview)            │
st.button("Progressive Config")  │
  → ctx.phase = PHASE_CONFIG     │
  → st.rerun()                   │
────────────────────────────────────────────────────────────────

PHASE 2 — CONFIGURATION (Progressive Wizard)
────────────────────────────────────────────────────────────────
UI (helpers.py)                  │ Backend
────────────────────────────────────────────────────────────────
  → build_config()               → config_builder.py (re-reads 100 samples)
  progressive_config_wizard()    │
    Stage A (GENERAL):           │
      st.selectbox (file_type)   │
      st.checkbox (has_header)   │
      st.button("Confirm")       →
        cfg.mark_section_complete(GENERAL)
    Stage B (FILE):              │
      st.selectbox (delimiter)   │
      st.text_input (layout)     →
        cfg.mark_section_complete(FILE)
    Stage C (SCHEMA):            │
      st.dataframe (columns)     │
      st.text_input (rename)     →
        cfg.mark_section_complete(SCHEMA)
    Stage D (BUSINESS_RULES):    │
      st.selectbox (mapping)     │
      st.radio (price_type)      │
      st.checkbox (implied)      →
        cfg.mark_section_complete(BUSINESS_RULES)
    Stage E (VALIDATION):        │
      st.checkbox (toggles)      →
        cfg.mark_section_complete(VALIDATION)
    Stage F (OUTPUT):            │
      st.selectbox (format)      →
        cfg.mark_section_complete(OUTPUT)
  all_done → ctx.config_locked   │
  → ctx.phase = CONFIG_VAL       │
────────────────────────────────────────────────────────────────

PHASE 3 — CONFIG VALIDATION
────────────────────────────────────────────────────────────────
UI (helpers.py)                  │ Backend
────────────────────────────────────────────────────────────────
  → validate_config_before_processing(cfg)
                                 → config_validator.validate_config(cfg)
                                 → List[str] errors
st.error(errors) │ st.success()  │
st.button("Proceed")            │
  → ctx.phase = PHASE_PROCESS    │
────────────────────────────────────────────────────────────────

PHASE 4 — PROCESSING
────────────────────────────────────────────────────────────────
UI (onboarding.py)               │ Backend
────────────────────────────────────────────────────────────────
ThreadPoolExecutor(max_workers=2)│
  submit(stream_store_aggregate, │ → _aggregators.py → _parsers.py
         paths, type, columns...)│   → _normalizer.py → group_by + sum
  submit(stream_item_aggregate,  │ → same pipeline, item level
         paths, type, columns...)│
  → future.result(timeout=600)   │
  → ctx.store_agg (DataFrame)    │
  → ctx.item_agg (DataFrame)     │
→ ctx.phase = PHASE_VALIDATION   │
────────────────────────────────────────────────────────────────

PHASE 5 — VALIDATION
────────────────────────────────────────────────────────────────
UI (onboarding.py)               │ Backend
────────────────────────────────────────────────────────────────
st.checkbox("Compare Store List")│
st.checkbox("UPC Summary")       │
st.checkbox("File Review")       │
st.button("Validate")            │
  → compare_files()              → store-level compare
  → stream_upc_summary()         → _aggregators.py (UPC level)
  → generate_file_review()       → _reports.py
                                 → uses pre-computed store_agg + upc_summary
                                 when available (no re-parse)
st.dataframe(results)            │
→ ctx.done = True                │
→ ctx.phase = PHASE_REPORTS      │
────────────────────────────────────────────────────────────────

PHASE 6 — REPORTS
────────────────────────────────────────────────────────────────
UI (onboarding.py)               │ Backend
────────────────────────────────────────────────────────────────
  display_execution_summary()    → ctx.metrics (timing, memory, files)
  display_processing_history()   → session_state.execution_history
st.download_button("CSV")        │
st.button("Start Over")          →
  _reset_phase() → del all DataFrames → gc.collect()
────────────────────────────────────────────────────────────────
```

---

## Processing Context: `processing_context.py`

The `ProcessingContext` dataclass is the state object that flows through every phase. It is stored in `st.session_state` and passed between UI phase functions.

### Key Fields by Phase

| Phase | Fields Populated |
|-------|-----------------|
| Initial | `metrics: ProcessingMetrics`, `phase: 0` |
| Discovery | `file_paths`, `file_type`, `delimiter`, `layout`, `record_type`, `columns`, `header_prefix`, `ml_record_types`, `ml_flattened`, `schema` |
| Configuration | `store_col`, `upc_col`, `desc_col`, `units_col`, `price_col`, `price_type`, `implied_dollars`, `implied_units`, `mapping_confirmed`, `config_locked` |
| Processing | `store_agg: pl.DataFrame`, `item_agg: pl.DataFrame` |
| Validation | `compare_result`, `upc_summary`, `file_review`, `done` |

### ExistingContext (two-sided)

Wraps two `ProcessingContext` instances: `prod` and `test`, plus shared `compare_result`, `store_df`, `comparison_df`, `summary_df`.

---

## Configuration Save/Load Cycle

```
UI "Save Config" button
  → config_from_ctx(ctx)       → FormatConfig from ProcessingContext
  → save_format_config(cfg, path) → JSON file
  → st.success()

UI "Load Config" text input
  → load_format_config(path)   → FormatConfig from JSON
  → apply_format_config(cfg, ctx, config_dir, file_paths)
      → sets ctx.file_type, ctx.delimiter, ctx.layout, ctx.schema, etc.
      → flattens multiline data (if applicable)
  → ctx._config_applied = True
  → st.rerun()
```

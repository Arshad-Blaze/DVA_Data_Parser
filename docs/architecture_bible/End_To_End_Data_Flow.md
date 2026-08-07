# End-To-End Data Flow

Exhaustive trace of the entire workflow, stage by stage, from source connection to
cleanup. Verified against source.

## Overview

```
Source (Local/SSH)
 → Connection Manager
 → Discovery
 → Detection
 → Parser Selection
 → Parser
 → Flatten
 → Canonical Dataset
 → Column Mapping
 → Aggregation
 → Validation
 → Report Generation
 → Downloads
 → Cleanup
```

Two flows exist: **Onboarding** (single-sided) and **Format Change / Existing**
(two-sided BAU vs TEST). This document traces both, calling out differences.

---

## Stage 1 — Source Connection

| | |
|---|---|
| **Purpose** | Establish which filesystem the app reads from (local or remote SSH). |
| **Input** | User selection (Local / host+port+user+auth). |
| **Objects** | `IDataSource` (ABC), `LocalDataSource`, `SSHDataSource`, module singleton in `datasource/manager.py`. |
| **Methods called** | `connect_local()` / `connect_ssh(host, port, user, auth...)` → `source.connect()`; `is_connected()`, `get_server_info()`, `get_connection_string()`. |
| **Files used** | `datasource/base.py`, `datasource/local.py`, `datasource/ssh.py`, `datasource/manager.py`, `ui/connection_manager.py`. |
| **Business logic** | `supports_direct_path` (True local, False SSH) later switches the aggregation engine between Polars native streaming and chunked remote reads. |
| **Next stage** | User picks a folder path (`_cm_selected_path` onboarding; `_cm_bau_path` / `_cm_test_path` existing). |

## Stage 2 — Connection Manager

| | |
|---|---|
| **Purpose** | Let the user select the data folders used by both flows. |
| **Input** | Browsed directory from `source.list_directory(...)`. |
| **Objects** | `ConnectionConfig`, `_ACTIVE_SOURCE`/`_ACTIVE_CONFIG`. |
| **Methods called** | `get_file_list`, `list_directory`, `read_sample` (preview), `navigate`, `getcwd` (SSH). |
| **Business logic** | Paths are stored in session state only; files are read later through the active source. |
| **Next stage** | Onboarding/existing read the CM-selected path(s). |

## Stage 3 — Discovery

| | |
|---|---|
| **Purpose** | Detect the structure of the first file in the selected folder. |
| **Input** | `file_paths` (list), active `source`. |
| **Objects** | `DiscoveryResult` (`workflow/discovery.py:48`). |
| **Methods called** | `detect_file(file_paths, source)` → `detection.generate_detection_summary(fp)` on `file_paths[0]`. |
| **Files used** | `workflow/discovery.py`, `detection.py`. |
| **Business logic** | Detects file_type, delimiter, encoding, header, trailer, record types, fixed-width length/layout, multiline structure, candidate columns/keys, confidence. Wired into `ctx.discovery` (onboarding L379, existing L1017). |
| **Outputs** | `DiscoveryResult` with 32 fields + `recommended_parser` + `file_architecture`. |
| **Next stage** | Detection detail below; then configuration. |

## Stage 3a — Detection (detail)

Decision order in `generate_detection_summary` (detection.py:942):

1. `detect_file_type` → extension `.xlsx/.xls` ⇒ `("excel", None)`; else delimiter
   scoring ⇒ `("delimited", best)` or `("fixed", None)` (fixed is the fallback).
2. `is_multiline_record` → if True, `file_type` is **overwritten** to `"multiline"`.
3. `detect_encoding` (byte probe cp1252 → utf-8 → utf8-lossy → latin-1).
4. Fixed: `detect_record_length` → `detect_candidate_layout`.
5. Disclaimer / start-line: `detect_disclaimer_lines` → `detect_start_line`.
6. Fixed: `detect_record_prefix`.
7. Multiline: `detect_hdr_prefix`, `detect_fixed_width_detail_prefixes`,
   `detect_record_types`, `detect_trailer_prefix`.
8. Delimited: `has_header`, columns via `safe_read_csv(n_rows=5)`.
9. Delimited/fixed only: `detect_candidate_keys`, `detect_date_columns`,
   `detect_quantity_columns`, `detect_weight_columns`, `detect_uom_columns`.
10. `compute_confidence_score` + `compute_confidence_breakdown`.

Confidence penalties: fixed −0.30; ambiguous delimiter −0.15; zero-scoring delimiter
−0.30; multiline missing prefixes −0.20 / missing trailer −0.10; no header −0.10.
Excel short-circuits at confidence 1.0.

## Stage 4 — Parser Selection

| | |
|---|---|
| **Purpose** | Pick the parser for the detected structure. |
| **Objects** | `ParserFactory` (`parser/factory.py`), `recommended_parser` string. |
| **Methods called** | `recommend_parser(result)` (discovery.py:20) then `ParserFactory.create(discovery)`. |
| **Selection logic** | 1) `file_type=="multiline"` → `record_based`; 2) `ml_flattened` or (`header_prefix` and `detail_layout`) → `parent_child`; 3) `file_type=="fixed"` → `fixed_width`; 4) `product_master_path` + delimited → `sales_product`; 5) fallback `delimited`. If `recommended_parser` is not registered, factory falls back to `supports()` over registered parsers by priority. |
| **Notes** | `"excel"` is never recommended (ExcelParser only reachable via `supports()`). `sales_product` unreachable via plain detection (product_master_path is never set by detection). |

## Stage 5 — Parser

| | |
|---|---|
| **Purpose** | Convert raw bytes into structured DataFrames. |
| **Input** | `DiscoveryResult`, optional kwargs (chunk_size, column_names...). |
| **Objects** | `BaseParser` subclasses → `ParsedResult`. |
| **Methods called** | `parser.parse(discovery, source=...)`. |
| **Files used** | `parser/{delimited,fixed_width,record_based,parent_child,excel,sales_product}.py`, `_parsers.py` chunk functions. |
| **Business logic** | Delimited/FixedWidth/ParentChild read chunked via `_parsers.py` then `pl.concat` (in-memory result). RecordBased builds a `RecordTree` in memory. Excel uses `pl.read_excel`/openpyxl. SalesProduct optionally left-joins a product master. |
| **Next stage** | Flatten. |

## Stage 6 — Flatten

| | |
|---|---|
| **Purpose** | Convert multi-record (HDR/detail/trailer) structures into row-per-detail flat data. |
| **Objects** | `RecordTree` (record_based), `_parsers.flatten_multiline_chunks` / `flatten_multiline_fixed_width` (parent_child). |
| **Business logic** | Parent context merged into each child detail row; trailers act as transaction boundaries and are discarded. |
| **Note** | The declared `FlattenEngine` (`flatten.py`) is **broken and unused** — it passes a `rejection_collector` kwarg that `_parsers` functions don't accept. |

## Stage 7 — Canonical Dataset

| | |
|---|---|
| **Purpose** | The single Processing input contract; hides all file-format details. |
| **Objects** | `CanonicalDataset` (`workflow/canonical.py:83`), `CANONICAL_SCHEMA_TEMPLATES`. |
| **Methods called** | `CanonicalDataset.from_parse_options(file_paths, parse_opts, mapping, level, source)` (production) OR `from_discovery(...)` (parser-driven path). |
| **Files used** | `workflow/canonical.py`, `_parsers.canonical_chunk_stream`. |
| **Business logic** | `_build_stream()` closes over `canonical_chunk_stream(...)`. Fast path (delimited + direct-path source): `scan_delimited` → lazy `with_columns` normalization → single `lazy.collect(engine="streaming")`. General path: `iter_chunks` → per-type chunk parsers → `normalize_*_chunk` per chunk. |
| **Note** | `schema_template` is used to declare the schema but **not forwarded into the stream** in `from_parse_options`; `from_discovery` streams raw parser output without canonical normalization. |

## Stage 8 — Column Mapping

| | |
|---|---|
| **Purpose** | Map physical columns to canonical roles. |
| **Objects** | `ColumnMapping` (frozen), `ParseOptions`. |
| **Methods called** | `ColumnMapping.from_context(ctx)`; `smart_column_indices` (config_builder) / `detect_candidate_columns` (detection) produce the suggestions shown in the UI. |
| **Business logic** | Physical columns → `STORE_NUMBER` / `UPC_CODE` / `PRODUCT_DESCRIPTION` / units / price. Quantity strategy (auto/prefer_weight/prefer_units/weight_only/units_only), weight UOM, per-row UOM column, price type (Total/Unit), implied dollars/units. |

## Stage 9 — Aggregation

| | |
|---|---|
| **Purpose** | Group canonical data to Store/Item/UPC level. |
| **Objects** | `_aggregators.aggregate_dataset`, `_aggregate_store_stream`, `_aggregate_item_stream`, `_aggregate_upc_stream`. |
| **Methods called** | `run_store_aggregation` / `run_item_aggregation` (workflow/processing.py) — for format_change, 4 in parallel via `ThreadPoolExecutor(max_workers=4)`. |
| **Files used** | `_aggregators.py`, `workflow/processing.py`, `operations/workflow_ops.py`. |
| **Business logic** | Two-phase map-reduce: per-chunk `group_by(keys).agg(sum Units, sum Totalprice)` → `pl.concat` → re-aggregate → sort. Keys: store → `STORE_NUMBER`; item → `[UPC_CODE, PRODUCT_DESCRIPTION]`; upc → `UPC`. |
| **Outputs** | `ctx.store_agg`, `ctx.item_agg` (and per-side for existing). |

## Stage 10 — Validation

| | |
|---|---|
| **Purpose** | Compare BAU vs TEST (existing) or BAU vs store-list (onboarding). |
| **Objects** | `ValidationResult`, `storelevelvalidation`, `run_item_validation`, `compare_files`. |
| **Methods called** | `run_existing_validation(...)` / `run_onboarding_validation(...)` (workflow/validation.py). |
| **Files used** | `validation/store.py`, `validation/item.py`, `calculations/core.py`, `workflow/validation.py`. |
| **Business logic** | Store diff via full-outer-join + coalesce (missing = 0.0 → ±100% diffs). Item comparison full-joins on `[UPC_CODE, PRODUCT_DESCRIPTION]`, classifies `Present In`, computes absolute + % differences. Item summary groups by presence. Validators hard-refuse to aggregate. |
| **Outputs** | `store_df`, `comparison_df`, `summary_df`, `compare_result`, `fr_prod`, `fr_test`. |

## Stage 11 — Report Generation

| | |
|---|---|
| **Purpose** | Produce reportable DataFrames + CSV strings. |
| **Objects** | `OutputResult` (dataclass), `generate_summary_analytics`, `generate_summary_sheets`. |
| **Methods called** | `generate_onboarding_output(ctx)` / `generate_existing_output(ctx)` → `generate_summary_sheets(...)`. |
| **Files used** | `workflow/output.py`, `_reports.py`. |
| **Business logic** | KPI single-row frame (store/UPC counts, totals, top/bottom stores/UPCs, variance, growth, averages, metrics); worksheet frames (top/bottom stores, top UPCs, top brands, category summary, store validation summary). |
| **Outputs** | `OutputResult` with DataFrames + `write_csv()` strings. |

## Stage 12 — Downloads

| | |
|---|---|
| **Purpose** | Let the user download reports. |
| **Methods called** | `st.download_button(..., data=<csv string>, file_name="*.csv")` for UPC summary, file reviews, store compare, item compare, summary. Migration report download is a JSON string. |
| **Note** | **No Excel writer exists.** All downloads are CSV strings. |

## Stage 13 — Cleanup

| | |
|---|---|
| **Purpose** | Release resources on Start Over. |
| **Objects** | `flush(metrics, clear_session, ctx_objects)` (workflow/flush.py:37). |
| **Methods called** | `_flush_temp_files()` → `cleanup_data_access()` → `_flush_connection()` → `_flush_dataframes(ctx_objects)` → `_flush_registry()` → optional `_flush_session_state()` → `gc.collect()`. |
| **Note** | `track_temp_dir` is never called so temp-file flushing is a no-op; `_flush_dataframes` releases known context frames. |

---

## Per-flow variation summary

| Stage | Onboarding | Format Change / Existing |
|-------|-----------|--------------------------|
| Connection | one folder | BAU + Test folders |
| Discovery | one `detect_file` | `detect_file` per side |
| Discovery compare | — | `compare_discovery` |
| Schema compare | — | `compare_schemas` |
| Aggregation | `AggregateWorkflowOp` (2 parallel) | `FormatChangeWorkflowOp` (4 parallel) |
| Validation | store-list compare / UPC summary / file review | store + item validation + summary + file reviews (×2) |
| Reports | `generate_onboarding_output` | `generate_existing_output` + migration report |

---

## Stage 14 — The Data Pipeline (Sprint 3)

The new data-centric pipeline (`dav_tool/pipeline/`) is the target
architecture. It runs the identical chain for every retailer:

```
Connection → Discovery → Dataset Graph → Transformation Planner →
Transformation Engine → Parser Pipeline → Canonical Dataset →
Aggregation → Validation → Reporting
```

| Stage | Contract | Business logic owned |
|-------|----------|----------------------|
| Connection | `ConnectionResult` | active source, resolved paths |
| Discovery | `DiscoveryResult` | file detection ONLY |
| Dataset Graph | `DatasetGraph` | relationships, hierarchy, record types, layout (descriptive only) |
| Transformation Planner | `TransformationPlan` | builds ordered ops — executes nothing |
| Transformation Engine | `TransformedDataset` | header/trailer/metadata removal, flattening, parent replication, joins |
| Parser Pipeline | `ParsedDataset` | interpret transformed fields → parsed result |
| Canonical Dataset | `CanonicalDataset` | normalize to canonical schema |
| Aggregation | `AggregatedDataset` | retailer-agnostic grouping/summaries |
| Validation | `ValidationDataset` | business rules |
| Reporting | `ReportDataset` | downloadable artifacts |

Workflow Engine (`pipeline/engine.py`) only orchestrates: it advances
stages and moves contracts between them. It contains no parsing, validation,
or reporting logic.

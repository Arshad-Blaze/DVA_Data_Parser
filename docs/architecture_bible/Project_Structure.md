# Project Structure

Full map of every package in `dav_tool/`, with purpose, responsibilities, public APIs,
dependencies, inputs and outputs. Line counts approximate the reading size.

```
dav_tool/
├── __init__.py                  (empty)
├── __main__.py                  CLI → streamlit entry
├── config.py                    shared constants
├── options.py                   frozen option dataclasses (ParseOptions, ColumnMapping, ...)
├── processing_context.py        ProcessingContext / ExistingContext
├── detection.py                 (1504) heuristic detection engine
├── format_config.py             FormatConfig serializable config model
├── config_builder.py            sample-based FormatConfig construction
├── config_validator.py          config validation (mode-aware)
├── layout_registry.py           ORPHANED layout registry (dead code)
├── io.py                        safe_read_csv
├── _parsers.py                  (759) low-level chunk parsers + canonical_chunk_stream
├── _normalizer.py               canonical column normalizers (store/item/upc)
├── _numeric.py                  numeric parsing expression pipeline
├── quantity.py                  quantity resolution + UOM→lb
├── _aggregators.py              aggregation engine
├── _reports.py                  file review + summary analytics
├── _observability.py            metrics, df registry, logging, memory snapshots
├── _column_utils.py             column synonym matching
├── rejection.py                 rejection collector (dormant)
├── flatten.py                   FlattenEngine (BROKEN dead code)
│
├── datasource/                  filesystem abstraction
│   ├── base.py                  IDataSource ABC, DataSourceEntry, DataSourceError
│   ├── local.py                 LocalDataSource
│   ├── ssh.py                   SSHDataSource (paramiko)
│   └── manager.py               connection singleton (connect_local/ssh, disconnect)
│
├── workflow/                    orchestration + services
│   ├── __init__.py              WorkflowPhase, WorkflowState, Workflow protocol
│   ├── discovery.py             detect_file → DiscoveryResult, recommend_parser
│   ├── discovery_compare.py     DiscoveryComparison (BAU vs Test metadata)
│   ├── orchestration.py         run_onboarding_processing/_validation, run_existing_*
│   ├── execution.py             ExecutionEngine (operation dispatch)
│   ├── processing.py            run_store/item_aggregation (CanonicalDataset)
│   ├── canonical.py             CanonicalSchema, CanonicalDataset, templates
│   ├── validation.py            run_onboarding/existing_validation → ValidationResult
│   ├── output.py                OutputResult, summary sheets, migration report
│   ├── preview.py               preview wrappers over _parsers
│   ├── data_access.py           DataAccessor strategy (stream/copy)
│   ├── flush.py                 flush() lifecycle cleanup
│   ├── relationship.py          RelationshipEngine (enrich datasets)
│   ├── schema_comparison.py     compare_schemas → SchemaDiff
│   ├── operation_comparison.py  compare_operations → OperationComparison
│   └── migration_report.py      MigrationReport + recommendations
│
├── operations/                  Operation Layer
│   ├── base.py                  OperationResult, IDataOperation, WorkflowOperation
│   ├── registry.py              data-op + workflow-op registries
│   ├── orchestration.py         OperationContext, OperationExecutor
│   ├── workflow_ops.py          AggregateWorkflowOp, FormatChangeWorkflowOp
│   └── aggregate.py             AggregateOperation
│
├── parser/                      Parser contract + factory
│   ├── __init__.py              registers all parsers
│   ├── factory.py               ParserRegistry, ParserFactory
│   ├── base.py                  ParsedResult, BaseParser
│   ├── delimited.py             DelimitedParser
│   ├── fixed_width.py           FixedWidthParser
│   ├── record_based.py          RecordBasedParser (HEB, tree-based)
│   ├── parent_child.py          ParentChildParser
│   ├── excel.py                 ExcelParser
│   ├── sales_product.py         SalesProductParser (join w/ product master)
│   └── record_tree.py           RecordNode, RecordTree
│
├── validation/
│   ├── store.py                 compare_files, storelevelvalidation, _from_df
│   ├── item.py                  run_item_validation, create_comparison
│   └── __init__.py
│
├── calculations/
│   ├── core.py                  pct_diff, classify_presence, store_diffs, item_comparison, item_summary
│   └── __init__.py              re-exports
│
├── certification/
│   ├── runner.py                CertificationRunner (headless QA)
│   ├── datasets.py              fixture generators for retailer_certification/
│   └── __init__.py
│
└── ui/                          Streamlit layer
    ├── app.py                   shell + page switch
    ├── connection_manager.py    DataSource UI + file browser
    ├── onboarding.py            (878) onboarding flow
    ├── existing.py              (1411) format-change flow
    ├── helpers.py               (1070) shared UI helpers + caches
    ├── layout_builder.py        fixed-width layout editor
    ├── certification_suite.py   developer QA harness
    └── __init__.py              (empty)
```

---

## Package-by-package detail

### `dav_tool/ui/` — UI Layer
- **Purpose:** Streamlit screens and shared widget helpers.
- **Responsibilities:** render controls, collect input, session-state caches, progress
  stepper, preview tables, downloads. Mutates `ctx` fields and `ctx.phase`.
- **Public APIs:** `run()` (onboarding/existing), `render_connection_manager()`,
  `render_layout_builder(prefix, ...)`, `render_certification_suite()`, and the helper
  functions in `helpers.py`.
- **Dependencies:** workflow, datasource, format_config, config_validator, _observability,
  _column_utils, io, parser (function-local, `helpers.autoparse_context`).
- **Inputs:** user input + `ProcessingContext`/`ExistingContext`.
- **Outputs:** rendered UI; context mutated; downloads.

### `dav_tool/workflow/` — Workflow Layer
- **Purpose:** owns the pipeline lifecycle and exposes a thin facade to the UI.
- **Responsibilities:** discovery service, orchestration wrappers, ExecutionEngine,
  processing service, validation service, output service, data access strategy, flush.
- **Public APIs:** `detect_file`, `run_onboarding_processing`, `run_existing_processing`,
  `run_onboarding_validation`, `run_existing_validation`, `generate_onboarding_output`,
  `generate_existing_output`, `generate_migration_report`, `flush`, preview wrappers.
- **Dependencies:** detection, _parsers, _aggregators, _normalizer, _reports, options,
  processing_context, operations, parser (via canonical.from_discovery).
- **Inputs:** contexts, DiscoveryResult, ParseOptions/ColumnMapping.
- **Outputs:** aggregated DataFrames, ValidationResult, OutputResult.

### `dav_tool/operations/` — Operation Layer
- **Purpose:** config-driven, registry-dispatched operations between Workflow and
  Processing.
- **Responsibilities:** dispatch by `operation_type`; `aggregate` and `format_change`
  workflow ops run the aggregations (with thread pools); `AggregateOperation` is the
  single registered data operation (consumed by validation).
- **Public APIs:** `OperationExecutor.execute(OperationContext)`, `OperationResult`.
- **Dependencies:** workflow.processing, _aggregators, options.
- **Inputs:** OperationContext (type + ctx + source).
- **Outputs:** mutated ctx aggregation frames.

### `dav_tool/parser/` — Parser Contract Layer
- **Purpose:** uniform parsing contract, registry, factory.
- **Responsibilities:** `ParserFactory.create(discovery)` picks a parser by
  `recommended_parser` then `supports()`; each parser returns `ParsedResult`.
- **Public APIs:** `default_factory`, `register_parser`, `ParsedResult`, `BaseParser`.
- **Dependencies:** _parsers (low-level engine), workflow.discovery (DiscoveryResult).
- **Inputs:** DiscoveryResult.
- **Outputs:** ParsedResult (DataFrame + metadata).

### `dav_tool/_parsers.py` + `io.py` — Parser Engine
- **Purpose:** byte-level chunk readers and the canonical stream.
- **Responsibilities:** `parse_delimited_chunks`, `parse_fixed_width_chunks`,
  `flatten_multiline_chunks`, `flatten_multiline_fixed_width`,
  `canonical_chunk_stream` (fast lazy path + chunked path), previews.
- **Public APIs:** canonical_chunk_stream, iter_chunks, preview_raw, safe_read_csv.
- **Dependencies:** _numeric, _normalizer, quantity, config, datasource.base.
- **Inputs:** file paths + parse/mapping params.
- **Outputs:** iterators of polars DataFrames (raw or canonical).

### `dav_tool/detection.py` — Detection Engine
- **Purpose:** discover file structure.
- **Responsibilities:** file type, delimiter, encoding, header, trailer, record types,
  fixed-width length/layout, multiline decision tree, disclaimer/start line, candidate
  keys/columns, confidence scoring.
- **Public APIs:** `generate_detection_summary`, plus ~28 exported functions.
- **Dependencies:** io, datasource.base, config.
- **Inputs:** file path (+ optional IDataSource).
- **Outputs:** DetectionResult dict (informal) / fields for DiscoveryResult.

### `dav_tool/_normalizer.py`, `_numeric.py`, `quantity.py` — Normalization
- **Purpose:** turn raw rows into canonical columns.
- **Responsibilities:** canonical expressions (`STORE_NUMBER/Units/Totalprice`,
  `UPC_CODE/PRODUCT_DESCRIPTION/UNITS_SOLD/TOTAL_DOLLARS`), numeric parsing pipeline,
  quantity resolution + UOM conversion.
- **Public APIs:** `store_normalize_exprs`, `item_normalize_exprs`, `upc_normalize_exprs`,
  `normalize_*_chunk`, `numeric_parse_expr`, `resolve_quantity`.
- **Inputs/Outputs:** polars expressions/DataFrames.

### `dav_tool/_aggregators.py` — Aggregation
- **Purpose:** group canonical data to Store/Item/UPC level.
- **Responsibilities:** two-phase map-reduce aggregation over the canonical stream.
- **Public APIs:** `aggregate_dataset(dataset)`, `aggregate(...)`, `stream_*` wrappers.
- **Inputs:** CanonicalDataset.
- **Outputs:** aggregated polars DataFrame.

### `dav_tool/validation/` + `dav_tool/calculations/` — Validation & Calculation
- **Purpose:** business-rule comparison.
- **Responsibilities:** store diff, item comparison, item summary, store-list compare.
- **Public APIs:** `storelevelvalidation`, `run_item_validation`, `compare_files`,
  `store_diffs`, `item_comparison`, `item_summary`, `pct_diff`, `classify_presence`.
- **Inputs:** pre-computed summaries (validators refuse to aggregate).
- **Outputs:** comparison DataFrames.

### `dav_tool/_reports.py` + `dav_tool/workflow/output.py` — Reporting
- **Purpose:** report generation.
- **Responsibilities:** file review, summary analytics KPIs, summary sheet frames,
  OutputResult (DataFrames + CSV strings).
- **Public APIs:** `generate_file_review`, `generate_summary_analytics`,
  `generate_*_output`, `generate_summary_sheets`.
- **Inputs:** pre-computed aggregation/validation frames.
- **Outputs:** polars frames + CSV strings for download.

### `dav_tool/datasource/` — Data Access
- **Purpose:** abstract the filesystem (local vs SSH).
- **Responsibilities:** connect/disconnect, list/stat/read/stream/download.
- **Public APIs:** `connect_local`, `connect_ssh`, `disconnect`, `get_active_source`,
  `is_connected`, `get_active_config`.
- **Dependencies:** paramiko (soft), os/glob.
- **Outputs:** file streams, local temp paths, server info.

### `dav_tool/options.py` + `processing_context.py` — Contracts
- **Purpose:** immutable option objects + mutable pipeline state.
- **Responsibilities:** carry parse/mapping/validation options; per-side and two-sided
  context with discovery, mapping, aggregations, results.
- **Public APIs:** `ParseOptions`, `ColumnMapping`,
  `ValidationOptions`, `OutputMode`, `ProcessingContext`, `ExistingContext`.

### `dav_tool/format_config.py` + `config_builder.py` + `config_validator.py` — Configuration
- **Purpose:** persisted/reusable configuration.
- **Responsibilities:** FormatConfig (3-layer schema model), JSON load/save, apply to
  context, sample-based build, mode-aware validation.
- **Public APIs:** `load_format_config`, `save_format_config`, `apply_format_config`,
  `config_from_ctx`, `build_config`, `validate_config`, `validate_section`.

### `dav_tool/_observability.py` — Observability
- **Purpose:** metrics, memory, logging.
- **Responsibilities:** ProcessingMetrics, ProcessingTimer, DataFrame registry,
  `setup_logging`, `log_phase`, `print_memory_snapshot`, `log_dataframe_summary`.
- **Note:** counter fields on ProcessingMetrics are never written in production.

### `dav_tool/certification/` — Certification
- **Purpose:** headless QA across representative retailer datasets.
- **Responsibilities:** run Discovery→Config→Processing→Validation per dataset under
  `retailer_certification/`, compare to expected outputs, generate reports.
- **Public APIs:** `CertificationRunner` (run_all/category/one), `discover_retailer_datasets`,
  `generate_report`.

### `dav_tool/calculations/` — see validation above.

---

## Top-level (repo) structure

| Path | Purpose |
|------|---------|
| `retailer_certification/` | Certified retailer datasets (7+ scenarios) |
| `tests/` | unit tests + golden CSVs + e2e (Playwright) |
| `benchmarks/` | data_gen, runner, report |
| `docs/` | architecture / audit / developer / user documentation |
| `scripts/` | dev scripts |
| `run_e2e_tests.sh`, `run_benchmarks.py`, `full_test.py` | dev entry points |

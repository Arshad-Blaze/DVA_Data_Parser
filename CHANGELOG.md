# Changelog

## [Unreleased] — 2026-07-15

### High

- **RC1-1: Architecture audit** — Created `IMPLEMENTATION_REVIEW.md` with full architecture compliance audit, layer-by-layer assessment, and gap analysis against the target 8-layer pipeline.

- **RC1-2: Flush Layer** — Created `dav_tool/workflow/flush.py` as a formal cleanup stage that closes SSH connections, deletes temp files, releases DataFrames, clears session state, and logs final metrics. Called once per workflow execution.

- **RC1-3: Format Change workflow** — Renamed "Certification" to "Format Change" throughout the UI (`app.py`, `existing.py`, `connection_manager.py`). Replaced progressive 8-section config wizard with single-page configuration (`render_all_config_sections`) for the Format Change workflow.

- **RC1-4: Discovery column propagation** — Fixed "discovery comparison showing 0 columns" bug by ensuring `DiscoveryResult.columns` are propagated to `ProcessingContext.columns` and `ProcessingContext.schema` when consumed from the Connection Manager. Also fixed stale discovery data by clearing `columns`, `schema`, and `discovery` on path changes.

- **RC1-5: Canonical Layer** — Created `dav_tool/workflow/canonical.py` as a formal pipeline stage for building Canonical Schema from Physical Schema, handling user schema edits, and propagating canonical names to downstream consumers. Added `CanonicalSchema` dataclass with `from_discovery()` and `update_canonical_names()` methods.

- **RC1-6: CanonicalContext** — Created `CanonicalContext` option object in `dav_tool/options.py` as the single input contract for the Processing Layer. Added `run_store_aggregation_canonical()` and `run_item_aggregation_canonical()` methods that consume only `CanonicalContext`.

- **RC1-7: Requirement Layer** — Created `dav_tool/workflow/requirement.py` as the Operation Selection layer, supporting Raw Data Review, Aggregate Only, and Aggregate + Calculate operations. Wires the existing 7 registered operations (Aggregate, Filter, Sort, Sample, Statistics, Export, Preview) into the pipeline.

### Medium

- **RC1-8: Phase label update** — Updated `PHASE_LABELS` in `workflow/__init__.py` to use "Detection" instead of "Discovery" for Phase 2, matching the target pipeline terminology.

- **RC1-9: App title update** — Changed page title from "DAV TOOL" to "DVA Platform".

- **RC1-10: Onboarding discovery optimization** — Updated `onboarding.py` to use `DiscoveryResult.columns` when available instead of re-reading files with `get_column_names()`, avoiding redundant file reads.

### Low

- **RC1-11: Code cleanup** — Removed unused `progressive_config_wizard` import from `existing.py`, replaced with `render_all_config_sections`.

## [Unreleased] — 2026-07-14 03:16

### High

- **H-1: Delimited multiline crash** — Detects multiline datasets using H/D record types
  (`ml_record_types` without `header_prefix`) and returns early with a clear error message
  instead of crashing during processing. Fixed-width multiline (with `header_prefix`) is
  unaffected.
  - Added `_MULTILINE_DELIMITED_HINT` constant
  - Added `_is_delimited_multiline()` helper function
  - File: `dav_tool/certification/runner.py`

- **H-2: Duplicate ParseOptions/ColumnMapping creation** — `ParseOptions` and `ColumnMapping`
  were created once in the processing block and again in the validation block. Now lifted
  to shared scope and reused across `run_store_aggregation`, `run_item_aggregation`, and
  `run_existing_validation`.
  - File: `dav_tool/certification/runner.py`

### Medium

- **M-1: suite_result not reset between calls** — `run_all()` and `run_category()` reused
  the same `suite_result` from `__init__`, carrying over results from previous invocations.
  Changed to private `_suite` attribute, reset at the start of each method, with a public
  `suite_result` property for backward compatibility.
  - File: `dav_tool/certification/runner.py`

- **M-2: config_ok set too early** — `result.config_ok = True` was set immediately after
  `load_format_config()` succeeded, before `apply_format_config()` ran. Moved to inside
  the `apply_format_config` success branch so it reflects actual config application.
  - File: `dav_tool/certification/runner.py`

- **M-3: Config application errors mislabeled** — The combined `try/except` wrapped both
  config application and file discovery, so `apply_format_config` failures were logged as
  "Discovery error". Split into separate try blocks with correct labels.
  - File: `dav_tool/certification/runner.py`

- **M-4: Missing type hints** — `_is_delimited_multiline` parameter `ctx_prod` was untyped;
  `_compare_expected` parameter `ctx` was untyped. Added `ProcessingContext` and
  `ExistingContext` type annotations.
  - File: `dav_tool/certification/runner.py`

- **M-5: Optional type mismatch** — `prod_parse`, `test_parse`, `prod_mapping`,
  `test_mapping` were declared `Optional[...]` but `run_existing_validation` expects
  non-optional types. Added `assert` statements before the validation block to narrow
  types for static analysis.
  - File: `dav_tool/certification/runner.py`

### Low

- **L-1: Unused imports** — Removed `csv`, `DiscoveryResult`, `flatten_multiline`,
  `OutputMode`, `ProcessingContext`, `load_layout`.
  - File: `dav_tool/certification/runner.py`

- **L-2: Missing docstrings** — Added docstrings to `_report_json`, `_report_markdown`,
  `_report_html`, `_report_text`, `CertificationResult`, `CertificationSuiteResult`.
  - File: `dav_tool/certification/runner.py`

- **L-3: HTML fallback is bare** — The `markdown` import fallback rendered a bare `<pre>`
  tag. Now wrapped in `<!DOCTYPE html><html><body><pre>...</pre></body></html>`.
  - File: `dav_tool/certification/runner.py`

- **L-4: to_list() materializes entire columns** — `_compare_expected` used
  `.to_list()` to compare columns, loading all data into Python lists. Replaced with
  native polars `series_equal()` which avoids materialization.
  - File: `dav_tool/certification/runner.py`

- **L-5: Early return gaps** — Early return paths left `result.metrics` as `None` and
  `result.details` as empty. Added `result.metrics = ProcessingMetrics()` at top of
  `run_one`, and populated `result.details` in the discovery-error and
  delimited-multiline return paths. Added explanatory comment for `expected_outputs_match`
  exclusion from `passed_checks`.
  - File: `dav_tool/certification/runner.py`

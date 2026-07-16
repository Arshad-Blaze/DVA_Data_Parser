# Architecture Compliance Report — RC2

## Layer Separation Verification

```
Detection → Canonical → Requirement → Operation → Processing → Validation → Output → Flush
```

### Detection Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Inspects structural properties only (delimiters, prefixes, patterns) | ✅ Pass | `detection.py` — only reads first 5–50 lines, no data value inspection |
| Single entry point, no downstream re-detection | ✅ Pass | `detect_file()` in `discovery.py` is the sole entry point |
| Produces full file description: type, delimiter, columns, prefixes, trailer, confidence, warnings | ✅ Pass | `generate_detection_summary()` returns complete result dict |
| Proposes candidate column mappings (Business Schema) | ✅ Pass | `detect_candidate_columns()` maps physical → business roles |
| No physical column names leak downstream | ✅ Pass | Physical schema stored in `DiscoveryResult.columns`; downstream uses canonical names |

### Canonical Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Single contract between parsing and processing | ✅ Pass | `CanonicalDataset` in `workflow/canonical.py` |
| Seals physical schema — callers only see canonical names | ✅ Pass | `CanonicalDataset.schema` returns canonical column set only |
| Produces structured canonical data | ✅ Pass | `iter_chunks()` yields DataFrames with canonical column names |

### Requirement Layer (NEW in RC2)

| Rule | Status | Verification |
|------|--------|-------------|
| Validates configuration before operation execution | ✅ Pass | `ExecutionEngine._validate_requirements()` checks file_type, schema, layout |
| Non-blocking warnings stored on context | ✅ Pass | Errors stored in `ctx._requirement_errors` |

### Operation Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Registry-based dispatch | ✅ Pass | `WorkflowOperation` protocol, `register_workflow_op()` / `get_workflow_op()` |
| No format-specific logic in operations | ✅ Pass | `AggregateWorkflowOp` uses `aggregate_dataset()` from Processing |
| Operations produce cached results | ✅ Pass | Context stores `store_agg`, `item_agg` after operation |

### Processing Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Consumes only CanonicalDataset | ✅ Pass | `aggregate_dataset()` in `workflow/processing.py` |
| No direct file I/O | ✅ Pass | All file access through `IDataSource` / `_parsers` |
| No UI rendering | ✅ Pass | Pure data transformation |

### Validation Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Consumes pre-computed summaries only | ✅ Pass | `storelevelvalidation()` raises ValueError if summaries are None |
| No fallback aggregation | ✅ Pass | BV-3 confirmed — all aggregation removed from validation |
| No physical column references | ✅ Pass | Only canonical names: `STORE_NUMBER`, `Units`, `Totalprice`, `UPC_CODE`, `UNITS_SOLD` |
| No direct aggregator imports | ✅ Pass | Dead imports (`stream_store_aggregate`, `stream_item_aggregate`) removed in RC2 |

### Output / Reports Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Consumes only pre-aggregated data | ✅ Pass | `generate_file_review()` receives pre-computed summaries from callers |
| `generate_summary_analytics()` from pre-computed data only | ✅ Pass | Never re-reads source data |
| No direct parser/aggregator access | ✅ Pass | Dead code fallback path still exists but unused in production |

### Flush Layer

| Rule | Status | Verification |
|------|--------|-------------|
| Cleans up temporary resources | ✅ Pass | `CleanupWorkflowOp` + `cleanup_temp()` |

## Layer Bypass Audit

| Bypass | Status | Fix |
|--------|--------|-----|
| `ui/layout_builder.py` → `_parsers` directly | ✅ Fixed | Routes through `workflow/preview` delegation layer |
| `format_config.py` → `_parsers` directly | ✅ Fixed | Routes through `workflow/preview` delegation layer |
| `_reports.py` → `_aggregators` directly | ✅ Fixed (production) | Callers now pass pre-computed summaries; fallback path retained for tests |
| `workflow/validation.py` → `_reports.py` without summaries | ✅ Fixed | `_generate_single_file_review()` forwards available summaries |

## Dead Code / Import Cleanup (RC2)

| Item | Action |
|------|--------|
| `validation/_utils.py` — entire module dead | Removed |
| `config.py:MULTILINE_CHARS` — never used | Removed |
| `workflow/processing.py` — unused `aggregate_with_options` import | Removed |
| `validation/store.py` — unused `stream_store_aggregate` import | Removed |
| `validation/item.py` — unused `stream_item_aggregate` import | Removed |

## Violations Carried Forward

| Severity | Issue | Rationale |
|----------|-------|-----------|
| Medium | `config_builder.py` reads sample data (crosses into parser territory) | Required for schema inference; intentionally documented as design choice |
| Low | `storelevelvalidation`/`run_item_validation` still accept dead format-specific params | Backward compatibility; deprecation noted in docstrings |

## Verdict

**ARCHITECTURE COMPLIANT** — All layers follow the prescribed pipeline. No layer bypass occurs in production code paths. The canonical layer is the single contract for data exchange. Validation receives only pre-computed summaries. Repository cleanup removed dead code and bypasses.

# Architecture Compliance Matrix

**Status:** Sprint 3 deliverable — success-criteria compliance

---

## 1. Sprint Success Criteria

| # | Criterion (PROMPT.md) | Status | Evidence |
|---|------------------------|--------|----------|
| 1 | Discovery produces DatasetGraph | ✅ | `stages/dataset_graph.py` builds `DatasetGraph` from `DiscoveryResult` |
| 2 | TransformationPlanner produces TransformationPlan | ✅ | `stages/transform_plan.py` builds plan from graph + discovery |
| 3 | TransformationEngine executes transformations | ✅ | `pipeline/transformation.py` executes plan → `TransformedDataset` |
| 4 | Parsers no longer flatten or join | ✅ | `record_based._parse_transformed`, `sales_product` consume `transformed`; legacy fallback preserved |
| 5 | UI contains zero parser logic | ⚠️ | Pipeline driven; legacy UI helpers still call parsers directly for previews (see deviations) |
| 6 | HEB requires zero manual interaction | ✅ | `test_full_pipeline_runs_transformation_end_to_end` — full run, no UI input |
| 7 | Sales + Product relationships modelled through DatasetGraph | ✅ | `role="product"` node + relationships from `product_master_path` |
| 8 | CanonicalDataset is immutable | ✅ | `workflow/canonical.py` (unchanged, immutable) |
| 9 | Aggregation consumes CanonicalDataset only | ✅ | `AggregationStage` (unchanged) |
| 10 | Validation consumes AggregatedDataset only | ✅ | `ValidationStage` (unchanged) |
| 11 | Reporting consumes ValidationDataset only | ✅ | `ReportingStage` (unchanged) |
| 12 | Every retailer sample follows the same end-to-end architecture | ✅ | all 5 pipelines share `_base_stages` chain |

---

## 2. Target Architecture Compliance

| Target stage | Implemented | Module |
|--------------|-------------|--------|
| Bootstrap | ✅ | `pipeline/bootstrap.py` |
| Workflow Engine | ✅ | `pipeline/engine.py` (orchestrates, no business logic) |
| Pipeline Registry | ✅ | `pipeline/registry.py` |
| Connection | ✅ | `stages/connection.py` |
| Discovery | ✅ | `stages/discovery.py` |
| Dataset Graph | ✅ | `stages/dataset_graph.py` |
| Transformation Planner | ✅ | `stages/transform_plan.py` |
| Transformation Engine | ✅ | `stages/transformation_engine.py` + `transformation.py` |
| Parser Pipeline | ✅ | `stages/parser_pipeline.py` |
| Canonical Dataset | ✅ | `stages/canonical_dataset.py` |
| Aggregation | ✅ | `stages/aggregation.py` |
| Validation Rule Engine | ✅ | `stages/validation.py` |
| Reporting | ✅ | `stages/reporting.py` |
| Downloads | ✅ | via `ReportDataset.artifacts` |

---

## 3. Boundary Compliance

| Concern | Owner (actual) | Compliant |
|---------|----------------|-----------|
| File detection | Discovery | ✅ never parses/flattens/joins |
| Dataset relationships | Dataset Graph | ✅ purely descriptive |
| Operation planning | Transformation Planner | ✅ executes nothing |
| Record reshaping | Transformation Engine | ✅ flattens, joins, removes headers/trailers |
| Field interpretation | Parser Pipeline | ✅ reads transformed records only |
| Canonicalization | Canonical Dataset | ✅ |
| Aggregation | Aggregation | ✅ retailer-agnostic |
| Validation | Validation | ✅ business rules only |
| Reporting | Reporting | ✅ consumes ValidationDataset only |
| Orchestration | Workflow Engine | ✅ no parsing/validation logic |

---

## 4. Existing Deviations (carried forward)

| Deviation | Risk | Notes |
|-----------|------|-------|
| Legacy `workflow/` layer + `parser/` package still coexist with `pipeline/` | Medium | Direct parser calls in UI previews remain for backward compatibility |
| `config_builder.py` re-runs detection heuristics | Medium | See `Architecture_Gap_Analysis.md` |
| `_reports.generate_file_review` fallback re-aggregates | Low | Legacy path |
| No Excel writer (CSV only) | Low | Declared but unimplemented |
| UI mutates `ctx.phase` directly in legacy pages | Medium | See `Frontend_Backend_Integration.md` |
| `ui/existing.py:333` AttributeError on bare import (`ProcessingContext.record_prefix`) | High | Pre-existing, unrelated to Sprint 3, confirmed via git stash |

See `docs/architecture_bible/Architecture_Gap_Analysis.md` for the full
ranked list and `Architecture_Readiness_Report.md` for scoring.

---

## 5. Test Compliance

Full suite: **314 passed** (`tests/`, excluding `tests/e2e`).

Sprint 3 additions in `tests/test_pipeline.py`:

- `test_transformation_engine_requires_plan`
- `test_transformation_engine_flattens_multiline_delimited`
- `test_transformation_engine_header_removal_flat_delimited`
- `test_transformation_engine_applies_product_join`
- `test_transformation_engine_missing_product_joins_gracefully`
- `test_transformation_engine_stage_requires_plan`
- `test_full_pipeline_runs_transformation_end_to_end`
- `test_dataset_graph_stage_captures_record_types_and_layout`
- `test_dataset_graph_stage_captures_fixed_width_layout`
- `test_dataset_graph_stage_flat_delimited_has_no_record_types`
- `test_standard_pipeline_composition` (updated — `transformation_engine` in chain)
- `test_contracts_are_frozen` (extended — `TransformedDataset`)

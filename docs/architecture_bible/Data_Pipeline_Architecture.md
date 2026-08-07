# Data Pipeline Architecture

**Status:** Sprint 3 deliverable — data-centric processing pipeline
**Companion docs:** `DatasetGraph_Design.md`, `Transformation_Planner_Design.md`, `Transformation_Engine_Design.md`, `Parser_Simplification_Report.md`, `HEB_Architecture_Report.md`, `Retailer_Compatibility_Report.md`, `Architecture_Compliance_Matrix.md`

---

## 1. Principle

The DVA Platform is **NOT a workflow application**. It is a retailer data
ingestion, transformation and validation platform.

The **Workflow Engine orchestrates** processing.

The **Data Pipeline owns** business logic.

Every piece of business complexity — flattening, joining, header/trailer
removal, parent replication, record selection — lives inside the data
pipeline. The engine only advances stages and moves contracts between them.

---

## 2. Target Architecture

```
Bootstrap
   ↓
Workflow Engine
   ↓
Pipeline Registry
   ↓
Connection
   ↓
Discovery
   ↓
Dataset Graph
   ↓
Transformation Planner
   ↓
Transformation Engine
   ↓
Parser Pipeline
   ↓
Canonical Dataset
   ↓
Aggregation
   ↓
Validation Rule Engine
   ↓
Reporting
   ↓
Downloads
```

Workflow owns orchestration. Data Pipeline owns business logic.

---

## 3. Implementation

The `dav_tool/pipeline/` package implements the target architecture:

| Stage | Module | Contract produced |
|-------|--------|-------------------|
| Connection | `stages/connection.py` | `ConnectionResult` |
| Discovery | `stages/discovery.py` | `DiscoveryResult` (reused from `workflow/discovery.py`) |
| Dataset Graph | `stages/dataset_graph.py` | `DatasetGraph` |
| Transformation Planner | `stages/transform_plan.py` | `TransformationPlan` |
| Transformation Engine | `stages/transformation_engine.py` | `TransformedDataset` |
| Parser Pipeline | `stages/parser_pipeline.py` | `ParsedDataset` |
| Canonical Dataset | `stages/canonical_dataset.py` | `CanonicalDataset` |
| Aggregation | `stages/aggregation.py` | `AggregatedDataset` |
| Validation | `stages/validation.py` | `ValidationDataset` |
| Reporting | `stages/reporting.py` | `ReportDataset` |

All five standard pipelines (`standard_delimited`, `fixed_width`,
`record_based`, `sales_product`, `excel`) compose the **same** stage chain
(`standard_pipelines.py::_base_stages`). Pipelines differ only in the parser
selected for a given `DiscoveryResult` — never in architecture.

### Contract flow

```
ConnectionResult
   ↓
DiscoveryResult
   ↓
DatasetGraph
   ↓
TransformationPlan
   ↓
TransformedDataset
   ↓
ParsedDataset
   ↓
CanonicalDataset
   ↓
AggregatedDataset
   ↓
ValidationDataset
   ↓
ReportDataset
```

Contracts are **immutable** (`frozen=True` dataclasses in
`contracts.py`). No stage can mutate another stage's output.

---

## 4. Data-Centric Boundaries

| Concern | Owner | Must NOT |
|---------|-------|----------|
| File detection | Discovery | Parse, flatten, join, normalize, aggregate, validate |
| Dataset relationships | Dataset Graph | Parse |
| Operation planning | Transformation Planner | Execute anything |
| Record reshaping | Transformation Engine | Parse |
| Field interpretation | Parser Pipeline | Flatten, join, detect relationships, remove disclaimers, ignore trailers, replicate parents |
| Canonicalization | Canonical Dataset | See `Canonical_Architecture.md` |
| Aggregation | Aggregation | Retailer-specific logic |
| Validation | Validation | Parse, UI |
| Reporting | Reporting | Consume Aggregation/Parser objects directly |

---

## 5. Why This Corrects the Audit Gap

The Architecture Audit found orchestration was elegant but the ingestion
pipeline was under-specified — the real business complexity lived inside
Discovery → Parser → Canonical Dataset, and future retailer onboarding would
still require parser complexity.

Sprint 3 moves ALL transformation logic into a dedicated **Transformation
Engine** that executes a **TransformationPlan**. Parsers now read transformed
records only; they never flatten, join, or detect relationships. Every
retailer runs through the identical architecture; only Discovery and the
TransformationPlan differ.

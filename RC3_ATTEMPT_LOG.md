# RC3 Certification Attempt Log

Single living document for RC3 (Architecture Finalization & Retailer Certification).
Each attempt appends one timestamped entry describing intent and outcome.
This replaces the 10 separate OUTPUT DOCUMENTS from PROMPT.md; a single
scorecard section is maintained at the bottom.

---

## Attempt 1 — 2026-08-07

### Intent

Prove every retailer executes the identical 14-stage pipeline and certify all
retailer datasets end-to-end. Instead of emitting ten separate RC3 output
documents, capture the first attempt here and update this same document on
every subsequent attempt with a timestamp and intent.

### Objective

- Finish RC3: Connection → Discovery → Dataset Graph → Transformation Planner →
  Transformation Engine → Parser Pipeline → Canonical Mapping → Quantity
  Resolution → Canonical Dataset → Data Quality → Aggregation → Validation →
  Insights Engine → Reporting → Downloads.
- Only DiscoveryResult / DatasetGraph / TransformationPlan may differ per
  retailer.
- Fix the 4 retailers that failed the new pipeline certification and lock in
  regression coverage.

### Changes Made

1. **HEB (record_based)**
   - `canonical_dataset.py::_canonical_select` now applies `numeric_parse_expr`
     to UNITS_SOLD / WEIGHT_QTY / TOTAL_DOLLARS (record-based path produced
     string dtypes that broke aggregation).
   - `canonical_mapping.py`: alias/substring fallback now requires confidence
     ≥ 0.85, so noisy substring matches (e.g. `Units` → WEIGHT_QTY /
     WEIGHT_UOM) are rejected.
2. **Wholesale (multiline) + Apparel (header_detail)**
   - `parser_pipeline.py`: parsed columns are renamed via
     `user_config.column_names` for all parser types, so Canonical Mapping sees
     business names.
   - `transform_plan.py`: emit a `flatten_fixed_width` plan op when a
     header_prefix plus detail/trailer layouts exist and no hierarchy is
     detected (Apparel previously never flattened).
3. **Pharmacy FW (fixed_width)**
   - `discovery.py::_apply_user_overrides`: a config-provided layout clears the
     detected `candidate_layout` so the real 5-column layout wins over the
     auto-detected 7-column one.

### Outcome

- Pipeline certification: **8/8 retailers pass** (all 14 stages each).
- Full unit suite: **323 passed** (314 baseline + 9 new pipeline-certification
  tests in `tests/test_pipeline_certification.py`).
- Every retailer produces a canonical mapping with confidence, runs data-quality
  checks, emits insight frames, and writes report artifacts.

### Known Gaps / Next Steps

- Scenario 5 (Sales + Product relationship), 14 (large files), 17 (duplicate
  headers), 18 (Excel), 19 (relationship), 20 (future unknown retailer) are not
  backed by dedicated datasets yet — covered via scenario-level datasets.
- Scorecard (per PROMPT.md FINAL SCORECARD) not yet populated.

---

## Scorecard

(Populated on a later attempt.)

# Implementation Plan RC

## Priority Legend
- **P0: Critical** — Blocks core retailer scenarios
- **P1: High** — Required for completeness
- **P2: Medium** — Important for quality
- **P3: Low** — Nice to have

---

## Phase 1: Fixed-Width Record Length & Candidate Layout Detection
**Priority:** P0 — Critical  
**Retailer Scenarios:** Retailer 2 (no layout), Retailer 3 (fixed-width multiline)  
**Architecture Gaps:** G1  
**Files:** `dav_tool/detection.py`, `dav_tool/workflow/discovery.py`

### Implementation
1. Add `detect_record_length(file_path, source)` — scan sample lines for consistent length
2. Add `detect_candidate_layout(file_path, record_length, source)` — propose column positions using:
   - Whitespace pattern analysis
   - Character type transitions (alpha→digit, digit→alpha)
   - Consistent separator characters
3. Store `record_length` and `candidate_layout` on `DiscoveryResult`
4. Update UI Layout Builder to pre-populate from candidate_layout when available

### Effort: 2-3 days
### Risk: Medium — layout proposals may need manual refinement

---

## Phase 2: Disclaimer & Start Line Detection
**Priority:** P1 — High  
**Retailer Scenarios:** Retailer 3 (disclaimer), general  
**Architecture Gaps:** G5  
**Files:** `dav_tool/detection.py`

### Implementation
1. Add `detect_disclaimer_lines(file_path, source)` — find leading non-data lines
2. Add `detect_start_line(file_path, source)` — find first data line after headers/disclaimers
3. Add `detect_record_prefix(file_path, source)` — discover fixed-width record type prefixes (U, D, S, etc.)
4. Store results on `DiscoveryResult`

### Effort: 1-2 days
### Risk: Low

---

## Phase 3: Business Key & Relationship Key Detection
**Priority:** P1 — High  
**Retailer Scenarios:** Sales + Product Master  
**Architecture Gaps:** G2  
**Files:** `dav_tool/detection.py`, `dav_tool/workflow/discovery.py`

### Implementation
1. Add `detect_candidate_keys(columns, sample_data)` — identify columns with:
   - High uniqueness ratio
   - Known patterns (UPC: 12-digit, SKU: alphanumeric patterns)
   - Column name keywords (upc, sku, item_code, product_code)
2. Add `detect_relationship_keys(file_pairs)` — recommend join keys across file sets
3. Add `candidate_keys` and `suggested_joins` to `DiscoveryResult`
4. Add confidence scoring for key recommendations

### Effort: 2-3 days
### Risk: Medium — requires good heuristics for diverse retailer formats

---

## Phase 4: Relationship Engine — Sales + Product Master Join
**Priority:** P1 — High  
**Retailer Scenarios:** Sales + Product Master  
**Architecture Gaps:** G4  
**Files:** New module `dav_tool/workflow/relationship.py`, update `dav_tool/workflow/canonical.py`

### Implementation
1. Create `RelationshipEngine` module:
   - `discover_relationships(detection_results)` — propose joins from detection
   - `confirm_relationship(sales_keys, product_keys, join_type)` — validate join
   - `enrich_dataset(canonical_dataset, product_dataset, join_mapping)` — produce enriched canonical output
2. Add `enrich()` method to `CanonicalDataset`
3. Update UI for relationship configuration:
   - Select Sales file, Product Master file
   - Confirm join keys
   - Select product attributes to include
4. Update Discovery/Canonical pipeline to support two-file workflow

### Effort: 3-5 days
### Risk: Medium-High — new architectural concepts

---

## Phase 5: Dynamic Canonical Schema
**Priority:** P1 — High  
**Architecture Gaps:** G3, G8  
**Files:** `dav_tool/workflow/canonical.py`, `dav_tool/options.py`, `dav_tool/format_config.py`

### Implementation
1. Replace `_build_schema_for_level()` with a configurable schema registry:
   - Pre-defined templates: `minimal` (current), `standard` (+QuantityType, UOM, Date), `enriched` (+Brand, Category)
   - Allow custom column definitions
2. Add `QuantityType` and `UOM` to canonical schema
3. Add Date column to canonical schema when detected
4. Update `_aggregators.py` to handle new canonical columns
5. Update `_normalizer.py` to populate new columns

### Effort: 3-4 days
### Risk: Medium — affects multiple layers

---

## Phase 6: Quantity Engine — UOM & QuantityType Propagation
**Priority:** P1 — High  
**Retailer Scenarios:** Retailer 1 (Mixed Units/Weight, UOM column)  
**Architecture Gaps:** G8  
**Files:** `dav_tool/quantity.py`, `dav_tool/_normalizer.py`, `dav_tool/_aggregators.py`

### Implementation
1. Add `QuantityType` column to normalized output (WEIGHT/UNIT/NONE)
2. Add `UOM` column to normalized output (per-row UOM or default)
3. Update aggregators to:
   - Sum quantities as before
   - Carry QuantityType as metadata
   - Group by UOM or store as first/last value
4. Update canonical schema to include these columns

### Effort: 1-2 days
### Risk: Low

---

## Phase 7: Output Summary Worksheets
**Priority:** P2 — Medium  
**Architecture Gaps:** G9  
**Files:** `dav_tool/workflow/output.py`, `dav_tool/_reports.py`

### Implementation
1. Add to `OutputResult`:
   - `summary_kpis: pl.DataFrame` — key business statistics
   - `top_stores: pl.DataFrame` — top/bottom stores by sales/qty
   - `top_upcs: pl.DataFrame` — top/bottom selling UPCs
   - `category_summary: pl.DataFrame` — category-level aggregation
   - `store_validation_summary: pl.DataFrame` — validation results summary
2. Add `generate_summary_sheets()` to output service
3. Update UI to display summary sheets

### Effort: 2-3 days
### Risk: Low

---

## Phase 8: Move Detection Logic Out of UI
**Priority:** P2 — Medium  
**Architecture Gaps:** G6  
**Files:** `dav_tool/ui/helpers.py`, `dav_tool/workflow/discovery.py`

### Implementation
1. Move `get_column_names()` from `ui/helpers.py` to `workflow/discovery.py`
2. Update all imports to use the workflow version
3. Keep UI helper as a thin wrapper for caching only

### Effort: 0.5 day
### Risk: Low — pure refactor

---

## Phase 9: Route Reports Through Processing Layer
**Priority:** P2 — Medium  
**Architecture Gaps:** G7  
**Files:** `dav_tool/_reports.py`, `dav_tool/workflow/processing.py`

### Implementation
1. Remove direct imports of `stream_store_aggregate` / `stream_upc_summary` from `_reports.py`
2. Add `run_store_aggregation` and `run_item_aggregation` wrappers in `workflow/processing.py` for single-path aggregation
3. Update `generate_file_review()` to require pre-computed summaries (fail early if missing)

### Effort: 1 day
### Risk: Low

---

## Phase 10: Preview Enhancements
**Priority:** P2 — Medium  
**Architecture Gaps:** G10, G11  
**Files:** `dav_tool/workflow/preview.py`, `dav_tool/_parsers.py`

### Implementation
1. Add `preview_canonical()` — run canonical_chunk_stream for small sample with current mapping
2. Add streaming large-file preview using LazyFrame.fetch()
3. Add raw fixed-width preview without layout (show as raw text column)
4. Add quantity/weight resolution preview
5. Update UI to show canonical and relationship previews

### Effort: 1-2 days
### Risk: Low

---

## Phase 11: Dependency Cleanup
**Priority:** P3 — Low  
**Architecture Gaps:** G12  
**Files:** `pyproject.toml`, `requirements-dev.txt`

### Implementation
1. Add version upper bounds: `streamlit>=1.28,<2.0`
2. Add `ruff` to dev dependencies
3. Add `mypy` to dev dependencies
4. Remove `requests` if not used by tests
5. Add linting config (ruff/pyproject.toml)

### Effort: 0.5 day
### Risk: Low

---

## Implementation Order

```
Sprint 1 (Week 1-2):           Sprint 2 (Week 3-4):            Sprint 3 (Week 5-6):
┌─────────────────────┐       ┌─────────────────────┐        ┌─────────────────────┐
│ Phase 1: Fixed-Width│       │ Phase 4: Relation.  │        │ Phase 7: Output Sum. │
│   Detection (P0)    │       │   Engine (P1)       │        │   Worksheets (P2)    │
│ Phase 2: Disclaimer │       │ Phase 5: Dynamic    │        │ Phase 8: Move Det.   │
│   Detection (P1)    │       │   Canonical (P1)    │        │   Logic from UI (P2) │
│ Phase 3: Key        │       │ Phase 6: Quantity   │        │ Phase 9: Reports     │
│   Detection (P1)    │       │   Propagation (P1)  │        │   Layer (P2)         │
└─────────────────────┘       └─────────────────────┘        └─────────────────────┘
                                                              Phase 10: Preview (P2)
                                                              Phase 11: Deps (P3)
```

## Verification Strategy

Each phase should be verified with:
1. Unit tests for new detection/processing logic
2. Integration test with a synthetic file matching the target retailer scenario
3. Manual E2E test through UI workflow
4. Regression: existing retailer scenarios (Retailer 4) must continue to work

# Architecture Gap Report

## Overview
Comprehensive gap analysis of the DVA Data Parser against the Architecture Bible and retailer scenarios.

---

## G1: Detection Does Not Discover Fixed-Width Record Length
**Priority:** High  
**Architecture Impact:** High  
**Business Impact:** High — blocks Retailer 2 (fixed-width, no layout)  
**Files:** `dav_tool/detection.py`, `dav_tool/workflow/discovery.py`  
**Description:** Detection classifies files as "fixed" but does not discover record length or candidate column positions. The UI Layout Builder is required, but for Retailer 2 there is no layout available initially.  
**Recommendation:** Add record-length detection and candidate-layout generation to `detect_file_type()` or `generate_detection_summary()`.  
**Estimated Effort:** 2-3 days

---

## G2: No Business Key / Relationship Key Detection
**Priority:** High  
**Architecture Impact:** High  
**Business Impact:** High — blocks the Sales + Product Master scenario  
**Files:** `dav_tool/detection.py`, `dav_tool/workflow/discovery.py`  
**Description:** Detection has no concept of candidate join keys across file sets. No UPC/SKU/Item Code detection or recommendation.  
**Recommendation:** Add `detect_candidate_keys()` that identifies columns likely to be business keys (high uniqueness, known patterns like UPC, SKU). Add `detect_relationship_keys()` for cross-file analysis.  
**Estimated Effort:** 2-3 days

---

## G3: Canonical Schema Is Static and Limited
**Priority:** High  
**Architecture Impact:** High  
**Business Impact:** Medium — limits business reporting and enrichment  
**Files:** `dav_tool/workflow/canonical.py` (`_build_schema_for_level`)  
**Description:** The canonical schema is hardcoded per level with only 3-4 columns. Missing: QuantityType, UOM, Date, Brand, Category, Store Name. Cannot be extended without code changes.  
**Recommendation:** Make canonical schema configurable/dynamic. Support a configurable canonical schema registry that maps business concepts to column names.  
**Estimated Effort:** 3-4 days

---

## G4: No Sales + Product Master Enrichment
**Priority:** High  
**Architecture Impact:** Medium  
**Business Impact:** High — blocks the additional scenario  
**Files:** New module needed, `dav_tool/workflow/canonical.py`  
**Description:** No support exists for joining Sales File with Product Master File. Canonical dataset cannot be enriched with product attributes.  
**Recommendation:** Add a Relationship Engine layer between Detection and Canonical. Detection discovers candidate keys, UI confirms, Canonical enriches sales data using confirmed join.  
**Estimated Effort:** 3-5 days

---

## G5: No Disclaimer / Trailer / Start Line Detection
**Priority:** Medium  
**Architecture Impact:** Medium  
**Business Impact:** Medium — affects Retailer 1 (blank values), Retailer 3 (disclaimer)  
**Files:** `dav_tool/detection.py`  
**Description:** Detection does not identify disclaimer lines, trailer lines generically, or auto-detect start_line. Fixed-width record type prefixes are not detected.  
**Recommendation:** Add `detect_disclaimer_lines()`, improve `detect_trailer_prefix()` for generic trailers, add `detect_start_line()`, add `detect_record_prefix()` for fixed-width.  
**Estimated Effort:** 2 days

---

## G6: UI Contains Detection Logic (get_column_names)
**Priority:** Medium  
**Architecture Impact:** Medium  
**Business Impact:** Low — maintainability concern  
**Files:** `dav_tool/ui/helpers.py` (lines 260-288)  
**Description:** `get_column_names()` in `ui/helpers.py` performs file parsing logic (delimited reading, fixed-width chunking, multiline flattening) to determine column names. This should live in the Detection or Parser layer.  
**Recommendation:** Move `get_column_names()` to `dav_tool/workflow/discovery.py` and expose through the workflow preview service.  
**Estimated Effort:** 0.5 day

---

## G7: _reports.py Bypasses Processing Layer
**Priority:** Medium  
**Architecture Impact:** Medium  
**Business Impact:** Low — re-parsing occurs when pre-computed summaries are absent  
**Files:** `dav_tool/_reports.py` (lines 6-7, 91-130)  
**Description:** `_reports.py` imports `stream_store_aggregate` and `stream_upc_summary` directly from `_aggregators`, bypassing the Processing Layer. When pre-computed summaries are not provided, reports re-parse and re-aggregate.  
**Recommendation:** Route all report aggregation through `workflow/processing.py`. Enforce that the Reports layer receives pre-computed summaries only.  
**Estimated Effort:** 1 day

---

## G8: No QuantityType / UOM in Canonical Output
**Priority:** Medium  
**Architecture Impact:** Medium  
**Business Impact:** High — Retailer 1 (Mixed Units + Weight, UOM column)  
**Files:** `dav_tool/workflow/canonical.py`, `dav_tool/_normalizer.py`  
**Description:** Quantity resolution exists in the processing pipeline, but the resolved QuantityType (WEIGHT/UNIT/NONE) and UOM are not exposed in the canonical dataset or aggregated output. Business users cannot see whether quantities are weight-derived or unit-derived.  
**Recommendation:** Add `QuantityType` and `UOM` columns to the canonical schema. Propagate through aggregation (group-by + first/last for UOM).  
**Estimated Effort:** 1-2 days

---

## G9: No Summary Worksheets in Output
**Priority:** Low  
**Architecture Impact:** Low  
**Business Impact:** Medium — useful for business reporting  
**Files:** `dav_tool/workflow/output.py`, `dav_tool/_reports.py`  
**Description:** Output currently provides raw DataFrames and CSV. No summary worksheets with KPIs, Top/Bottom stores, category summaries exist.  
**Recommendation:** Add summary generation to the Output Layer. Generate Key Business Statistics, Top N stores/UPCs, and Store Validation Summary as pre-computed DataFrames on `OutputResult`.  
**Estimated Effort:** 2-3 days

---

## G10: No Preview for Canonical or Relationships
**Priority:** Medium  
**Architecture Impact:** Low  
**Business Impact:** Medium — user cannot see canonical transformation  
**Files:** `dav_tool/workflow/preview.py`, `dav_tool/ui/`  
**Description:** Preview supports raw and detected/flattened views but not canonical view (after column mapping and normalization). No product/sales relationship preview.  
**Recommendation:** Add `preview_canonical()` that runs canonical_chunk_stream for a small sample. Add `preview_relationship()` for joined data.  
**Estimated Effort:** 1-2 days

---

## G11: No Streaming Preview for Large Files
**Priority:** Low  
**Architecture Impact:** Low  
**Business Impact:** Medium — large files may cause memory issues during preview  
**Files:** `dav_tool/_parsers.py`  
**Description:** Preview reads entire sample into memory. No streaming/chunked preview for large files.  
**Recommendation:** Use Polars `LazyFrame` with `fetch()` for delimited previews. Use chunk-based preview for fixed-width.  
**Estimated Effort:** 1 day

---

## G12: pyiceberg Investigation Needed
**Priority:** Low  
**Architecture Impact:** Medium  
**Business Impact:** Low — dependency hygiene  
**Files:** `requirements.txt`, `pyproject.toml`  
**Description:** `pyiceberg` is not listed as a dependency but may be imported somewhere. Needs investigation for removal or optionalization.  
**Recommendation:** Search all imports for pyiceberg usage. If unused, remove from any configuration. If used but optional, move to optional-dependencies.  
**Estimated Effort:** 0.5 day

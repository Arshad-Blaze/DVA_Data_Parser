# Retailer Coverage

How the platform handles each retailer scenario, which parser/workflows run, and the
remaining gaps. "Retailer 1–4" from the discovery brief map onto the certified
scenarios as follows:

| Brief | Scenario | Certified dataset(s) |
|-------|----------|----------------------|
| Retailer 1 | Delimited sales (comma) | `delimited/retailer_grocery` |
| Retailer 2 | Delimited (tab / pharmacy) | `delimited/retailer_pharmacy` |
| Retailer 3 (HEB) | Record-based / multiline fixed-width | `record_based/retailer_heb` |
| Retailer 4 | Sales + Product | `parser/sales_product.py` (no certified fixture) |

Additional certified scenarios: fixed-width (`fixed_width/retailer_pharmacy_fw`),
header/detail + trailer (`header_detail/retailer_apparel`), multiline delimited
(`multiline/retailer_wholesale`), UTF-8 (`unicode/retailer_global`), malformed CP-1252
(`malformed/retailer_legacy`).

---

## 1. Retailer 1 — Delimited Sales (comma)

- **File shape:** `Store,UPC,Description,Units,Price` header + rows.
- **Detection:** `detect_file_type` → delimiter scoring finds `,` → `delimited`.
  `has_header` → True. Columns via `safe_read_csv`.
- **Parser:** `recommend_parser` → `"delimited"` → `DelimitedParser` (or the production
  `canonical_chunk_stream` fast path).
- **Workflows:** Onboarding or Format Change; store + item aggregation; validation.
- **Handling:** fully supported, certified, fast-path streaming (local).
- **Gaps:** none for this shape.

## 2. Retailer 2 — Delimited (tab)

- **File shape:** tab-delimited, same columns.
- **Detection:** delimiter scoring finds `\t` → `delimited` with delimiter `\t`.
- **Parser:** `delimited` (DelimitedParser / `scan_delimited` with separator).
- **Workflows:** same as Retailer 1.
- **Gaps:** none.

## 3. Retailer 3 — HEB (record-based, fixed-width multiline)

- **File shape:** `HDR` header, `S` store, `U` UPC detail, `T` trailer; fixed-width.
- **Detection:** `is_multiline_record` → `multiline`; `detect_hdr_prefix` → `HDR`;
  `detect_fixed_width_detail_prefixes` → `S/U`; `detect_trailer_prefix` → `T`.
- **Parser:** `recommend_parser` → `record_based` → `RecordBasedParser` builds a
  `RecordTree` (HDR=parent, S/U=detail, T=trailer boundary) and flattens details.
- **Workflows:** Onboarding multiline flow (`_multiline_flow` → `autoparse_context` →
  schema editor); also parseable through `canonical_chunk_stream` with layouts.
- **Gaps:**
  - In-memory parsing (500 MB+ HEB files will be fully resident).
  - `RecordBasedParser._open` hardcodes `utf-8` (app default is cp1252).
  - Multi-file sets: only `file_paths[0]` is parsed by the tree builder.
  - Discovery produces `columns=[]` for multiline → schema suggestions empty.

## 4. Retailer 4 — Sales + Product

- **File shape:** delimited sales records + a separate product master; enrichment of
  sales rows with product attributes (Brand/Category...).
- **Detection:** standard delimited detection; `product_master_path` is **never set by
  detection**.
- **Parser:** `SalesProductParser` — only selected when `recommended_parser ==
  "sales_product"` OR (`product_master_path` present). Since detection never sets
  `product_master_path`, this parser is **unreachable through the normal flow** and must
  be driven programmatically (tests / explicit discovery construction).
- **Workflows:** not wired into Onboarding/Existing UI.
- **Gaps:**
  - No certified dataset fixture for sales+product.
  - No UI path to supply a product master.
  - The join/enrichment lives inside the parser layer (crosses into Aggregator/
    Relationship territory; `RelationshipEngine.enrich_dataset` exists separately but
    is also un-wired to the UI).

---

## Cross-cutting scenarios

### Header/Data with different delimiters
- Supported for multiline delimited via `ml_record_types` + `ml_delimiter`
  (`multiline/retailer_wholesale`: `H|`/`D|`). Parent (`H`) fields merged into detail.
- Gap: detection re-derives record types; no explicit "header delimiter ≠ detail
  delimiter" model (single `ml_delimiter`).

### Parent/Child
- `RecordBasedParser` (tree) and `ParentChildParser` (flat merge). `record_based` wins
  for `multiline`; `parent_child` reachable only via `ml_flattened` or
  `header_prefix`+`detail_layout` on non-multiline results.

### Header/Trailer
- `detect_trailer_prefix` (TRL/T/...) + `detect_hdr_prefix` (HDR); trailer rows excluded
  from detail output; trailer acts as transaction boundary in flatteners.

### Mixed Quantity
- `quantity.py` resolves units vs weight with 5 strategies; weight → lb via `UOM_TO_LB`.
- Certified datasets currently use pure units; mixed-quantity is unit-tested
  (`tests/data/mixed_quantity`, `tests/test_quantity.py`) but not certified as a
  retailer scenario.

### Fixed Width
- `detect_record_length` + `detect_candidate_layout`; user confirms via
  `layout_builder`; `FixedWidthParser` / `parse_fixed_width_chunks`.
- Certified: `fixed_width/retailer_pharmacy_fw`.

### Multiline
- Certified: `multiline/retailer_wholesale` (delimited), `record_based/retailer_heb`
  (fixed-width), `header_detail/retailer_apparel` (fixed-width HDR/detail/trailer).

---

## Summary table

| Scenario | Parser | Certified | Status | Key gap |
|----------|--------|-----------|--------|---------|
| Delimited comma | Delimited | ✅ | Full | — |
| Delimited tab | Delimited | ✅ | Full | — |
| HEB record-based | RecordBased | ✅ | Works | in-memory; utf-8 hardcode; first-file only |
| Sales + Product | SalesProduct | ❌ | Unreachable in UI | product_master_path never set; no UI/UX; join in parser |
| Fixed width | FixedWidth | ✅ | Full | needs layout confirmation |
| HDR/detail+trailer (fixed) | ParentChild/RecordBased | ✅ | Full | trailer chunk flush semantics |
| Multiline delimited (H/D) | ParentChild/RecordBased | ✅ | Full | single ml_delimiter model |
| Mixed quantity | n/a (quantity resolver) | ⚠️ tests only | Supported | no certified retailer fixture |
| UTF-8 / CP-1252 | Delimited | ✅ | Full | encoding re-detection in config_builder |
| Excel | Excel | ❌ | Partial | never recommended; config_validator rejects "excel" |

**Overall:** Retailers 1–3 and the majority of format variants are handled end-to-end and
certified. Retailer 4 (Sales + Product) is the significant coverage gap — the parser and
the enrichment engine exist, but no discovery signal, UI path, or certified dataset
wires them together.

# Detection & Parser Validation Report

**Sprint**: PROMPT.md — 10 Work Items  
**Date**: 2026-07-31  
**Status**: All items completed and validated

---

## Summary

All 10 PROMPT.md work items have been implemented, tested, and validated. The system handles 10 distinct retailer scenarios with 285 passing tests (1 pre-existing deselected). No regressions introduced.

---

## Validation Results (10 Retailer Scenarios)

| # | Scenario | Test | Status |
|---|----------|------|--------|
| 1 | Mixed quantity (Weight + Units) | `test_scenario1_mixed_quantity` | PASS |
| 2 | Pure fixed-width parsing | `test_scenario2_pure_fixed_width` | PASS |
| 3 | HDR + S/U/T record flattening | `test_scenario3_hdr_su_records` | PASS |
| 4 | Simple delimited with dates | `test_scenario4_simple_delimited` | PASS |
| 5 | Sales + Product master relationship | `test_scenario5_sales_product_relationship` | PASS |
| 6 | Header vs data different delimiters | `test_scenario6_header_data_diff_delimiter` | PASS |
| 7 | Parent-child (HDR + Trailer) flatten | `test_scenario7_parent_child_flattening` | PASS |
| 8 | Multiple record layouts (registry) | `test_scenario8_multiple_record_layouts` | PASS |
| 9 | Mixed quantity fallback | `test_scenario9_mixed_quantity_fallback` | PASS |
| 10 | Large file streaming chunks | `test_scenario10_large_streaming` | PASS |

---

## Edge Cases Validated

| Dataset | Risk | Status |
|---------|------|--------|
| `quoted_csv/` | Fields containing delimiters | PASS |
| `escaped_quotes/` | `""` inside quoted fields | PASS |
| `empty_columns/` | Missing/null values | PASS |
| `ragged_rows/` | Varying column count per row | PASS |
| `mixed_delimiters/` | Header uses `\|`, data uses `,` | PASS |
| `mixed_quantity/` | Weight + Unit-only rows | PASS |
| `per_row_uom/` | Each row has its own UOM | PASS |
| `dated_sales/` | Date column in delimited | PASS |
| `hdr_with_trailer/` | Multi-line parent-child | PASS |
| `disclaimers/` | Footer text after structured data | PASS |
| `negatives/` | Negative quantities | PASS |
| `sut_records/` | S/U/T record types | PASS |

---

## Code Quality

- **285 tests pass**, 1 deselected (`test_report_html` — pre-existing).
- **Golden regression**: 12/12 tests pass.
- **Edge case suite**: 11/11 tests pass.
- **10 retailer scenarios**: 10/10 pass.
- **No new dependencies** introduced.
- **All new code** is backward compatible (optional `rejection_collector` param, optional layout overrides, default-chunk fallthrough).
- **Lint**: All modules pass ruff.

---

## Files Modified or Created

### New files
- `dav_tool/rejection.py` — RejectedRow, RejectionCollector
- `dav_tool/flatten.py` — FlattenConfig, FlattenEngine
- `dav_tool/layout_registry.py` — LayoutEntry, ColumnLayout, LayoutRegistry
- `tests/data/` — 12 edge-case dataset directories
- `tests/test_retailer_scenarios.py` — 10-scenario validation tests
- `docs/E2E_WALKTHROUGH.md` — Full end-to-end walkthrough
- `docs/Detection_Parser_Validation_Report.md` — This report

### Modified files
- `dav_tool/detection.py` — Quote-aware CSV via `_split_csv_line` (5 locations)
- `dav_tool/_parsers.py` — Rejection tracking in 6 parser functions; flatten engine delegation
- `dav_tool/_aggregators.py` — WEIGHT_QTY/WEIGHT_UOM carried through aggregation
- `dav_tool/_normalizer.py` — Unified normalize functions (6→2) + preview_normalized
- `dav_tool/quantity.py` — UOM aliases, QuantityResolutionResult dataclass
- `dav_tool/workflow/relationship.py` — O(n+m) enrich_dataset, overlap validation
- `dav_tool/workflow/preview.py` — Error wrapping, preview_multiline, preview_canonical
- `dav_tool/workflow/canonical.py` — Dead code cleanup, schema validation

---

## Remaining Work

- `test_report_html` pre-existing failure (HTML report format in certification runner)
- Multi-file batch processing (advanced pipeline wiring — out of scope for this sprint)

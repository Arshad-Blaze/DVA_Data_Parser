# Certification Suite — Sprint D

## Overview

Production Readiness certification for DVA Platform 1.0 RC1. Runs the full pipeline (Discovery → Configuration → Processing → Validation) against representative retailer datasets and compares results against expected outputs.

## Dataset Coverage

| Category | Retailer | Format | Status |
|----------|----------|--------|--------|
| delimited | retailer_grocery | Comma CSV | ✅ Pass |
| delimited | retailer_pharmacy | Tab CSV | ✅ Pass |
| fixed_width | retailer_pharmacy_fw | Fixed-width numeric | ✅ Pass |
| header_detail | retailer_apparel | HDR fixed-width + trailer | ✅ Pass |
| unicode | retailer_global | UTF-8 CSV | ✅ Pass |
| malformed | retailer_legacy | CP-1252 CSV | ✅ Pass |
| multiline | retailer_wholesale | Pipe-delimited H/D | ⚠️ Requires UI schema editor |

**Pass Rate:** 6/7 (85.7%)

## Architecture

```
retailer_certification/
├── delimited/retailer_grocery/
│   ├── BAU/sales.csv
│   ├── TEST/sales.csv
│   ├── Config/config.json
│   └── Documentation/README.md
├── fixed_width/retailer_pharmacy_fw/
│   ├── BAU/fixed.txt
│   ├── TEST/fixed.txt
│   ├── Layout/layout.csv
│   ├── Config/config.json
│   └── Documentation/README.md
├── multiline/retailer_wholesale/
│   ├── BAU/wholesale.txt
│   ├── TEST/wholesale.txt
│   ├── Config/config.json
│   └── Documentation/README.md
├── header_detail/retailer_apparel/
│   ├── BAU/apparel.txt
│   ├── TEST/apparel.txt
│   ├── Layout/*.csv (header, detail, trailer)
│   ├── Config/config.json
│   └── Documentation/README.md
├── unicode/retailer_global/
│   ├── BAU/global.csv
│   ├── TEST/global.csv
│   ├── Config/config.json
│   └── Documentation/README.md
├── malformed/retailer_legacy/
│   ├── BAU/legacy.csv
│   ├── TEST/legacy.csv
│   ├── Config/config.json
│   └── Documentation/README.md
├── configs/          (shared configs - future)
├── expected/         (shared expected - future)
└── large_files/      (large file testing - future)
```

## CertificationRunner

### Interface

```python
runner = CertificationRunner()
suite = runner.run_all()              # Run all retailers
suite = runner.run_category("delimited")  # Run one category
result = runner.run_one("fixed_width", "retailer_pharmacy_fw")  # Run one retailer
report = runner.generate_report(suite, "markdown")  # json, markdown, html, text
```

### Result Structure

- `CertificationSuiteResult`: total, passed, failed, duration, results[]
- `CertificationResult`: category, retailer, passed, duration, discovery_ok, config_ok, processing_ok, validation_ok, expected_outputs_match, errors[], metrics, details

### Pipeline Phases

1. **Discovery**: detect_file for each side (or load config)
2. **Configuration**: load FormatConfig or build_config fallback
3. **Processing**: run_store_aggregation + run_item_aggregation (4 parallel)
4. **Validation**: store, item, store-list, file-review via run_existing_validation
5. **Expected Comparison**: compare results against expected/ CSVs (optional)

## Developer Mode UI

Integrated into the certification page's developer mode checkbox:

```
🧪 Certification Suite
├── ▶️ Run All
├── Category dropdown ▶️ Run Category
├── Retailer dropdown ▶️ Run Retailer
└── Download Reports (Markdown / JSON / HTML)
```

Access: navigate to **Certification** page, enable **Developer Mode** in the sidebar.

## Tests

```
tests/test_certification_runner.py — 15 tests
├── dataset discovery and structure
├── run_all / run_category / run_one
├── error handling (missing root, missing retailer)
├── report generation (json, markdown, html)
├── details and metrics validation
└── dataset regeneration and re-certification
```

All 15 tests pass alongside the 195 existing tests.

## Performance

Full suite (7 retailers): **~1.6s** on local machine.
Each retailer averages ~0.2–0.4s depending on format complexity.

## Limitations

- **Multiline delimited** (H/D record types) requires the UI schema editor for column renaming — cannot be fully automated. The store aggregation fails on empty fields from H records.
- **Expected output comparison** is optional per-retailer (expected/ CSVs not yet populated for all retailers).
- **Large files** (500MB+) and **memory streaming** are not yet benchmarked in the suite.

## Next Steps

- Populate expected/ CSVs for all 7 retailers
- Add large file testing (100MB, 500MB, 1GB)
- Add memory profiling to the certification runner
- Add Playwright E2E tests for the Developer Mode UI
- Address multiline delimited automation (schema mapping from canonical_schema)

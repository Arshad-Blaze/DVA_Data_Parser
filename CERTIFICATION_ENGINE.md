# Configuration Certification Engine

## Overview

The Configuration Certification workflow validates that a retailer's new data delivery (Test) can safely replace their current production feed (BAU). It extends the original "Existing" comparison workflow with structured comparison phases and a formal Migration Report.

## Architecture

```
UI (certification.py)
│
├─ Discovery         ─ reuses workflow.discovery
├─ Discovery Compare ─ NEW: file-type, delimiter, column comparison
├─ Configuration     ─ reuses config_builder / format_config
├─ Schema Compare    ─ NEW: column diff (new/removed/common)
├─ Config Validate   ─ reuses validate_config_before_processing
├─ Processing        ─ reuses workflow.processing (Store/Item agg)
├─ Certification     ─ reuses workflow.validation (Store/Item/FileReview)
├─ Reports           ─ reuses display_results
└─ Migration Report  ─ NEW: structured JSON report + recommendations
```

## Phase Details

### Phase 1 — Discovery (unchanged)
- Detect file type, delimiter, columns for BAU and Test
- Consumes Connection Manager DiscoveryResult when available
- Load optional FormatConfig JSON for pre-configured setups

### Phase 2 — Discovery Comparison (NEW)
- Side-by-side file type, delimiter, column count display
- Match indicators (✓/✗) for type, delimiter, column count
- Column set diff (BAU-only vs Test-only columns)
- Gate before Configuration

### Phase 3 — Configuration (reused)
- Progressive config wizard for BAU, then Test
- Column mapping (store, UPC, units, price, description)
- Price type / implied decimals

### Phase 4 — Schema Comparison (NEW)
- Metric cards: common columns, BAU-only, Test-only
- Detailed column diff with add/remove detection
- Schema comparison table for full review
- Gate before Config Validation

### Phase 5 — Config Validation (reused)
- Validates both BAU and Test configurations
- Checks required fields and data types

### Phase 6 — Processing (reused)
- Store-level and item-level aggregation
- Parallel execution (4 workers: BAU Store, Test Store, BAU Item, Test Item)
- Fixes pre-existing bugs: undefined `prod_ml_rtypes_prod` and `test_ml_rtypes` variables

### Phase 7 — Certification / Validation (reused)
- Store-level validation (BAU vs Test)
- Item-level validation (UPC comparison)
- Store list comparison
- File review reports

### Phase 8 — Reports (reused)
- Displays all validation results
- Download buttons for CSV exports

### Phase 9 — Migration Report (NEW)
- Aggregation comparison (store count, item count)
- Schema diff summary (common, BAU-only, Test-only columns)
- Validation result summary
- Recommendations engine:
  - New columns detected in Test
  - Columns removed in Test
  - File type mismatches
  - Store coverage gaps
  - Error/warning counts
- Downloadable JSON report with full certification data

## Reuse Rules

| Component | Source | How Reused |
|-----------|--------|------------|
| Discovery | `workflow.discovery.detect_file` | Called per-side in Phase 1 |
| Config Builder | `config_builder.build_config` | Called per-side in Phase 3 |
| Format Config | `format_config.load_format_config` | Config load in Phase 1 |
| Config Validation | `ui.helpers.validate_config_before_processing` | Phase 5 |
| Store Aggregation | `workflow.processing.run_store_aggregation` | Phase 6 |
| Item Aggregation | `workflow.processing.run_item_aggregation` | Phase 6 |
| Store Validation | `validation.store.storelevelvalidation` | Phase 7 |
| Item Validation | `validation.item.run_item_validation` | Phase 7 |
| File Review | `_reports.generate_file_review` | Phase 7 |
| Execution Summary | `ui.helpers.display_execution_summary` | Phase 8/9 |
| Phase Progress | `ui.helpers.render_phase_progress` | All phases |

## Migration Report Schema

The downloadable JSON report (`migration_report.json`) follows this structure:

```json
{
  "certification_type": "Configuration Certification",
  "bau": {
    "file_type": "delimited",
    "delimiter": ",",
    "column_count": 12,
    "columns": ["STORE", "UPC", "..."]
  },
  "test": {
    "file_type": "delimited",
    "delimiter": "|",
    "column_count": 14,
    "columns": ["STORE", "UPC", "NEW_COL", "..."]
  },
  "schema_differences": {
    "common_columns": ["STORE", "UPC"],
    "bau_only": ["OLD_COL"],
    "test_only": ["NEW_COL"]
  },
  "validation": {
    "store_list_missing_in_test": "STORE123,STORE456",
    "store_list_missing_in_prod": "",
    "errors": [],
    "warnings": []
  },
  "metrics": {
    "rows_processed": 1500000,
    "total_execution_time": 12.34,
    "peak_memory_mb": 256.0
  }
}
```

## Backward Compatibility

- File remains `dav_tool/ui/existing.py` — existing imports unchanged
- `ExistingContext` class preserved — used by validation workflow
- `run_existing_validation()` function preserved — called from Phase 7
- All session state keys (`ex_*` prefix) preserved
- Phase constants renumbered (shift +3) — internal to the file

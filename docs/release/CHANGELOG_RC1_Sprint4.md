# Changelog — RC1 Sprint 4 (Canonical Layer)

## Added

### Three-Layer Schema Model
- **Canonical schema propagation:** `ctx.schema` (canonical) flows from discovery
  through config to processing. All downstream modules consume canonical-only
  column names. (`format_config.py:318-323`, `options.py:78`)

- **ColumnMapping weight/UOM fields:** Added `quantity_type`, `weight_col`,
  `weight_uom`, `weight_uom_col` to `ColumnMapping` with `from_context()` support.
  (`options.py:96-117`)

- **Effective Quantity in normalizer:** New `_effective_qty_expr()` function selects
  quantity source based on `quantity_type` ("units", "weight", or "mixed") and
  applies UOM conversion when `weight_uom_col` is set. (`_normalizer.py:46-76`)

- **UOM conversion table:** `UOM_TO_LB` dict and `_apply_uom_conversion()` for
  per-row UOM normalization to canonical lb. (`_normalizer.py:30-44`)

- **ProcessingContext declared fields:** Added `quantity_type`, `weight_col`,
  `weight_uom`, `weight_uom_col`, `resolution_rule` as declared dataclass fields.
  (`processing_context.py:57-61`)

### Canonical Dataset Enforcement
- **Physical schema no longer referenced downstream.** All aggregation,
  validation, and report functions consume only canonical column names.

### Architecture Documentation
- `Canonical_Architecture.md` — describes three-layer model, data flow,
  effective quantity, and key design decisions.

## Changed

- **onboarding.py column dropdowns** now use `ctx.schema` (canonical) instead
  of `ctx.columns` (physical) when available. (`onboarding.py:412,530`)

- **All aggregator functions** (`stream_store_aggregate`, `stream_item_aggregate`,
  `stream_upc_summary`) accept and pass weight/UOM params to normalizer.
  (`_aggregators.py`)

- **`aggregate()`, `aggregate_with_options()`, `aggregate_with_config()`** all
  thread weight/UOM through to streaming functions. (`_aggregators.py`)

- **`generate_file_review()`** accepts weight/UOM params and passes them to
  aggregator calls. (`_reports.py`)

- **`run_file_review()`, `_generate_single_file_review()`,
  `_generate_both_file_reviews()`** thread weight/UOM from `ColumnMapping`.
  (`workflow/processing.py`, `workflow/validation.py`)

## Fixed

- Physical schema (`ctx.columns`) is no longer used for column selection dropdowns
  in onboarding — canonical schema (`ctx.schema`) is preferred.

## Backward Compatibility

- All existing retailer configs continue to work. Default `quantity_type` is
  `"units"`, which produces identical behavior to before.
- 210 unit tests + 12 golden tests: PASS

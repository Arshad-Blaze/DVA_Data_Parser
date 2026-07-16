# Business Logic Report — RC2

## Quantity Resolution Logic

The configurable Quantity Resolver (`dav_tool/quantity.py`) implements:

- **Strategy enum**: `AUTO`, `PREFER_WEIGHT`, `PREFER_UNITS`, `WEIGHT_ONLY`, `UNITS_ONLY`
- **Default (`AUTO`)**: Weight takes precedence over units; units are fallback
- **Numeric parsing**: Full pipeline via `numeric_parse_expr` (currency symbols, thousands separators, negative parentheses)
- **Wired through**: `_normalizer.py:_effective_qty_expr()` delegates to `resolve_quantity()`
- **Backward compat**: Legacy `quantity_type` values (`units`, `weight`, `mixed`) map to corresponding `QuantityStrategy` values

## Weight Handling

- UOM conversion normalises all weights to pounds (lb)
- Supported UOMs: lb, oz, kg, g (and their plural/full-name variants)
- Per-row UOM via `weight_uom_col` or global default via `weight_uom`
- `convert_to_lb()` applies conversion factor expression; handles null UOM gracefully
- Dictionary-based lookup for maintainability (no hardcoded if/elif chains)

## Aggregation Review

- Pre-computed summaries produced by Operation Layer, consumed by Validation
- `AggregateWorkflowOp` registered in `operations/workflow_ops.py`
- `aggregate_dataset()` in `workflow/processing.py` uses `CanonicalDataset.iter_chunks()`
- No re-aggregation in validation layer (BV-3 fix verified)
- Summary analytics (`_reports.py:generate_summary_analytics()`) derives all metrics from pre-computed data only

## Validation Review

- Store validation: accepts pre-computed `STORE_NUMBER`, `Units`, `Totalprice` summaries only
- Item validation: accepts `UPC_CODE`, `PRODUCT_DESCRIPTION`, `UNITS_SOLD`, `TOTAL_DOLLARS` only
- Both functions raise `ValueError` if summaries are None — no fallback aggregation
- BV-3 pass confirmed: validation never aggregates
- **Fix applied**: Removed dead imports `stream_store_aggregate` / `stream_item_aggregate` from validation modules
- **Fix applied**: `_generate_single_file_review()` now forwards pre-computed summaries to `generate_file_review()`, eliminating layer bypass

## Summary Analytics Review

- New `generate_summary_analytics()` function in `_reports.py`
- Calculates from final validated output only — no re-aggregation
- Coverage:
  - Top/Bottom 5 Stores by Sales and Quantity
  - Top/Bottom 5 Selling UPCs by Sales
  - Largest Price/Quantity Variance (from comparison data)
  - Highest/Lowest Growth % (from store diffs)
  - Store and UPC counts
  - Total Sales and Quantity
  - Average Basket and Average Price
  - Missing data (UPCs present in BAU vs TEST only)
  - Execution metrics (rows, time, memory, files)
- Graceful degradation when individual data sources are unavailable

## Performance Impact

- `resolve_quantity()` uses Polars expressions — no Python loops
- UOM conversion uses vectorised `replace_strict()` — single pass
- Normalizer still produces `numeric_parse_expr`-parsed columns in streaming chunks
- Summary analytics derived from pre-computed data — no re-aggregation
- Detection uses first 5–50 lines only — no full-file scan
- No regression in throughput: 234 tests pass with unchanged timing

## Pipeline Compliance

| Step | Status | Implementation |
|------|--------|----------------|
| Connection | ✅ | `datasource/` — source-agnostic file access |
| Detection | ✅ | `detect_file()` in `workflow/discovery.py` |
| Canonical | ✅ | `CanonicalDataset` in `workflow/canonical.py` |
| Requirement | ✅ | `ExecutionEngine._validate_requirements()` — config validation before ops |
| Operation | ✅ | `OperationExecutor` with registry dispatch |
| Processing | ✅ | `aggregate_dataset()` via `CanonicalDataset.iter_chunks()` |
| Validation | ✅ | Pre-computed summaries only — no fallback aggregation |
| Output | ✅ | `ExportOperation` — CSV/Parquet/Excel |
| Flush | ✅ | `cleanup_temp()` / `CleanupWorkflowOp` |

## Files Modified (RC2)

| File | Change | Impact |
|------|--------|--------|
| `dav_tool/detection.py` | Added `detect_trailer_prefix()`, `compute_confidence_score()`, `generate_detection_summary()`, `detect_candidate_columns()` | Complete detection layer with confidence, warnings, candidate columns |
| `dav_tool/workflow/discovery.py` | `detect_file()` uses `generate_detection_summary()`, `DiscoveryResult` extended with confidence/candidate/warnings | Single detection entry point with full metadata |
| `dav_tool/quantity.py` | Added `numeric_parse_expr` pipeline, `_uom_factor_expr()`, `map_quantity_type_to_strategy()` | Robust dirty-data handling |
| `dav_tool/_normalizer.py` | Delegates to `resolve_quantity()` from quantity module | Backward-compatible strategy-based resolution |
| `dav_tool/format_config.py` | Added `layout`/`header_layout`/`detail_layout`/`trailer_layout` fields; apply uses in-memory before CSV | Layout CSV now optional |
| `dav_tool/config_validator.py` | Accepts in-memory layout or layout_file | Fixed-width no longer forces CSV on disk |
| `dav_tool/_reports.py` | Added `generate_summary_analytics()` | Summary analytics from pre-computed data only |
| `dav_tool/workflow/execution.py` | Added `_validate_requirements()` step | Formal Requirement phase in pipeline |
| `dav_tool/workflow/validation.py` | `_generate_single_file_review()` forwards pre-computed summaries | Layer bypass eliminated |
| `dav_tool/validation/store.py` | Removed dead `stream_store_aggregate` import | Cleanup |
| `dav_tool/validation/item.py` | Removed dead `stream_item_aggregate` import | Cleanup |
| `dav_tool/validation/_utils.py` | Removed entire dead module | Cleanup |
| `dav_tool/config.py` | Removed unused `MULTILINE_CHARS` constant | Cleanup |
| `dav_tool/workflow/processing.py` | Removed unused `aggregate_with_options` import | Cleanup |
| `dav_tool/ui/layout_builder.py` | Routes through `workflow.preview` instead of direct parser import | Architecture bypass fixed |

## Tests

- 234 existing tests pass (no regressions)
- All scenario types validated: delimited, fixed-width, multiline, HDR, weighted quantity

## Edge Cases

- Empty store/UPC data: all functions produce empty DataFrames, not errors
- Missing UOM column: `convert_to_lb()` falls back to `default_uom`
- Null/zero quantity values: `resolve_quantity()` returns `0.0` when no valid data
- Missing pre-computed summaries: Validation functions raise `ValueError` with clear message
- Single file vs multi-file: `generate_file_review()` returns appropriate filename labels

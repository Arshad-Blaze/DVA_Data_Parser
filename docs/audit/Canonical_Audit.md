# Canonical Audit

## Current State

**Location:** `dav_tool/workflow/canonical.py`

The `CanonicalDataset` class provides:
- `schema` — canonical column names
- `iter_chunks()` — streaming iterator of polars DataFrames
- `level` — aggregation level (store/item/upc)
- `from_parse_options()` — factory for standard construction
- `from_context()` — factory from ProcessingContext

## Canonical Schema Per Level

| Level | Columns | Notes |
|-------|---------|-------|
| store | STORE_NUMBER, Units, Totalprice | Missing: QuantityType, UOM, Date |
| item | UPC_CODE, PRODUCT_DESCRIPTION, UNITS_SOLD, TOTAL_DOLLARS | Missing: QuantityType, UOM, Date, Brand, Category |
| upc | UPC, UNITS_SOLD, TOTAL_DOLLARS | Missing: QuantityType, UOM |

## Findings

1. **CA-1: Schema is hardcoded** — `_build_schema_for_level()` returns literal lists. Adding a new column (e.g., UOM) requires changing the function signature, the normalizer, and the aggregator.

2. **CA-2: No QuantityType propagation** — Quantity resolution determines whether a row is weight-based or unit-based, but this information is not stored in the canonical dataset. Aggregation loses this metadata.

3. **CA-3: No UOM in canonical output** — UOM column (from weight_uom_col) is used during quantity resolution but not preserved in canonical output.

4. **CA-4: No date handling** — Date columns are not part of the canonical schema, even when detected.

5. **CA-5: No enrichment support** — CanonicalDataset has no mechanism for joining/enriching from a second dataset (Product Master).

6. **CA-6: CanonicalContext still exists** — `options.py:CanonicalContext` is marked as internal but still used. Should be consolidated into `CanonicalDataset` factories.

## Strengths

- Clean streaming interface hides all file-format details
- Factory pattern allows construction from multiple sources
- Metadata dict carries file-type info for downstream diagnostics
- Capabilities set allows runtime feature detection

## Recommendations

1. Make canonical schema configurable — allow user to define which business columns to include
2. Add `QuantityType` and `UOM` to canonical schema and propagate through aggregation
3. Add date column support to canonical schema
4. Add `enrich()` method to CanonicalDataset for relationship joins
5. Deprecate `CanonicalContext` in favor of `CanonicalDataset.from_parse_options()`
6. Consider a `CanonicalSchemaRegistry` that maps business concepts to dynamic columns

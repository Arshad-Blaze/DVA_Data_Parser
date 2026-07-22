# DVA Platform 1.0 RC1 — Configuration Review (Sprint B)

## Schema Propagation Report

### Three-Layer Schema Model

```
Physical Schema          Canonical Schema         Business Mapping
  (discovery)     →        (editable)       →     (concepts)
                                                    
  Store_Number     →       store                 → Store
  Product_UPC      →       upc                   → UPC
  Product_Desc     →       description           → Description
  Sold_Qty         →       quantity              → Quantity
  Retail_Price     →       price                 → Price
```

### Physical Schema
- Set once during file discovery, **never changes**
- Stored as `FormatConfig.physical_schema`
- Displayed read-only in UI section "Physical Schema (from Discovery)"
- Preserves original column names exactly as discovered

### Canonical Schema
- Editable by the user via text area
- Stored as `FormatConfig.canonical_schema`
- **Propagates to**:
  - Business Mapping (column selectors sourced from canonical schema)
  - Operations (Aggregate, Filter, Sort, etc.)
  - Validation (validated against canonical schema)
  - Reports (column names used in output)
- Backward-compat alias: `FormatConfig.schema` → `canonical_schema`

### Business Mapping
- Maps business concepts (Store, UPC, Description, Quantity, Price) to canonical schema columns
- `FormatConfig.store_col`, `upc_col`, `desc_col`, `quantity_col`, `price_col`
- Validator checks these against the **canonical** schema, not physical
- Unused canonical schema columns are **not** validation errors

---

## Validator Report

### Operation-Aware Validation

| Mode | Required Mappings | Notes |
|---|---|---|
| VALIDATE | store, upc, quantity, price | Full pipeline |
| AGGREGATE_ONLY | store (group_by) | No UPC/quantity/price required |
| STATISTICS | none | No column mapping required |
| EXPORT | none | No column mapping required |

### Key Changes
- Validator now validates against `canonical_schema` (not `physical_schema`)
- Unused canonical schema columns never trigger validation errors
- `units_col` replaced with `quantity_col` (backward-compat property maintained)
- Schema existence check split: physical_schema + canonical_schema

---

## Quantity Architecture

### Configuration Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `quantity_type` | str | "units" | "units", "weight", or "mixed" |
| `weight_col` | str | None | Canonical schema column for weight |
| `weight_uom` | str | "lb" | Unit of measure: lb, oz, kg, g |
| `resolution_rule` | str | "units_preferred" | How to resolve mixed datasets |

### Behavior

- **Units Only**: Standard behavior. Quantity column contains unit counts.
- **Weight Only**: Quantity column contains weight values. Weight UOM tracked.
- **Mixed**: Both units and weight columns present. `resolution_rule` determines effective quantity:
  - `units_preferred`: Use units when available, fall back to weight
  - `weight_preferred`: Use weight when available, fall back to units
  - `average`: Average units and weight (after normalization)

### Canonical Dataset
- `EFFECTIVE_QUANTITY` — resolved quantity value
- `QUANTITY_TYPE` — indicates "units" or "weight" for each row
- Original retailer columns remain untouched

---

## Backward Compatibility

| Old Field | New Field | Status |
|---|---|---|
| `schema` | `canonical_schema` | Property alias — fully backward compat |
| `detected_columns` | `physical_schema` | Property alias — fully backward compat |
| `units_col` | `quantity_col` | Property alias — fully backward compat |
| `suggested_mapping` | `suggested_mapping` | Regular field (was property) — API compatible |
| `BUSINESS_RULES` section | `BUSINESS_MAPPING` section | Renamed, new section added |
| (new) | `QUANTITY` section | Added |
| (new) | `PHYSICAL_SCHEMA` section | Added |
| (new) | `CANONICAL_SCHEMA` section | Added |

## Regression Report

- **195 unit tests pass** (no regressions)
- All existing `cfg.schema`, `cfg.detected_columns`, `cfg.units_col`, `cfg.suggested_mapping` access patterns continue to work
- All existing ProcessingContext field references (`ctx.schema`, `ctx.columns`, `ctx.units_col`) unchanged
- Serialization (save/load JSON) compatible — properties auto-convert on access

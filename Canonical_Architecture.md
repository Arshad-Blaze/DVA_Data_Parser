# Canonical Architecture — DVA Platform RC1

## Three-Layer Schema Model

```
                        ┌─────────────────────────────────────┐
                        │         Physical Schema              │
                        │  Column names exactly as discovered  │
                        │  Immutable — never modified          │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │         Canonical Schema             │
                        │  Business-friendly, user-editable    │
                        │  Names propagated to all downstream  │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │         Business Mapping             │
                        │  Maps concepts to canonical columns │
                        │  store, upc, desc, units, price,    │
                        │  weight_col, weight_uom_col         │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │         Canonical Dataset            │
                        │  DataFrame with canonical columns:  │
                        │  STORE_NUMBER, UPC_CODE, Units,     │
                        │  Totalprice, UNITS_SOLD, etc.       │
                        └──────────────┬──────────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────┐
            │                          │                      │
            ▼                          ▼                      ▼
     Aggregation Engine        Validation Engine        Reports Engine
     (canonical-only)          (canonical-only)         (canonical-only)
```

## Data Flow

### 1. Discovery (Source of Truth)

```python
# dav_tool/workflow/discovery.py:120-121
ctx.columns = self.columns        # Physical schema
ctx.schema = self.schema or self.columns  # Canonical schema
```

### 2. Configuration → ProcessingContext

```python
# dav_tool/format_config.py:318-323
if config.canonical_schema:
    ctx.schema = config.canonical_schema           # Canonical → ctx.schema
if config.physical_schema:
    ctx.columns = config.physical_schema           # Physical → ctx.columns
```

### 3. ColumnMapping Construction

```python
# dav_tool/options.py:105-117
ColumnMapping.from_context(ctx):
    # Reads store_col, upc_col, desc_col, units_col, price_col
    # Also reads quantity_type, weight_col, weight_uom, weight_uom_col
    # All column references use canonical schema names
```

### 4. Aggregation Pipeline

```
ParseOptions.column_names (= ctx.schema = canonical)
    ↓
apply_column_names(chunk, column_names)  — renames raw columns to canonical
    ↓
Normalizer (_effective_qty_expr) — handles units/weight/mixed/UOM column
    ↓
Canonical columns: STORE_NUMBER, Units, Totalprice, UPC_CODE, UNITS_SOLD, TOTAL_DOLLARS
    ↓
Aggregation (group by canonical columns)
```

### 5. Validation & Reports

Both consume only canonical-named DataFrames. No physical schema references.

## Effective Quantity

The `quantity_type` field on `ColumnMapping` controls how quantity is measured:

| Type | Source Column | UOM Handling |
|------|-------------|--------------|
| `"units"` (default) | `units_col` | No conversion |
| `"weight"` | `weight_col` | UOM column or default converted to lb |
| `"mixed"` | `coalesce(weight_col, units_col)` | Weight values converted to lb |

When `weight_uom_col` is set, per-row UOM values are read from that column and
converted to canonical lb. When unset, the `weight_uom` default ("lb") is used.

### UOM Conversion Factors (to lb)

| Input UOM | Factor |
|-----------|--------|
| lb | 1.0 |
| oz | 1/16 |
| kg | 2.20462 |
| g | 0.00220462 |

## Key Design Decisions

1. **No downstream module references physical schema.** All processing,
   validation, and reports consume only canonical column names.

2. **ParseOptions.column_names = ctx.schema.** The parser receives canonical
   names, not physical names.

3. **ColumnMapping holds all business mappings**, including quantity type,
   weight column, and UOM column.

4. **CanonicalContext bundles ParseOptions + ColumnMapping + canonical_schema**
   as the single input contract for the processing layer.

5. **Backward compatibility maintained.** Default `quantity_type` is "units".
   Existing retailer configs without weight/UOM settings continue to work identically.

## File Reference

| File | Role |
|------|------|
| `format_config.py` | `FormatConfig` dataclass — serializable config with three-layer schema |
| `processing_context.py` | `ProcessingContext` — runtime state with schema/columns |
| `options.py` | `ParseOptions`, `ColumnMapping`, `CanonicalContext` — immutable option objects |
| `workflow/canonical.py` | `CanonicalSchema` — physical↔canonical mapping utilities |
| `_normalizer.py` | Normalization functions with Effective Quantity support |
| `_aggregators.py` | Aggregation engine — streaming, chunked, canonical-only |
| `workflow/processing.py` | Processing orchestration — consumes CanonicalContext |
| `ui/helpers.py` | Schema editor UI — canonical names editable via text area |

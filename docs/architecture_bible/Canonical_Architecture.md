# Canonical Architecture

The Canonical layer: schema, dataset contract, column mapping, business rules, quantity
resolution, weight priority, UOM, metadata, and how every retailer becomes identical.

---

## 1. Canonical Schema (`workflow/canonical.py:27`)

```python
@dataclass
class CanonicalSchema:
    physical_schema: List[str]   # original columns from detection (immutable)
    canonical_names:  List[str]  # business-friendly editable names
    column_mapping:   Dict[str, str]  # canonical → normalized canonical names
```

- `from_discovery(discovery)` / `from_physical(columns)` — canonical names default to
  physical names.
- `get_rename_mapping()` — physical→canonical pairs that differ.
- `columns` property — canonical names for display/selection.

**Finding:** `CanonicalSchema` is effectively **dead code in production** — never
instantiated outside its own module. The runtime "canonical schema" is
`CANONICAL_SCHEMA_TEMPLATES` plus the normalizer output names.

---

## 2. Schema Templates (`CANONICAL_SCHEMA_TEMPLATES`, canonical.py:333)

| template | store | item | upc |
|----------|-------|------|-----|
| `minimal` (default) | `STORE_NUMBER, Units, Totalprice` | `UPC_CODE, PRODUCT_DESCRIPTION, UNITS_SOLD, TOTAL_DOLLARS` | `UPC, UNITS_SOLD, TOTAL_DOLLARS` |
| `standard` | + `QuantityType, UOM, Date` | + `QuantityType, UOM, Date` | + `QuantityType, UOM, Date` |
| `enriched` | + `Brand, Category` | + `Brand, Category` | + `Brand, Category` |

Note the naming inconsistency: store level uses `Units`/`Totalprice` (mixed case) while
item/upc use `UNITS_SOLD`/`TOTAL_DOLLARS`.

---

## 3. CanonicalDataset (canonical.py:83)

The **single Processing input contract**. Hides delimiter, encoding, fixed-width,
multiline, HDR, record types behind a uniform streaming iterator of canonically-named
DataFrames.

- `schema`, `level` ("store"/"item"/"upc"), `metadata`, `file_paths`, `capabilities`
  (default `{"store","item"}`), `statistics` (never populated).
- `iter_chunks()` — yields normalized DataFrames.
- `enrich(target, join_mapping, attributes)` — delegates to
  `RelationshipEngine.enrich_dataset` (chunked left-join; not driven by the UI).

### Construction paths

| Factory | Used by | Behavior |
|---------|---------|----------|
| `from_parse_options(file_paths, parse_opts, mapping, level, source, schema_template)` | **production** (`workflow/processing.py`) | builds `col_args` per level, closes over `canonical_chunk_stream(...)` |
| `from_discovery(discovery, level, ...)` | parser-driven / HEB | `default_factory.parse(discovery)` → `ParsedResult.to_dataframe()` streamed as **one chunk**; **no canonical renaming/normalization applied** |
| `from_context(ctx, level, ...)` | convenience | builds options from a ProcessingContext → from_parse_options |

### Gaps

- `schema_template` is used to build the declared `schema` but is **not forwarded into
  `_build_stream()`** → chunks may contain only the minimal columns while `schema`
  declares standard/enriched columns.
- `from_discovery` streams raw parser output; chunk columns and declared schema can diverge.

---

## 4. Column Mapping (`options.py:88`)

```python
ColumnMapping(store, upc, description, units, price,
    price_type="Total Price",
    implied_dollars=False, implied_units=False,
    quantity_type="units",
    weight_col=None, weight_uom="lb", weight_uom_col=None,
    quantity_strategy="auto",
    weight_qty_col=None, units_uom=None,
    date_col=None, schema_template="minimal")
```

Mapping from physical columns to canonical roles. Suggestions come from two heuristics:

1. `smart_column_indices` / `find_best_column_index` (`_column_utils.py:37-73`) — used by
   `config_builder`: exact case-insensitive → synonym exact → substring overlap.
2. `detect_candidate_columns` (`detection.py:1145`) — keyword scanning with guards
   (e.g. a column containing "uom"/"weight"/"lb"/"kg" is excluded from the `units` match).

---

## 5. Business Rules Applied During Canonicalization (`_normalizer.py`)

### Store level (`store_normalize_exprs` / `normalize_store_chunk`)
- `Units` = resolved quantity (`_effective_qty_expr` → `quantity.resolve_quantity`).
- `Totalprice` = `numeric_parse_expr(price_col)`.
- `price_type == "Unit Price"` → `Totalprice = Units * price`.
- `implied_units` / `implied_dollars` → divide by 100.
- `STORE_NUMBER` = cast to Utf8.
- Optional `QuantityType` / `UOM` / `Date` for standard/enriched templates.

### Item level (`item_normalize_exprs` / `normalize_item_chunk`)
- `UPC_CODE` = cast Utf8 + strip.
- `PRODUCT_DESCRIPTION` = cast Utf8 + strip + `fill_null("")`.
- `UNITS_SOLD`, `TOTAL_DOLLARS` same quantity/price rules.

### UPC level — same as item minus description.

---

## 6. Quantity Resolution (`quantity.py`)

Business rule (default `auto`):

```
IF weight_qty IS NOT NULL AND weight_qty > 0  → resolved = weight_qty (converted to lb)
ELSE IF units > 0                             → resolved = units
ELSE                                          → resolved = 0
```

### Strategies

| Strategy | Behavior |
|----------|----------|
| `auto` | weight takes precedence, units fallback |
| `prefer_weight` | same as auto (explicit alias) |
| `prefer_units` | units take precedence, weight fallback |
| `weight_only` | only weight, ignore units |
| `units_only` | only units, ignore weight |

Legacy mapping: `units→units_only`, `weight→weight_only`, `mixed→auto`
(`map_quantity_type_to_strategy`).

### UOM → lb (`UOM_TO_LB`, quantity.py:40)

`lb/lbs/pound/pounds=1.0`, `oz/ounce/ounces=1/16`, `kg/kilogram(s)=2.20462`,
`g/gram(s)=0.00220462`. When `weight_uom_col` is set, per-row UOM values are read from
that column, lowercased/stripped, and mapped (unknown → factor 1.0).

`resolve_quantity(units_col, weight_qty_col, weight_uom_col, weight_uom, strategy,
units_uom, numeric_config)` returns a Float64 expression. `units_uom` is informational
only — units are counts, no conversion applied.

`_normalizer._quantity_type_expr` / `_uom_expr` mirror the resolution to label each row
`UNIT` / `WEIGHT` / `NONE` and the resolved UOM for standard/enriched templates.

---

## 7. Numeric Parsing Pipeline (`_numeric.py`)

`numeric_parse_expr(column, config)` — 13-step expression:

1. cast Utf8 → 2. strip → 3. collapse whitespace → 4. NULL-like patterns → None →
5. strip currency symbols (`$£€₹¥`) → 6. detect parenthesized negatives →
7. strip parens → 8. remove thousands separator → 9. normalize decimal separator →
10. strip → 11. empty → None → 12. validate against
`^-?\d+(\.\d+)?([eE][+-]?\d+)?$` → cast Float64 → 13. apply paren-negative →
`on_invalid==AS_ZERO` → fill 0.0.

`NumericParsingConfig` (frozen): `decimal_separator="."`, `thousands_separator=","`,
`currency_symbols=[...]`, `negative_format="prefix_minus"|"parens"`,
`on_invalid=AS_NULL|AS_ZERO|REJECT`, `null_patterns`, `strip_leading_zeros`.
**Finding:** `REJECT` and `strip_leading_zeros` are defined but never handled.

---

## 8. Metadata

`CanonicalDataset.metadata` (from_parse_options): `file_type`, `delimiter`,
`file_count`. (from_discovery): `parser`, `file_type`, `record_types`, `file_count`,
`detail_row_count`. Enrichment (RelationshipEngine) adds `Brand`/`Category` via chunked
left-join for the `enriched` template.

---

## 9. How Every Retailer Becomes Identical

1. Physical columns are discovered (detection) and shown to the user for mapping.
2. `ColumnMapping` + `ParseOptions` drive `canonical_chunk_stream`, which applies
   level-specific `normalize_*_exprs`/`normalize_*_chunk`.
3. Aggregators key on canonical names only (`STORE_NUMBER`, `UPC_CODE`, ...).
4. Validators require canonical frames (`STORE_NUMBER/Units/Totalprice`,
   `UPC_CODE/PRODUCT_DESCRIPTION/UNITS_SOLD/TOTAL_DOLLARS`) and refuse to aggregate.

Downstream layers never reference physical columns — **in the production path**. The
parser-driven `from_discovery` path is the exception (no normalization applied).

---

## 10. Known Defects

| # | Severity | Finding |
|---|----------|---------|
| 1 | High | `CanonicalDataset.from_discovery` bypasses the normalizer → non-canonical columns can reach downstream on the parser path. |
| 2 | Medium | `schema_template` not forwarded into `canonical_chunk_stream` in `from_parse_options`. |
| 3 | Medium | `CanonicalSchema` class is dead code (declared contract never used). |
| 4 | Medium | `capabilities` defaults to `{"store","item"}` — no `"upc"` despite upc-level templates existing. |
| 5 | Medium | `statistics` is never populated (declared but dead). |
| 6 | Low | Naming inconsistency between store (`Units`/`Totalprice`) and item/upc templates. |
| 7 | Low | `units_uom` is stored but only informational; `NumericHandling.REJECT` and `strip_leading_zeros` unused. |

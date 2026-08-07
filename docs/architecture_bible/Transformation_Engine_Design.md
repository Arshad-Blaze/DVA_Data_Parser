# Transformation Engine Design

**Status:** Sprint 3 deliverable — executes the TransformationPlan

---

## 1. Purpose

The Transformation Engine executes the `TransformationPlan` against raw
input records, producing a `TransformedDataset`. It sits between the
Transformation Planner and the Parser Pipeline:

```
Discovery → DatasetGraph → TransformationPlan → TransformationEngine →
TransformedDataset → Parser Pipeline → ParsedDataset
```

The engine performs **no parsing**. It only reshapes records.

---

## 2. Contract

Defined in `dav_tool/pipeline/contracts.py` (frozen dataclass).

```python
@dataclass(frozen=True)
class TransformedDataset:
    records: pl.DataFrame            # transformed records (physical Column_N fields)
    record_types: Tuple[str, ...]    # surviving record type prefixes
    layout: Optional[List[Dict]]     # fixed-width layout applied (if any)
    operations: Tuple[str, ...]      # names of executed operations
    join_operations: Tuple[Dict, ...] # enrichment joins applied
    metadata: Dict[str, Any]         # file type, delimiter, removal counts
    warnings: Tuple[str, ...]        # non-fatal transformation warnings
    discovery: Optional[DiscoveryResult]
```

---

## 3. What the Engine Owns

All of these occur in `dav_tool/pipeline/transformation.py`:

- **Header removal** — skip `plan.header_removal` leading lines before
  parsing the flat-delimited body.
- **Trailer removal** — trailer prefixes excluded from surviving record
  types.
- **Metadata removal** — reserved for pure-metadata prefixes.
- **Flattening** — parent replication + child expansion via
  `_flatten_records`.
- **Parent replication** — multiline parent (header) fields merged onto
  each child detail row.
- **Relationship expansion / file joins** — left-joins against the product
  master (`_apply_joins` / `_left_join`).
- **Record selection** — `_surviving_record_types` keeps detail types and
  drops trailers.

### Execution path

```
TransformationEngine.execute(discovery, plan, source)
   ├── _flatten_records(...)   # reshape raw records
   └── _apply_joins(...)       # enrich via relationship joins
   → TransformedDataset
```

### Flattening paths

| Input shape | Path | Reused helper |
|-------------|------|---------------|
| Multiline delimited (H/D/T) | `flatten_multiline_chunks` | `_parsers.flatten_multiline_chunks` |
| Multiline fixed width | `_flatten_fixed` | `_parsers.flatten_multiline_fixed_width` |
| Flat delimited | header removal + `_rows_to_df` | `_parsers._rows_to_df`, `_open_text_stream` |

### Join path

- Reads the product master via `dav_tool.io.safe_read_csv`
  (`discovery.product_master_path`).
- Left-joins product attributes onto sales rows on the join key
  (`source_col` → `target_col`, default `UPC`).
- Graceful failure: missing master, missing key column, or load errors
  produce a **warning** and leave the records unchanged — the pipeline stays
  alive.

---

## 4. Stage Wrapper

`dav_tool/pipeline/stages/transformation_engine.py` exposes the engine as a
pipeline stage (`name="transformation_engine"`, `label="Transformation"`):

- Requires `ctx.discovery` and `ctx.plan` (else `FatalStageError`).
- Runs the engine with `source=ctx.source` (streaming support).
- Stores the result on `ctx.transformed`.

---

## 5. Why Parsers No Longer Transform

PROMPT.md: *"Move ALL transformation logic here. Do NOT keep transformation
inside parsers."*

Parsers (`record_based.py`, `sales_product.py`) now consume
`TransformedDataset` via the `transformed` kwarg. When a transformed dataset
is present they:

- **skip** record-type-based reshaping (already flattened),
- record `transformed: True` in their metadata,
- for sales+product, note whether joins were applied.

When no transformed dataset is present (direct parse calls), the legacy
fallback path is unchanged — backward compatibility is preserved.

---

## 6. Streaming / Performance

- Chunking is delegated to the reused `_parsers` helpers.
- Joins load only the product master (small), never the full sales file.
- Records stay in Polars DataFrames end-to-end.
- Failures degrade to warnings + empty/unchanged frames instead of crashing
  the pipeline (see `Failure Recovery` in the Architecture Bible).

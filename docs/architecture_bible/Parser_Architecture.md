# Parser Architecture

The Parser subsystem: factory, selection, every parser, why each exists, how they
differ, and the common contract.

---

## 1. Two Stacks, One Engine

The codebase has **two coexisting parser stacks**:

1. **`dav_tool/parser/`** — the contract/factory layer. `ParserFactory.create(discovery)`
   → `BaseParser` → `ParsedResult`. Used for multiline/HEB onboarding, previews, and
   certification tests.
2. **`dav_tool/_parsers.py`** — the low-level engine: chunked readers, multiline
   flatteners, and `canonical_chunk_stream`. This is what the **production aggregation
   path** uses (`workflow/processing.py` → `CanonicalDataset.from_parse_options`).

The `parser/` package delegates its byte-level work back into `_parsers.py`
(delimited.py:7, fixed_width.py:7, parent_child.py:15, sales_product.py:68). So
`_parsers.py` is not dead — it is the shared workhorse, and the two stacks are only
partially reconciled.

---

## 2. ParserFactory

**File:** `parser/factory.py` (105 lines)

- `ParserRegistry` — name → parser class map; `register/get/names`.
- `@register_parser` decorator — classes self-register at import time
  (`parser/__init__.py` imports every parser module).
- `default_factory = ParserFactory()` — module singleton.

### Selection (`create(discovery)`, factory.py:67-97)

**Stage A — explicit recommendation:**
```python
recommended = discovery.recommended_parser
if recommended:
    parser = self._registry.get(recommended)
    if parser is not None:
        return parser()
```
If `recommended_parser` is set and registered, it wins — `supports()` is never consulted.

**Stage B — fallback scan:** iterate registered parsers sorted by ascending `priority`
(ties by name); return the first whose `supports(discovery)` returns True. Defensive
try/except per parser.

### Registered parsers

| name | priority | `supports()` |
|------|----------|--------------|
| `record_based` | 10 | `file_type == "multiline"` |
| `parent_child` | 20 | `ml_flattened` OR `file_type=="multiline"` OR (`header_prefix` and `detail_layout`) |
| `excel` | 30 | `file_type=="excel"` and path ends `.xlsx/.xls` |
| `sales_product` | 50 | `recommended_parser=="sales_product"` OR (delimited and `product_master_path`) |
| `delimited` | 100 | `file_type in ("delimited","csv","tsv","tab")` |
| `fixed_width` | 100 | `file_type=="fixed"` and (`candidate_layout` or `layout`) |

Overlap: `record_based` and `parent_child` both claim `multiline`; `record_based` wins by
priority 10 < 20. `sales_product` beats `delimited` whenever a product master path exists.

---

## 3. Why Each Parser Exists

| Parser | Retailer scenario | Reason it exists |
|--------|-------------------|------------------|
| `delimited` | plain CSV/pipe/tab/semicolon | the common case |
| `fixed_width` | positional records | retailers with fixed-width layouts |
| `record_based` | HEB multi-record (HDR/S/U/T) | hierarchical parent→child structure, auto tree build + flatten |
| `parent_child` | HDR/detail or `H\|D\|` delimited multiline | flatten without a tree (carry parent fields forward) |
| `excel` | `.xlsx/.xls` inputs | workbook reading |
| `sales_product` | Retailer "Sales + Product" | enrich sales rows with a product master via left join |

---

## 4. How They Differ

| Parser | Input config | Streaming | Key behaviour |
|--------|--------------|-----------|---------------|
| Delimited | `file_paths`, `delimiter` | chunked read, `pl.concat` result (in-memory) | row 0 always treated as header |
| FixedWidth | `layout` (list of `{field,start,end,type}`) | chunked read, concat | `numeric` strips leading zeros; 6-digit `date` → `20YY-MM-DD`; filters by `record_type` prefix |
| RecordBased | `ml_record_types`, `header_prefix`, `trailer_prefix`, layouts | **in-memory** (entire file → RecordTree → list → DataFrame) | classifies prefixes, builds tree, flattens details, drops trailers |
| ParentChild | `header_layout`+`detail_layout` (fixed) OR `record_types`+`ml_delimiter` (delimited) | chunked read, concat | header merged into each detail row; trailer = flush boundary |
| Excel | `sheet` kwarg | in-memory | `pl.read_excel` then openpyxl fallback |
| SalesProduct | `product_master_path` / `product_master`, `link_col` | chunked read, concat | left-join product master on resolved key |

---

## 5. The Common Contract — `ParsedResult` (parser/base.py:26)

```python
@dataclass
class ParsedResult:
    canonical_data: Optional[pl.DataFrame]
    metadata: Dict[str, Any]          # parser name, file_type, record_types, ...
    discovery: Optional[DiscoveryResult]
    record_tree: Optional[RecordTree] # record_based only
    schema: Optional[List[str]]
    warnings: List[str]
    _parsed_data: Optional[pl.DataFrame]  # pre-canonical detail rows (record_based)
```

Methods/properties: `columns` (schema or canonical_data.columns), `is_empty`,
`to_dataframe()` (returns `canonical_data`), `expose_parsed_preview()` (returns
`_parsed_data` if present, else `to_dataframe()` — UI preview path).

**Every parser returns a polars DataFrame** (possibly empty). The schema is intentionally
loose — parsers do not apply the canonical schema; that happens in the canonical layer.

---

## 6. Flattening

- **`parser/` meaning:** converting multi-record files into row-per-detail flat data by
  carrying parent context into children (record tree flatten or chunk flatten).
- **`_parsers.py` flatteners:** `flatten_multiline_chunks` (delimited H/D/T),
  `flatten_multiline_fixed_width` (header+detail+trailer; chunk_size ignored when trailer
  active — flushed per trailer).
- **`flatten.py` `FlattenEngine`:** declared flatten abstraction, but **broken** — it
  passes a `rejection_collector=` kwarg that `_parsers` functions do not accept; calling
  it raises TypeError. Unused dead code.

---

## 7. Chunking / Large-File Strategy

- `DEFAULT_CHUNK_SIZE = 100_000` (config.py:3); `ParseOptions.chunk_size = 100_000`
  (options.py:51) — but `chunk_size` is **not actually plumbed** into `canonical_chunk_stream`
  (stream functions use the module default).
- `parser/` classes default `chunk_size=10_000` (`kwargs.get("chunk_size") or 10_000`).
- Production path (`canonical_chunk_stream`) has:
  - **Fast path** (delimited, start_line==0, no record_type, direct-path source):
    `pl.scan_csv(infer_schema_length=0, low_memory=True)` → lazy `with_columns`
    normalization → single `lazy.collect(engine="streaming")`. This is the only true
    vectorized out-of-core path.
  - **General path:** `iter_chunks` → per-type chunk parsers → `normalize_*_chunk`
    per chunk. Aggregators keep only small per-chunk aggregates (memory-bounded).

**Gap:** the `parser/` package collects all chunks and `pl.concat`s them in memory;
`RecordBasedParser` holds the entire file as a Python object tree. A 500 MB HEB file
through RecordBasedParser is fully resident in memory multiple times.

---

## 8. Known Defects

| # | Severity | Finding |
|---|----------|---------|
| 1 | High | Two canonical entry points: `CanonicalDataset.from_parse_options` (production, normalizer applied) vs `from_discovery` (parser-driven, no canonical renaming/normalization). |
| 2 | High | `RecordBasedParser` is in-memory end-to-end (violates 500 MB+ guidance). |
| 3 | Medium | `parser/` classes import legacy `_parsers` directly — the "new" layer depends on the "legacy" one. |
| 4 | Medium | `record_based._open` hardcodes `utf-8`; the rest of the app uses `cp1252`/`utf8-lossy`. |
| 5 | Medium | `ExcelParser` never selected via `recommended_parser`; only reachable through `supports()`. |
| 6 | Medium | `SalesProductParser` performs a join (aggregation/relationship concern) inside the parser. |
| 7 | Medium | `has_header` is never consumed by any parser — row 0 is always treated as header. |
| 8 | Medium | `_parsers._split_parent_child` re-detects the parent at parse time (duplicate classification). |
| 9 | Low | `warnings` lists in DelimitedParser/ParentChildParser are dead (always empty). |
| 10 | Low | `record_based.py` uses inline `__import__("re")`. |
| 11 | Low | Chunk-size mismatch: parser/ default 10k vs engine default 100k. |

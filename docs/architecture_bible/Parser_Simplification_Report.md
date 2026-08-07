# Parser Simplification Report

**Status:** Sprint 3 deliverable — parsers consume transformed data only

---

## 1. Before vs After

### Before (workflow-centric)

Transformations lived inside parsers and the UI:

```
Discovery → UI → Flatten → Parser → Canonical
```

Parsers flattened, joined, detected relationships, removed disclaimers,
ignored trailers, and replicated parents.

### After (data-centric)

```
Discovery → DatasetGraph → TransformationPlan → TransformationEngine →
RecordBasedParser → ParsedDataset → CanonicalDataset
```

Parser responsibility is now:

1. **Read transformed records.**
2. **Interpret fields.**
3. **Create ParsedDataset.**

A parser MUST NOT flatten, join, detect relationships, remove disclaimers,
ignore trailers, or replicate parents.

---

## 2. Parser Contract Change

`ParserFactory.parse(discovery, source=..., transformed=...)` accepts a new
`transformed` kwarg carrying the `TransformedDataset`. All parsers accept
`**kwargs`, so direct callers are unaffected.

### Parser behaviour when `transformed` is present

| Parser | Behaviour |
|--------|-----------|
| `record_based.py` | `_parse_transformed`: no record-tree reshaping; applies column names; metadata `transformed: True` + operations list |
| `sales_product.py` | Consumes transformed records; `joined = bool(transformed.join_operations)` |
| other parsers | Fall through to existing logic (no transformed handling needed) |

### Parser behaviour when `transformed` is absent

The legacy direct-parse path is fully preserved for backward compatibility
(e.g. UI previews, certification tests, direct API calls).

---

## 3. What Was Removed From Parsers

- Record-based reshape decisions are **delegated** to the engine — the
  parser reads already-flattened rows.
- Sales+Product join logic is **delegated** to the engine — the parser just
  notes whether a join ran.
- No new parse-side disclaimers/trailer handling: header removal and trailer
  drops happen in the Transformation Engine.

---

## 4. Simplification Benefits

- Parsers are smaller, single-responsibility modules.
- Business rules exist in exactly one place (the engine), not scattered
  across parser variants.
- New retailers add a **Discovery** + **TransformationPlan** tweak, never a
  new parser reshuffle.
- Parsing is now purely mechanical: transformed records → fields →
  `ParsedDataset`.

---

## 5. Verification

`tests/test_pipeline.py` covers:

- `test_transformation_engine_flattens_multiline_delimited` — engine flattens
  before the parser sees the file.
- `test_full_pipeline_runs_transformation_end_to_end` — record-based file
  completes `transformation_engine` → `parser_pipeline` → `canonical_dataset`
  → `aggregation` with zero UI interaction.
- `test_transformation_engine_applies_product_join` — join applied before
  parsing.

Full suite: **314 passed**.

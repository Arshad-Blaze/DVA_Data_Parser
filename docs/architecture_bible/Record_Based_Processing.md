# Record-Based Processing (HEB)

How HEB (and similar multi-record / header-detail-trailer) files are handled end to end.

---

## 1. The HEB File Shape

Typical record-based file (fixed-width or delimited):

```
HDR0012024-01-15          → HDR = header (parent)
S001S0012024-01-15        → S   = store record
U001100001Widget A        → U   = UPC detail record
T00002000020149.85        → T   = trailer (transaction boundary)
```

Record types observed: `HDR`/`S`/`U`/`T` (fixed-width HEB), `H|`/`D|`/`T|` (delimited
H/D multiline), `HDR`/`D`/`TRL` (header/detail with trailer).

---

## 2. Detection Side

`is_multiline_record` (detection.py:632) classifies these as `file_type="multiline"`
via the decision tree in `Discovery_Architecture.md`. Then:
- `detect_hdr_prefix` → `HDR`
- `detect_fixed_width_detail_prefixes` → `S`, `U`, `D`
- `detect_record_types` → `ml_record_types`
- `detect_trailer_prefix` → `T` / `TRL`

`recommend_parser` maps `multiline` → `record_based` (or `parent_child` when
`header_prefix` + `detail_layout` is set and the file is not flagged multiline).

---

## 3. RecordBasedParser (`parser/record_based.py`)

### 3.1 Classify prefixes (`_classify_prefixes`, :69-109)

1. Trailers = `record_prefix` + `trailer_prefix`.
2. If `ml_record_types` empty → `_discover_record_prefixes()` samples ≤200 lines and
   returns distinct leading alphabetic prefixes.
3. If `header_prefix` present among candidates → it is the sole parent; everything else
   is detail.
4. Else `_autodetect_parent()` (:189): the parent is the record type that occurs
   **least often** (one-per-transaction heuristic; ties → earliest first-index).
   Fallbacks: details = `fixed_width_detail_prefixes or ["D"]`, parents = `["HDR"]`.

### 3.2 Build tree (`_build_tree`, :111-155)

- Streams lines from `file_paths[0]` only (multi-file sets beyond the first are ignored).
- Classifies each line: **trailer → parent → detail**.
- Parent lines become children of the tree root and set `current_parent`; details and
  trailers attach to `current_parent` (or root).
- Trailer lines become `TRAILER` nodes — boundaries, never emitted as rows.

### 3.3 Flatten

`tree.flatten_details()` (record_tree.py:90) emits one row per detail node, merging
parent fields into each leaf; trailers are excluded. Result is a polars DataFrame.

### 3.4 Field extraction

`_extract_fields` (:242) applies a fixed-width layout when present (`numeric` type
strips leading zeros). Without a layout it stores `{"raw": line}`. **Note:** unlike
`_parsers._parse_fields`, it does not handle `date` type conversion.

### 3.5 File opening

`_open` (:235) hardcodes `encoding="utf-8", errors="ignore"` — inconsistent with the
rest of the app (`cp1252` default).

### 3.6 Output

`ParsedResult` with `record_tree=tree`, metadata `record_types`, `parent_type`,
`detail_type`, `detail_row_count`, `header_count`, and `_parsed_data` so
`expose_parsed_preview()` returns the flattened detail rows for the UI schema editor.

---

## 4. RecordTree (`parser/record_tree.py`)

- `RecordNode(record_type, line_number, fields, children, raw, parent)` — `flatten()`
  recursively merges parent fields (prepended) into each leaf; `walk()` depth-first;
  `descendant_count()`.
- `RecordTree(root="file", record_types, detail_type, parent_type, trailer_type)` —
  `add(node)` attaches under root; `detail_nodes()`; `flatten_details()` emits a row per
  parent's children plus standalone leaf details; trailers never emitted;
  `to_dict()` for diagnostics.

---

## 5. ParentChildParser (alternate path, `parser/parent_child.py`)

When `ml_flattened` or `header_prefix`+`detail_layout`:
- **Fixed-width:** `_parsers.flatten_multiline_fixed_width(header_prefix, header_layout,
  detail_layout, trailer_prefix, trailer_layout)` — header cached and merged into each
  detail row; trailer = transaction boundary → flush.
- **Delimited:** `_parsers.flatten_multiline_chunks(rtypes or ["H","D"], delimiter)`
  — parent prefix row carried forward into children.

No tree; chunked and streaming, unlike RecordBasedParser.

---

## 6. Intermediate Objects & Dataset Paths

```
RecordBasedParser / ParentChildParser
  ↓ ParsedResult (canonical_data, _parsed_data, record_tree)
  ↓
CanonicalDataset.from_discovery(discovery, ...)   [parser-driven canonical path]
  ↓ streams the whole ParsedResult as one chunk (no normalizer applied)
  ↓
UI: expose_parsed_preview() → schema editor → apply schema
```

For the **production aggregation path**, HEB-style files also flow through
`CanonicalDataset.from_parse_options` → `canonical_chunk_stream` using
`flatten_multiline_chunks` / `flatten_multiline_fixed_width` (chunked, streaming).

---

## 7. Intended vs Actual

| Intended architecture (ARCHITECTURE.md / docs) | Actual implementation |
|------------------------------------------------|-----------------------|
| Discovery determines record hierarchy; parser consumes it | Partly true: RecordBasedParser trusts `ml_record_types`/`header_prefix`, but also re-discovers prefixes and auto-detects the parent at parse time when the hints are missing. |
| Parser returns structured data to the canonical layer | True via `ParsedResult`; but the parser-driven canonical path skips canonical normalization, so columns may stay physical. |
| Streaming for 500 MB+ files | **Violated:** RecordBasedParser is fully in-memory (tree of Python objects → list → DataFrame). |
| One parser engine | Two stacks; `parser/` delegates to `_parsers.py`. |
| Encoding consistent | **Violated:** RecordBasedParser hardcodes utf-8. |

---

## 8. Retailer HEB coverage summary

| Aspect | Status |
|--------|--------|
| Record types (HDR/S/U/T) | auto-detected (`detect_record_types`, `detect_fixed_width_detail_prefixes`) |
| Hierarchy / tree construction | `RecordTree` parent→child |
| Parent/child detection | `header_prefix` else least-frequent-type heuristic |
| Flattening | `flatten_details()` — parent merged into detail, trailers dropped |
| Fixed-width HEB | supported via detail layout |
| Delimited HEB (`H\|`/`D\|`) | supported via `flatten_multiline_chunks` |
| Certification dataset | `retailer_certification/record_based/retailer_heb` |
| Gap | in-memory parsing; utf-8 hardcoded; multi-file sets beyond `[0]` ignored |

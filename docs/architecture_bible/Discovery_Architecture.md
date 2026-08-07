# Discovery Architecture

How the Discovery layer works, what it detects, the algorithms, the decision tree, and
the `DiscoveryResult` contract.

---

## 1. What Discovery Detects

| Aspect | Function | Details |
|--------|----------|---------|
| File Type | `detect_file_type` (detection.py:541) | `.xlsx/.xls` → excel; else delimiter scoring → `delimited` or `fixed` (fallback) |
| Delimiter | `detect_delimiter_scores` (:521) | quote-aware counts of `, \| \t ;` over first 5 lines; highest total wins |
| Encoding | `detect_encoding` (:83) | byte-probe 1024 bytes: cp1252 → utf-8 → utf8-lossy → latin-1 |
| Header | `has_header` (:803) | first-line cells ≥50% alphabetic |
| Trailer | `detect_trailer_prefix` (:819) | candidates `TRL, TR, T, TL, TRAILER, F`; ≥2 lines with prefix + digit/delim |
| Record Types | `detect_record_types` (:783) | single alpha prefix followed by delimiter |
| Fixed Width | `detect_record_length` (:135) + `detect_candidate_layout` (:304) | most-common line length ≥60% consistency; scored boundaries |
| Multiline | `is_multiline_record` (:632) | decision tree (below) |
| Relationships | `detect_relationship_keys` (:1472) | cross-file join suggestions by matching key types |
| Layouts | `detect_candidate_layout` | `{field, start, end, length, type, from}` |
| Confidence | `compute_confidence_score` (:843) | 1.0 minus penalties |
| Parser Recommendation | `workflow.discovery.recommend_parser` | string consumed by ParserFactory |

Also detected: disclaimer lines, start line, record prefix, HDR prefix, fixed-width
detail prefixes, candidate business keys, date columns, quantity columns, weight
columns, UOM columns, and candidate column→role mapping.

---

## 2. The Discovery Entry Point

```
workflow/discovery.py::detect_file(file_paths, source) → DiscoveryResult
   ├── fp = file_paths[0]                       (first file only)
   ├── summary = detection.generate_detection_summary(fp, source)
   ├── map summary dict → DiscoveryResult fields
   ├── if fixed and no candidate_layout → error set
   ├── candidate_columns = detect_candidate_columns(result.columns)
   ├── recommended_parser = recommend_parser(result)
   └── file_architecture = _file_architecture(result)
```

Downstream hand-off: `DiscoveryResult.apply_to_context(ctx)` copies all fields onto the
`ProcessingContext` (used by certification runner). In the UI, results are spliced onto
the context manually.

---

## 3. Multiline Decision Tree (`is_multiline_record`, detection.py:632-722)

Reads 10 stripped lines; checks in order:

1. **Header guard** — if first line ≥40% "long names" (alpha tokens ≥3 chars), it's a
   plain CSV header → not multiline.
2. **Delimited prefix test** — lines matching `[alpha][,|\t;]`, ≥2 distinct prefixes and
   ≥40% of lines, not a header → **True** (e.g. `H|`, `D|`).
3. **Backslash continuation** — ≥5 lines ending with `\` → **True**.
4. **Fixed-width multi-char HDR** — prefix `line[:i]` all-alpha followed by a digit;
   repeated on ≥2 lines, ≥2 data lines, no delimiters in data lines → **True**.
5. **Single-char prefix tests** — uppercase alpha at pos 0 followed by digit:
   - ≥2 distinct single-char prefixes (S/U, D/U…) + ≥2 data lines + no delimiters → **True**;
   - ≥1 repeated multi-char HDR + ≥1 single-char prefix + no delimiters → **True** (HDR+D+TRL).
6. Otherwise → **False**.

---

## 4. Fixed-Width Boundary Algorithm

`_detect_column_boundaries(lines, record_length)` (detection.py:167):

- Each position is scored: `space_ratio*0.5 + type_transition_ratio*0.3 + separator_bonus*0.2`.
- A boundary is placed when score ≥0.3 (0.6×0.5) or a gap (space_ratio>0.8) with score
  ≥0.3; minimum column width 2.
- Column types inferred: ≥80% digits → numeric; ≥60% date-like → date; else text.

---

## 5. Business-Key Detection

`detect_candidate_keys` (detection.py:1371):

- Per column: uniqueness score (capped at uniqueness/0.5), name match (keyword exact or
  word-overlap), pattern match (over up to 50 values).
- Combined: `uniqueness*0.4 + name*0.3 + pattern*0.3`; kept if ≥0.2; one best key type
  per column.
- `detect_relationship_keys` (:1472) pairs source/target keys of the same key type.
  **Note:** it is implemented but never invoked by `detect_file`; `suggested_joins` is
  never populated. Only `workflow/relationship.py:50` calls it (tests only).

---

## 6. Confidence Scoring

`compute_confidence_score(detection_result)` (detection.py:843):

| Condition | Penalty |
|---|---|
| `file_type is None` | return 0.0 |
| `file_type == "fixed"` | −0.30 |
| delimited, chosen delimiter scored 0 | −0.30 |
| delimited, best < next_best × 2 (ambiguous) | −0.15 |
| multiline, no header_prefix and no ml_record_types | −0.20 |
| multiline, no trailer_prefix | −0.10 |
| delimited, no header | −0.10 |

Excel → 1.0 (hardcoded early return). `compute_confidence_breakdown` mirrors the rules
as human-readable strings, displayed in the UI.

---

## 7. `DiscoveryResult` Contract (workflow/discovery.py:48)

Plain class, 32 constructor params, all defaulted:

`file_paths`, `file_type`, `delimiter`, `columns`, `schema`, `header_prefix`,
`header_layout`, `detail_layout`, `trailer_prefix`, `trailer_layout`, `ml_record_types`,
`ml_delimiter` ("|"), `ml_flattened` (False), `start_line` (0), `record_type`, `layout`,
`record_length`, `candidate_layout` ([]), `disclaimer_lines` ([]), `record_prefix` ([]),
`fixed_width_detail_prefixes` ([]), `candidate_keys` ([]), `suggested_joins` ([]),
`recommended_parser`, `file_architecture`, `product_master_path`, `error`,
`confidence` (0.0), `candidate_columns` ({}), `warnings` ([]), `recommendations` ([]),
`confidence_breakdown` ([]).

Class methods:
- `from_context(ctx)` — rebuild from any object exposing the same attribute names.
- `apply_to_context(ctx)` — writes all fields onto a ProcessingContext (schema =
  schema or columns).

**Fields dropped in the dict→DiscoveryResult mapping** (computed by detection but never
carried): `encoding`, `has_header`, `date_columns`, `quantity_columns`,
`weight_columns`, `uom_columns`, `_delimiter_scores`. As a consequence, the UI/
config_builder re-derives encoding and header separately.

---

## 8. DetectionResult dict (informal) — generate_detection_summary

Plain dict seeded at detection.py:964-988, keys: `file_path, file_type, delimiter,
encoding, is_multiline, has_header, header_prefix, trailer_prefix, ml_record_types,
record_length, candidate_layout, disclaimer_lines, start_line, record_prefix,
candidate_keys, date_columns, quantity_columns, weight_columns, uom_columns, columns,
confidence, warnings, recommendations`. Dynamic keys: `_delimiter_scores`,
`fixed_width_detail_prefixes`, `confidence_breakdown`.

---

## 9. Parser Recommendation (`recommend_parser`, discovery.py:20-45)

1. `file_type == "multiline"` → `"record_based"`
2. `ml_flattened` OR `file_type == "multiline"` OR (`header_prefix` and `detail_layout`)
   → `"parent_child"`  *(the `file_type=="multiline"` clause is unreachable — branch 1
   catches it)*
3. `file_type == "fixed"` → `"fixed_width"`
4. `product_master_path` and delimited/csv/tsv → `"sales_product"`
5. fallback → `"delimited"`

**Known gaps:** `"excel"` is never recommended; `"sales_product"` unreachable via plain
detection (product_master_path is never set); parent_child is only reachable via
`ml_flattened` or header_prefix+detail_layout on non-multiline results.

---

## 10. Known Defects in Discovery

| # | Severity | Finding |
|---|----------|---------|
| 1 | High | `config_builder.py` re-runs detection heuristics (`detect_encoding`, `is_multiline_record`, `detect_file_type`, `detect_hdr_prefix`, `detect_record_types`, `has_header`) — duplicates the "detect once" contract. Stage builders re-run unconditionally. |
| 2 | Medium | `detect_delimiter_scores` runs twice inside one `generate_detection_summary` call. |
| 3 | Medium | `detect_start_line` re-runs `detect_disclaimer_lines` internally. |
| 4 | Medium | Multiline files get `columns=[]` (column/key/date detection gated to delimited/fixed) → empty candidate_columns for HEB. |
| 5 | Medium | Excel gets confidence 1.0 with no columns/header/structure detected. |
| 6 | Medium | `config_validator.validate_config` rejects `"excel"` (only allows delimited/fixed/multiline) though detection produces it. |
| 7 | Low | `workflow/discovery._get_delimited_columns` is dead duplicate of column extraction. |
| 8 | Low | Unused imports in workflow/discovery.py. |
| 9 | Low | `LayoutRegistry` (layout_registry.py) is entirely orphaned dead code. |
| 10 | Low | Vocabulary drift: parser `supports()` accepts "csv"/"tsv"/"tab"; detection only produces "delimited". |

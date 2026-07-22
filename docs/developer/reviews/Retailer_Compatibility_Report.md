# Retailer Compatibility Report

## Scenarios Evaluated

| Scenario | Status | Notes |
|----------|--------|-------|
| Simple delimited | ✅ Supported | `parse_delimited_chunks` / `scan_delimited` |
| Delimited with quotes | ✅ Supported | `_count_delimiters_outside_quotes` in detection.py |
| Delimited with blank values | ✅ Supported | csv reader handles empty fields |
| Fixed-width | ✅ Supported | `parse_fixed_width_chunks` with layout |
| Fixed-width with uploaded layout | ✅ Supported | `load_layout` + layout builder upload |
| Fixed-width with manually built layout | ✅ Supported | `render_layout_builder` |
| Multiline fixed-width (HDR) | ✅ Supported | `flatten_multiline_fixed_width` |
| Record-type files (HDR/S/U/T/TRL) | ✅ Supported | `flatten_multiline_chunks` |
| Sales + Product Master (two-file) | ✅ Supported | Existing flow with prod/test comparison |
| Units only | ✅ Supported | `quantity_type="units"` |
| Weight only | ✅ Supported | `quantity_type="weight"` |
| Mixed units + weight | ✅ Supported | `quantity_type="mixed"` |
| Large streaming files | ✅ Supported | Chunked iteration with configurable chunk_size |

## Unsupported Scenarios

**None identified.** All retailer scenarios collected during the architecture phase are supported.

## Scenario Details

### Delimited Files
- Auto-detected delimiters: `,`, `|`, `\t`, `;`
- Header detection via alphabetic column name analysis
- Start line / disclaimer line auto-detection
- Column name-based schema inference
- Canonical mapping: Store, UPC, Description, Units, Price

### Fixed-Width Files
- Auto-detected record length using line-length histogram
- Auto-detected column boundaries using whitespace + character-type transitions
- Manual layout via Layout Builder or CSV upload
- Record type filtering (e.g., only "U" records)
- Multiline fixed-width with HDR prefix and trailer support

### Multiline / Record-Type Files
- Delimited multiline (H|D|U|T|TRL)
- Fixed-width HDR (header prefix + detail records + optional trailer)
- Record types: configurable comma-separated list
- Flattening merges header fields into detail rows
- Trailer prefix: auto-detected with fallback to manual input

### Quantity Handling
- `units`: count-based (quantity column only)
- `weight`: weight-based (weight column + weight UOM)
- `mixed`: both units and weight with resolution rule
- Implied units/dollars (divide by 100)

### Two-File Ingestion
- Sales + Product Master via Format Change workflow
- Discovery comparison and schema diff between BAU and Test
- Side-by-side column mapping
- Aggregation comparison

## Architectural Extensions Required for Full Support

**None.** The current architecture supports all scenarios via configuration only:
- `FormatConfig` JSON files capture per-retailer settings
- Layout CSVs define fixed-width column positions
- Record types and delimiters are parameterized
- Schema mapping is user-configurable in the UI

## Configuration-Only Deployment

Per the PROMPT requirement: "No supported retailer should require code changes. Only configuration should differ."

Each retailer profile consists of:
1. `FormatConfig` JSON (file type, delimiter, start_line, record_type, column mapping, quantity settings)
2. Optional layout CSV (fixed-width column definitions)
3. Optional multiline record type configuration
4. Validation rule settings

These can be loaded via the "Load Config" button in the UI, bypassing all manual setup.

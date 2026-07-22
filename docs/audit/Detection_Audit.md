# Detection Audit

## Current Detection Capabilities

| Feature | Supported | Confidence | Notes |
|---------|-----------|------------|-------|
| Delimited file detection | ✅ Yes | High | Scans 5 lines, counts delimiters |
| Delimiter auto-detection | ✅ Yes | High | Checks `, | \\t ;` |
| Fixed-width detection | ✅ Yes | Low | Fallback when no delimiter found |
| Excel detection | ✅ Yes | High | File extension check |
| Multiline detection | ✅ Yes | Medium | Alpha prefix, backslash, HDR patterns |
| Header detection | ✅ Yes | Medium | Alpha character ratio in first line |
| Trailer prefix detection | ✅ Yes | Medium | Checks predefined candidates |
| HDR prefix detection | ✅ Yes | Medium | Multi-char alpha prefix search |
| Record type detection | ✅ Yes | Medium | Single-char alpha prefixes |
| Candidate column mapping | ✅ Yes | Medium | Keyword-based heuristics |
| Confidence scoring | ✅ Yes | Medium | Composite score |
| Encoding detection | ❌ No | — | Uses hardcoded cp1252 |
| Start line detection | ❌ No | — | Always starts at 0 |
| Record length discovery | ❌ No | — | Fixed-width only |
| Layout discovery | ❌ No | — | Fixed-width only |
| Business key detection | ❌ No | — | UPC/SKU/etc |
| Join key detection | ❌ No | — | Cross-file relationships |
| Disclaimer detection | ❌ No | — | Retailer 3 scenario |
| Quantity column detection | ⚠️ Partial | Low | Basic keyword match |
| Weight column detection | ⚠️ Partial | Low | Basic keyword match |
| UOM column detection | ⚠️ Partial | Low | Basic keyword match |
| Date column detection | ❌ No | — | |
| Multiline hierarchy detection | ⚠️ Partial | Low | HDR prefix only |
| Store column detection | ⚠️ Partial | Low | Basic keyword match |
| UPC column detection | ⚠️ Partial | Low | Basic keyword match |

## Key Gaps

1. **No record-length detection for fixed-width** — Detection identifies "fixed" but provides no layout. The UI Layout Builder becomes mandatory, which blocks the "No Layout Available Initially" scenario (Retailer 2).

2. **No disclaimer handling** — Retailer 3 has disclaimer lines. Detection should identify and skip them.

3. **No start_line detection** — Files with leading non-data lines aren't handled automatically.

4. **No candidate business key detection** — UPC, SKU, Item Code columns are not specifically identified as potential join keys. This blocks the Sales + Product Master scenario.

5. **No date column detection** — Important for business reporting and relationship joins.

6. **Encoding is hardcoded** — `DEFAULT_ENCODING = "cp1252"` and `FALLBACK_ENCODING = "utf8-lossy"`. Should detect or allow user override.

## Detection Statistics

Detection runs `generate_detection_summary()` once per file. The `DiscoveryResult` is stored on the context and downstream layers consume it without re-detecting. This matches the architecture requirement.

## Recommendations

1. Add `detect_record_length()` for fixed-width files — scan lines to find consistent length
2. Add `detect_candidate_layout()` for fixed-width — propose column positions based on whitespace patterns
3. Add `detect_disclaimer_lines()` — find non-data prefix lines
4. Add `detect_date_columns()` — pattern matching for date formats
5. Add `detect_candidate_keys()` — identify high-uniqueness columns as potential business keys
6. Add encoding detection or user-configurable encoding
7. Improve confidence scoring with new detection dimensions

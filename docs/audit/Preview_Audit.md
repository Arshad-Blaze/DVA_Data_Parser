# Preview Audit

## Preview Types

| Preview Type | Location | Status | Notes |
|-------------|----------|--------|-------|
| Raw lines | `_parsers.py:preview_raw_lines()` | ✅ Working | Shows raw text lines |
| Raw (parsed) | `_parsers.py:preview_raw()` | ✅ Working | Shows delimited/fixed/multiline as DataFrame |
| Flattened multiline | `_parsers.py:preview_flattened_multiline()` | ✅ Working | Record-type flattened |
| Flattened multiline fixed | `_parsers.py:preview_flattened_multiline_fixed()` | ✅ Working | HDR fixed-width flattened |
| Delimited scan | `_parsers.py:scan_delimited()` | ✅ Working | LazyFrame scan |
| Fixed-width chunks | `_parsers.py:parse_fixed_width_chunks()` | ✅ Working | Chunk-based |

## Missing Preview Types

| Preview Type | Gap | Impact |
|-------------|-----|--------|
| Canonical Preview | ❌ Missing | User cannot see canonical transformation result |
| Product Preview | ❌ Missing | Product Master file preview |
| Relationship Preview | ❌ Missing | Joined Sales + Product preview |
| Streaming Preview | ❌ Missing | Large file preview without full read |
| Quantity Preview | ❌ Missing | See resolved quantity (units vs weight vs both) |

## Caching

Preview caching is implemented in `ui/helpers.py`:
- `cached_preview_raw()` — MD5-keyed cache in session state
- `cached_preview_raw_lines()` — MD5-keyed cache in session state
- `cached_get_column_names()` — MD5-keyed cache in session state

### Findings

1. **PA-1: Cache key doesn't include source** — Cache key uses file paths but not the data source. Same path from different sources (local vs SSH) could return stale results.

2. **PA-2: No canonical preview** — After column mapping, there's no way to preview the canonical output before running full processing.

3. **PA-3: No invalidation mechanism** — Cache entries live until session expires or app reruns. No explicit invalidation when file content changes.

4. **PA-4: Memory growth** — Large preview DataFrames cached in session state could cause memory issues.

5. **PA-5: No streaming preview** — All previews read full sample into memory before display.

6. **PA-6: Fixed-width preview requires layout** — If no layout exists, there's no way to preview raw parsed data to help define layout.

## Recommendations

1. Add canonical preview — run `canonical_chunk_stream` for small sample with current mapping
2. Add streaming preview for large files — use LazyFrame.fetch() or chunk-based
3. Include data source identity in cache keys
4. Add cache invalidation when mapping/configuration changes
5. Add raw fixed-width preview without layout (show as single-column text)
6. Add quantity preview showing how units/weight are resolved

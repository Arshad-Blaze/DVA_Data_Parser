# Execution Flow

## Onboarding (Single Dataset)

```
START → Step 1: Connection
         │
         ▼
Step 2: Discovery (detect file type, delimiter, columns)
         │
         ▼
Step 3: Configuration (progressive config wizard)
         │
         ▼
Step 4: Config Validation
         │
         ▼
Step 5: Processing
         ├─ Store Aggregation (parallel)
         └─ Item Aggregation (parallel)
         │
         ▼
Step 6: Validation (store compare, UPC summary, file review)
         │
         ▼
Step 7: Reports
         │
         ▼
END
```

### Detailed Phase Flow

#### Phase 1: Discovery
1. User selects folder path or uses Connection Manager path
2. If config JSON provided: load and apply
3. If no config: `detect_file()` runs detection
4. Detection identifies: file type, delimiter, multiline flags
5. For fixed-width: shows Layout Builder instead of requiring CSV
6. For multiline: raw preview → flatten → schema definition
7. Column names detected from sample
8. Context populated and phase advances to Configuration

#### Phase 2: Configuration
1. `build_config()` runs on a sample of the data
2. Progressive sections rendered: General, File, Physical Schema, Canonical Schema, Business Mapping, Quantity, Validation, Output
3. User edits and accepts configuration
4. Config locked and phase advances

#### Phase 3-4: Processing
1. ParseOptions + ColumnMapping built from context
2. Store and Item aggregation run in parallel via ThreadPoolExecutor
3. Each calls `canonical_chunk_stream()` → normalizes → aggregates
4. Results stored on context

#### Phase 5-6: Validation + Reports
1. Store validation, UPC summary, file review run
2. Results displayed with download options

## Format Change (Two Dataset Comparison)

Same flow as Onboarding but with two parallel pipelines (BAU + Test) followed by schema comparison and migration report.

## Canonical Chunk Stream

```python
canonical_chunk_stream(file_paths, file_type, ...)
  ├─ Fast Path (delimited, simple): polars LazyFrame with normalization exprs
  └─ Slow Path (all formats): iter_chunks() → normalize_chunk()
       ├─ delimited: parse_delimited_chunks()
       ├─ fixed: parse_fixed_width_chunks()
       └─ multiline:
            ├─ HDR: flatten_multiline_fixed_width()
            └─ delimited: flatten_multiline_chunks()
```

## Numeric Conversion (RC2)

`safe_numeric()` now handles:
- Empty strings → null
- NULL, N/A, NA, NaN, INF → null
- Dashes, spaces → null
- Configurable behavior via `NumericHandling`: AS_NULL (default), AS_ZERO, REJECT

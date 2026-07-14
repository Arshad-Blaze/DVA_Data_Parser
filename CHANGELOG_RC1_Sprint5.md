# Changelog — RC1 Sprint 5 (Processing Layer)

## Architecture

### Processing Layer now consumes ONLY Canonical Dataset + Operation Context

All file-format details (delimiter, encoding, header, fixed-width, multiline,
retailer schema) are fully encapsulated behind `canonical_chunk_stream()` in
`dav_tool/_parsers.py`. The Processing Layer (`_aggregators.py`,
`workflow/processing.py`) never references them.

**Before:** Three streaming functions (`stream_store_aggregate`,
`stream_item_aggregate`, `stream_upc_summary`) each had 25+ parameters
including delimiter, layout, start_line, record_type, multiline_*,
header_*, trailer_*. Each maintained its own fast/chunk path dispatch.

**After:** A single `canonical_chunk_stream()` in `_parsers.py` handles all
parsing + normalization. Three thin `_aggregate_*_stream()` helpers consume
only canonical chunks.

## Added

- **`canonical_chunk_stream()`** in `_parsers.py` — produces iterator of
  canonically-normalized DataFrames. Hides all format details. Supports
  fast path (delimited LazyFrame) and chunk path (all types).
  (`_parsers.py`)

- **`iter_chunks()`** in `_parsers.py` — moved from `_aggregators.py` to
  correct layer. (`_parsers.py`)

- **`run_raw_review()`** in `workflow/processing.py` — new Raw Review
  operation: preview first N rows of canonical data from a file.
  (`workflow/processing.py`)

- **`OutputMode.RAW_REVIEW`** and **`OutputMode.AGGREGATE_CALCULATE`** —
  new output modes for the processing pipeline. (`options.py`)

- **Performance instrumentation** — `ProcessingMetrics` fields for CPU and
  RAM are populated throughout the pipeline. (`_observability.py`)

## Changed

- **`_aggregators.py`** — completely restructured. Three streaming functions
  replaced by three `_aggregate_*_stream()` helpers that consume only
  canonical chunk iterators. `aggregate()` is the single entry point.
  (`_aggregators.py`)

- **Backward compatibility** — `stream_store_aggregate()`,
  `stream_item_aggregate()`, `stream_upc_summary()` preserved as thin
  aliases that delegate to `aggregate(level=...)`. All callers unchanged.

## Removed (Dead Code)

- `run_store_aggregation_canonical()` — zero callers
- `run_item_aggregation_canonical()` — zero callers
- `_iter_chunks()` from `_aggregators.py` — moved to `_parsers.py`
- 900+ lines of duplicated fast/chunk path logic from three streaming functions

## Tests

- 210 unit tests: PASS
- 12 golden tests: PASS
- All operation modes: RAW_REVIEW, AGGREGATE_ONLY, AGGREGATE_CALCULATE, VALIDATE

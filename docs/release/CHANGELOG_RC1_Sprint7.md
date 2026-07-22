# Changelog — RC1 Sprint 7: Data Access Strategy

## New

- **DataAccessStrategy module** (`dav_tool/workflow/data_access.py`)
  - `AccessStrategy` enum: DIRECT_STREAM, BATCH_COPY, SEQUENTIAL_COPY, CHUNK_STREAM
  - `DataAccessor` class: transparent IDataSource wrapper with automatic strategy
  - `wrap_source()`: convenience helper for processing functions
  - `_with_retry()`: retry decorator with exponential backoff (3 retries)
  - `cleanup_all()`: lifecycle cleanup integration with `flush()`

- **Automatic strategy selection** based on runtime resource profiling:
  - Available RAM (`psutil`)
  - Free disk space on temp partition
  - Total dataset size (sum of `source.stat().size`)
  - File count
  - Source type (local vs remote via `supports_direct_path`)

## Changed

- **`dav_tool/_parsers.py`**: `canonical_chunk_stream()` fast path now checks
  `source.supports_direct_path` in addition to `source is None`, enabling Polars
  LazyFrame streaming for batch-copied remote files

- **`dav_tool/workflow/processing.py`**: All 4 processing functions
  (`run_raw_review`, `run_store_aggregation`, `run_item_aggregation`,
  `run_file_review`) wrap source in DataAccessor before use

- **`dav_tool/workflow/validation.py`**: Both validation functions
  (`run_onboarding_validation`, `run_existing_validation`) wrap source in
  DataAccessor via `_wrap_validation_source()` helper

- **`dav_tool/workflow/flush.py`**: Calls `cleanup_data_access()` during flush
  sequence to remove temp files from batch/sequential copy strategies

## Fixed

- Remote files that are small enough (< 50 MB total) are now batch-downloaded
  and processed via the Polars LazyFrame fast path, instead of the slower
  chunked stream path

## Backward Compatibility

- No public API changes
- No UI changes
- No configuration options exposed
- All 246 existing tests pass unchanged

# Data Access Strategy Review — Sprint 7

## Overview

Implemented an automatic Data Access Strategy layer beneath the Connection
Layer (IDataSource). The strategy is entirely transparent to users — no UI
changes, no configuration options. All decisions are based on runtime resource
profiling and logged at INFO level.

## Architecture

```
┌──────────────────────────────┐
│      UI Layer (Streamlit)     │
├──────────────────────────────┤
│     Processing Layer          │
│  (workflow/processing.py)     │
├──────────────────────────────┤
│   DataAccessor (new)          │  ← Auto-selects strategy
│   ┌────────────────────────┐  │
│   │ DIRECT_STREAM          │  │  Local files, direct I/O
│   │ BATCH_COPY             │  │  Remote small files, download all
│   │ SEQUENTIAL_COPY        │  │  Remote medium, copy one-at-a-time
│   │ CHUNK_STREAM           │  │  Remote large, stream without copy
│   └────────────────────────┘  │
├──────────────────────────────┤
│   IDataSource (Connection)    │
│   ┌────────────────────────┐  │
│   │ LocalDataSource        │  │
│   │ SSHDataSource          │  │
│   └────────────────────────┘  │
└──────────────────────────────┘
```

## Strategy Selection Logic

The `DataAccessor.resolve()` method gathers:

| Factor | Source |
|---|---|
| Available RAM | `psutil.virtual_memory().available` |
| Free disk space | `shutil.disk_usage(tempfile.gettempdir())` |
| Total dataset size | `source.stat()` per file, summed |
| File count | Number of paths |
| Source type | `source.supports_direct_path` |

Decision thresholds:

| Condition | Strategy |
|---|---|
| `supports_direct_path == True` | DIRECT_STREAM |
| RAM < 256 MB | CHUNK_STREAM |
| Disk < 2× dataset size and < 500 MB free | CHUNK_STREAM |
| Total < 50 MB | BATCH_COPY |
| Total < 500 MB and RAM > 1 GB | SEQUENTIAL_COPY |
| Otherwise | CHUNK_STREAM |

## Strategy Details

### DIRECT_STREAM
- **When**: Local source (always)
- **Behavior**: All I/O passes through to the native filesystem
- **Fast path**: Polars LazyFrame with `collect(engine="streaming")` enabled
- **Temp files**: None

### BATCH_COPY
- **When**: Remote source, total < 50 MB
- **Behavior**: All files downloaded in parallel to a managed temp directory
- **Fast path**: Enabled after download (files are local)
- **Temp files**: Cleaned up by `flush()` lifecycle

### SEQUENTIAL_COPY
- **When**: Remote source, 50–500 MB total, RAM > 1 GB
- **Behavior**: `open_stream()` downloads file to temp on first access, opens
  local copy. Subsequent accesses use cached local path.
- **Fast path**: Not enabled (chunk path used via `_open_text_stream`)
- **Temp files**: Cleaned up on accessor cleanup

### CHUNK_STREAM
- **When**: Remote source, large files or constrained resources
- **Behavior**: Streams directly from `source.open_stream()` without local copy
- **Fast path**: Not enabled (chunk path only)
- **Temp files**: None

## Retry Logic

All remote operations use `_with_retry()`:

- Up to 3 retries with exponential backoff (2s, 4s, 6s)
- Retries on any `Exception` (connection drops, timeouts, transient errors)
- After exhausting retries: raises `DataAccessError`

Affected operations:
- `open_stream()` — on CHUNK_STREAM
- `download_if_required()` — on SEQUENTIAL_COPY
- `stat()` — during resource profiling

## Connection Recovery

The retry mechanism inherently handles connection drops:
1. First attempt fails → logged as warning
2. Brief pause → retry
3. If underlying source reconnects → operation succeeds
4. If all retries fail → error propagates to caller

Cleanup via `flush()` disconnects the source regardless of state.

## Automatic Cleanup

Integration points:

1. **`DataAccessor.cleanup()`** — removes temp files, empties caches
2. **`register_accessor()`** — registers accessor for lifecycle management
3. **`cleanup_all()`** — called from `workflow/flush.py` during normal teardown
4. **Idempotent** — safe to call multiple times

## Files Modified

| File | Change |
|---|---|
| `dav_tool/workflow/data_access.py` | **New** — 310 lines |
| `dav_tool/_parsers.py` | Fast path check uses `supports_direct_path` |
| `dav_tool/workflow/processing.py` | Source wrapped in DataAccessor (4 functions) |
| `dav_tool/workflow/validation.py` | Source wrapped in DataAccessor (2 functions) |
| `dav_tool/workflow/flush.py` | Calls `cleanup_data_access()` during flush |
| `tests/test_data_access.py` | **New** — 24 tests |

## Test Coverage

- 24 new unit tests for the DataAccessor module
- Covers all strategies (DIRECT, BATCH, SEQUENTIAL, CHUNK)
- Covers retry logic (transient failures, exhaustion)
- Covers cleanup (idempotent, lifecycle)
- Covers wrap_source helper (None passthrough)
- 0 existing tests broken
- Full suite: 246 tests passing (210 unit + 24 DAS + 12 golden)

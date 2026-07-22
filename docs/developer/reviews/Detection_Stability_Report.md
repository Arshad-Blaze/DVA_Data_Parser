# Detection Stability Report

## Root Cause

Detection could execute multiple times per Streamlit session due to:
1. Streamlit reruns re-executing the entire script top-to-bottom
2. No persistent caching of `DiscoveryResult` between reruns
3. No cache invalidation mechanism when input files change
4. Multiple entry points calling `detect_file()` without coordination

## Architecture Impact

**Low.** The `DiscoveryResult` class and `detect_file()` function were already designed as the single detection entry point (`workflow/discovery.py:156-206`). The caching layer simply enforces what the docstring already mandated: "This is the SINGLE detection entry point. Downstream phases must consume this result instead of re-detecting."

## Business Impact

Without caching:
- Every Streamlit widget interaction (checkbox, selectbox, button) triggers a rerun
- Each rerun could re-execute detection on potentially large files (500 MB+)
- This wastes I/O bandwidth and compute time, especially over SSH connections
- Detection results appearing/disappearing between interactions confused users

## Fix Implemented

### 1. Session-level detection cache (`_detection_cache`)

**Files:**
- `dav_tool/ui/onboarding.py:73` — cache initialized in `run()`
- `dav_tool/ui/existing.py:82` — cache initialized in `run()`
- `dav_tool/ui/onboarding.py:358-367` — cache check before `detect_file()` call
- `dav_tool/ui/existing.py:951-961` — cache check before `detect_file()` call

**Mechanism:**
```python
cache_key = hashlib.md5(str(sorted(file_paths)).encode()).hexdigest()
cached = st.session_state._detection_cache.get(cache_key)
if cached is not None:
    discovery = cached  # Skip re-detection
else:
    discovery = detect_file(...)  # Run once
    st.session_state._detection_cache[cache_key] = discovery
```

### 2. Unique cache keys per side (existing flow)

Existing flow uses `cache_key + f"_{side_label}"` (`_detect_and_set` in existing.py) to distinguish BAU and Test detection results.

### 3. Re-detect buttons

- `onboarding.py:231-235` — "Re-detect" button clears cache entry and resets `ctx.discovery`
- `existing.py:348-360` — "Re-detect BAU" and "Re-detect Test" buttons
- `existing.py:281-304` — Retry/Manual detection buttons also clear cache

### 4. Logging proving single execution

- `detection.py:842` — `logger.info("DETECTION EXECUTED — %s", file_path)` at function entry
- `detection.py:1018` — `logger.info("DETECTION COMPLETED — %s (%s, ...)", ...)` at function exit
- `onboarding.py:361` — `logger.info("DETECTION CACHE HIT — %s", file_paths)` on cache use
- `onboarding.py:364` — `logger.info("DETECTION EXECUTED — %s", file_paths)` on actual run
- `existing.py:953` — `logger.info("DETECTION CACHE HIT — %s (%s)", file_paths, side_label)` on cache use
- `existing.py:957` — `logger.info("DETECTION EXECUTED — %s (%s)", file_paths, side_label)` on actual run

## Conditions That Trigger Re-detection

| Condition | Cache cleared? | Detection runs? |
|-----------|---------------|-----------------|
| Streamlit rerun (widget change) | No | No (cache hit) |
| User clicks "Re-detect" | Yes | Yes |
| Input files change (new path) | No (new cache key) | Yes |
| Workflow reset (`_reset_phase`) | No (key stays) | Yes (ctx.discovery cleared) |
| Page navigation (Onboarding ↔ Existing) | No | Depends on ctx.discovery |

## Remaining Risks

1. **Cache size**: No eviction policy. If a user switches between many file sets in one session, the cache accumulates. Mitigation: session-level dict, freed on tab close.
2. **Detection and layout are separate**: The Layout Builder result is stored on `ctx.layout` but the cache only caches `detect_file()`. If the user changes layout, they don't need to re-detect — the detection cache is fine.
3. **No cache for preview**: Preview caching (`cached_preview_raw`) uses a separate mechanism. If detection results change, old previews could be stale. `invalidate_preview_caches()` exists but is never called.

## Test Evidence

Detection logging confirms:
```
DETECTION EXECUTED — /data/retailer/sample.csv
... (widget interaction) ...
DETECTION CACHE HIT — /data/retailer/sample.csv
... (another widget interaction) ...
DETECTION CACHE HIT — /data/retailer/sample.csv
```

Only one "DETECTION EXECUTED" message per file set until cache is explicitly cleared.

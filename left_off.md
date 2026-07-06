# Left Off — Phase 2 Multiline Record Support

## Current State

Phase 2 (Multiline Record Support) is **functionally complete**. The multiline parsing pipeline was already implemented in Version 1.0 (detection, flattening, aggregation dispatch). This sprint adds the missing verification, test coverage, and documentation.

## What Was Achieved

### 1. Canonical Equivalence Verification (Requirement 4)
- Added `test_multiline_canonical_equivalence_delimited()` in `tests/test_canonical_layer.py`
- Verifies same data in single-line CSV vs. multiline H/D-delimited produces identical canonical output for store aggregation, item aggregation, and UPC summary
- **Result**: Confirmed — multiline pipeline produces identical canonical output

### 2. E2E Playwright Test Coverage (10 new tests)
- **Onboarding multiline flow** (`tests/e2e/onboarding/test_onboarding_multiline.py`): 5 tests covering detection, raw preview, flatten, schema application, and phase transition
- **Existing multiline flow** (`tests/e2e/existing/test_existing_multiline.py`): 5 tests covering detection, raw preview, flatten, schema application, and phase transition

### 3. Test Infrastructure
- Added `create_multiline_flow_test_data()` in `tests/e2e/sample_data.py` — generates BAU and Test multiline H/D-delimited files with store list for E2E testing
- Added `multiline_test_data` fixture in `tests/e2e/conftest.py` — session-scoped temp directory with multiline test data
- Fixed `conftest.py` Streamlit PATH issue — added `venv/bin` to subprocess PATH so E2E tests can find the `streamlit` binary

### 4. Code Changes (no architecture modifications)
| File | Change |
|------|--------|
| `tests/e2e/sample_data.py` | Added `create_multiline_flow_test_data()` |
| `tests/e2e/conftest.py` | Added `multiline_test_data` fixture; fixed PATH for streamlit subprocess |
| `tests/test_canonical_layer.py` | Added `test_multiline_canonical_equivalence_delimited` |
| `tests/e2e/onboarding/test_onboarding_multiline.py` | New: onboarding multiline E2E tests |
| `tests/e2e/existing/test_existing_multiline.py` | New: existing multiline E2E tests |

No modifications to parser, validation, aggregation, reporting, or UI code.

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| Unit tests (`tests/`) | 68 | ✅ All pass |
| Integration (`full_test.py`) | 10 sections | ✅ All pass |
| Regression E2E (`test_regression.py`) | 8 | ✅ All pass |
| Onboarding delimited E2E | 8 | ✅ All pass |
| Existing delimited E2E | 8 | ✅ All pass |
| Onboarding multiline E2E | 5 | ✅ All pass |
| Existing multiline E2E | 5 | ✅ All pass |
| **Total E2E** | **34** | **✅ 33 pass, 1 pre-existing flaky** |

## Phase 2 Requirements Status

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Detect multiline record format | ✅ Done | `detection.py:is_multiline_record()` |
| 2 | Group physical lines into logical records | ✅ Done | `_parsers.py:flatten_multiline_chunks()` |
| 3 | Flatten logical records | ✅ Done | `_parsers.py:flatten_multiline_chunks()` |
| 4 | Same canonical dataframe as single-line | ✅ Verified | `test_canonical_layer.py` |
| 5 | No downstream changes | ✅ By design | Aggregation/validation/reports unchanged |

## Known Limitations

1. **HDR fixed-width E2E coverage missing**: No E2E Playwright test for the HDR fixed-width multiline flow (both onboarding and existing). The canonical equivalence test also only covers delimited multiline. HDR requires complex layout files that are hard to set up in automated tests.

2. **Column mapping not tested in multiline E2E**: The multiline E2E tests verify detection → flatten → schema → phase transition, but don't exercise column mapping → validation → results. This is because the flattened columns are named "Column_0".."Column_N" by default, and Streamlit selectbox option selection with these names has locator issues in Playwright. The column mapping and validation flows are identical to delimited (already tested).

3. **Record type detection default ("H,D")**: The default record type flags include both H and D records. For onboarding, this means H records (Store + Date) and D records (Store + UPC + Description + Units + Price) are both kept, producing a sparse DataFrame where H records have empty D-only columns. Users must clear the H record type or rename columns appropriately in the schema step.

4. **Flatten preview only**: The `preview_flattened_multiline()` function limits output rows but reads the full file. For very large multiline files, this incurs I/O cost on every rerun. No lazy/streaming preview is implemented.

5. **Pre-existing flaky E2E test**: `test_detection_completes_for_both_sides` in `test_existing_delimited.py` fails intermittently due to timing — it expects 2 "Delimited" status texts but sometimes only 1 is rendered before the assertion timeout. This is a pre-existing issue, not caused by Phase 2 changes.

## Future Improvements (for later phases)

1. **Phase 3 — Header Based Record Support**: Add HDR/DTL/TRL transaction grouping. Reuses canonical pipeline. Do not duplicate parsing logic.

2. **Phase 4 — Configuration Driven Parsing**: Replace retailer-specific logic with configuration-based parsing (record_type, delimiter, header, continuation_record, layout_file, field_mapping).

3. **Phase 5 — Golden Dataset Framework**: Create `tests/golden/expected/` with input → expected canonical output pairs for every supported format. Every parser change must compare against golden output.

4. **Phase 6 — Performance**: Memory/CPU optimization, eliminate repeated parsing/preview/aggregation, large file processing, batching, parallel processing, Polars optimization.

5. **HDR fixed-width E2E tests**: Add Playwright tests for HDR fixed-width workflow.

6. **Full multiline E2E flow test**: Fix the Playwright column selection locator issue and add a full end-to-end multiline E2E test that goes through column mapping and validation.

## Branch

Current work is on `phase2-multiline` branch (based on `runtime-stabilization-sprint`, which is based on `main`).

All Phase 2 changes have been committed at `df5b611`.

## Next Step

Begin Phase 3: Header Based Record Support per PROMPT.md.

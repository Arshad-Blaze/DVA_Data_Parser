# Architecture Review — DVA Data Parser

## Overview

The DVA Tool (Data Analysis & Validation Tool) is a Streamlit-based application for processing and validating retail/POS data files. It handles delimited (CSV, pipe, tab, semicolon), fixed-width, and multiline (HDR) file formats with streaming/chunked processing for files up to 500MB+.

## Architecture Layers

```
UI (Streamlit)
    ↓
Parser (Detection → Parsing)
    ↓
Canonical Layer (Normalization)
    ↓
Aggregator (Store/Item/UPC)
    ↓
Validation (Business Rules)
    ↓
Reports (File Review)
```

## Entry Points

| Entry Point | Location | Purpose |
|---|---|---|
| Streamlit App | `dav_tool/ui/app.py` | Main entry, page toggle (Onboarding vs Existing) |
| Onboarding | `dav_tool/ui/onboarding.py` | Single-file-set processing workflow |
| Existing/BAU | `dav_tool/ui/existing.py` | Two-sided comparison workflow |
| Unit Tests | `tests/` | 8 test files, 68+ tests |
| Integration | `full_test.py` | End-to-end pipeline test |

## UI Workflow

Both workflows follow a 3-phase state machine (phase 0 → 1 → 2):

### Onboarding
- **Phase 0** (`_phase0_parsing_and_preview`): Enter folder path → auto-detect file type → show preview
- **Phase 1** (`_phase1_column_mapping`): Map columns (Store, UPC, Description, Units, Price) → confirm → aggregate
- **Phase 2** (`_phase2_validation`): Select validations → validate → display/download results

### Existing / BAU
- **Phase 0** (`_phase0_detection_and_preview`): Enter BAU and Test folder paths → detect both → show dual preview
- **Phase 1** (`_phase1_column_mapping`): Map columns for both sides → confirm → aggregate both
- **Phase 2** (`_phase2_validation`): Store/Item/Compare validation → results → download

## Backend Modules

| Module | File | Responsibility |
|---|---|---|
| Detection | `dav_tool/detection.py` | File type detection (delimited, fixed, multiline, HDR) |
| Parsing | `dav_tool/_parsers.py` | Delimited (LazyFrame), fixed-width (chunked), multiline flattening |
| IO | `dav_tool/io.py` | Safe CSV reader with encoding fallback |
| Normalizer | `dav_tool/_normalizer.py` | Canonical column renaming, numeric sanitization, implied decimals |
| Aggregator | `dav_tool/_aggregators.py` | Store-level, item-level, UPC summary aggregations (streaming) |
| Validation | `dav_tool/validation/` | Store comparison, item comparison, percentage differences |
| Reports | `dav_tool/_reports.py` | Per-file summary reports |
| Observability | `dav_tool/_observability.py` | Metrics, timers, memory/CPU monitoring |
| ProcessingContext | `dav_tool/processing_context.py` | State dataclasses for pipeline state |

## Session State

Session state is used for:
- `st.session_state.page` — navigation toggle (`"onboarding"` or `"existing"`)
- `st.session_state.onb_ctx` — `ProcessingContext` for onboarding
- `st.session_state.ex_ctx` — `ExistingContext` for existing workflow
- Various UI state flags (detection failures, fixed-width settings, multiline config)
- `st.session_state.execution_history` — last 10 execution records

## Processing Context Lifecycle

`ProcessingContext` is a dataclass initialized on first load and reset via "Start Over". Phase (0/1/2) drives conditional rendering. Metrics accumulate through `ProcessingTimer` context managers around each pipeline stage.

## Detection Flow

1. `is_multiline_record()` — check first lines for multi-line patterns
2. If multiline: `detect_hdr_prefix()` (HDR fixed-width) or `detect_record_types()` (delimited multiline)
3. If not multiline: `detect_file_type()` — delimiter scoring (`,` , `|`, `\t`, `;`) → "delimited" or "fixed"

## Data Formats Supported

| Format | Detection | Parsing Strategy |
|---|---|---|
| Delimited (CSV) | Delimiter scoring | `pl.scan_csv()` LazyFrame |
| Delimited (pipe, tab, semicolon) | Delimiter scoring | LazyFrame with custom separator |
| Fixed-width | No delimiters found | Chunked character-position parsing with layout CSV |
| Multiline Delimited (H/D) | Multi-line prefixes | Record-type filtering + delimiter split |
| HDR Fixed-width | Multi-char alphabetic prefix | Header-carried-forward chunked parsing |

## Key Design Decisions

1. **Two processing paths**: Delimited → lazy (Polars streaming); Fixed/Multiline → chunked eager
2. **Canonical schema contract**: All downstream stages use normalized column names
3. **Observability first-class**: Every stage wrapped in ProcessingTimer
4. **Graceful degradation**: Missing layouts, undetectable types handled with user-facing errors

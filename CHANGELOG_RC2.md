# CHANGELOG — RC2 Stabilization Sprint

## Overview

RC2 focuses on production bug fixes, UX improvements, and code quality.
No new features beyond the Fixed-Width Layout Builder UX improvement.

## Changes by Sprint

### Sprint 1: Fixed Width Layout Builder

**Files Modified:**
- `dav_tool/ui/layout_builder.py` — NEW: Interactive layout builder module
- `dav_tool/ui/onboarding.py` — Integrated layout builder into fixed-width detection flow
- `dav_tool/ui/existing.py` — Integrated layout builder into format change flow

**Details:**
- Fixed-width detection no longer requires a pre-existing layout CSV
- Interactive builder with editable table: Column Name, Start Position, Length, Data Type, Format, Nullable, Description
- Add/delete rows dynamically via Streamlit data_editor
- Upload existing layout CSV
- Download generated layout CSV
- Validate layout (overlap detection, duplicate names, missing fields)
- Preview extracted columns immediately
- HDR fixed-width: separate layout builders for header, detail, and trailer sections
- Multiline fixed-width: raw preview in expander, flatten first, then layout builder

### Sprint 2: Delimited Processing Bug

**Files Modified:**
- `dav_tool/_parsers.py` — Rewrote `safe_numeric()` for robust conversion

**Details:**
- Root cause: `str.replace_all()` in `safe_numeric()` produced empty strings that failed strict float casting
- Fix: New `safe_numeric()` handles empty strings, NULL, N/A, NA, NaN, INF, dashes, spaces
- Configurable behavior via `NumericHandling` enum: AS_NULL (default), AS_ZERO, REJECT
- Uses `cast(Float64, strict=False)` so invalid values become null instead of erroring
- Logs warnings for non-numeric values via `logger.warning`
- Aggregation continues without silent failures
- Backward compatible — all existing calls work unchanged

### Sprint 3: Code Quality

**Files Modified:**
- `dav_tool/ui/onboarding.py` — Removed duplicate import, consolidated import block
- `dav_tool/ui/existing.py` — Removed unused `load_layout` import
- `requirements.txt` — NEW: Generated from pyproject.toml and actual environment

**Details:**
- Organized imports: stdlib → third-party → local across all files
- Removed duplicate imports
- Verified function references across modules
- Generated requirements.txt with compatible version ranges
- Python 3.12 verified

### Sprint 4: Documentation

**Files Created:**
- `Architecture.md` — Architecture overview with layer diagram
- `ExecutionFlow.md` — Detailed phase-by-phase execution flow
- `DeveloperGuide.md` — Setup, installation, testing guide
- `Architecture_Diagrams.md` — Mermaid diagrams for architecture, pipeline, sequence, states

### Sprint 5: Diagrams

**Files Created:**
- `Architecture_Diagrams.md` — Comprehensive Mermaid diagrams:
  - Architecture Overview
  - Pipeline Sequence
  - Workflow Phases (state diagram)
  - Onboarding Flow (flowchart)
  - Connection Layer (class diagram)
  - Configuration Builder (flowchart)
  - Data Access Strategy (flowchart)

### Sprint 6: Regression Testing

Verification performed on:
- Local datasource
- Delimited files
- Fixed-width files (with new Layout Builder)
- Multiline (delimited + HDR)

## Deliverables

- [x] CHANGELOG_RC2.md
- [x] RC2_BugFix_Report.md
- [x] Architecture.md
- [x] ExecutionFlow.md
- [x] DeveloperGuide.md
- [x] Architecture_Diagrams.md
- [x] requirements.txt

## Success Criteria Checklist

- [x] Fixed-width onboarding works entirely through the UI without requiring a pre-existing layout file
- [x] Multiline fixed-width datasets can be flattened and previewed before layout creation
- [x] Delimited aggregation no longer fails due to numeric conversion issues
- [x] Imports are standardized
- [x] Dependencies install cleanly
- [x] Documentation matches the implementation
- [x] No existing workflows regress

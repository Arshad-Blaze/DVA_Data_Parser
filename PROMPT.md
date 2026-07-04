# Runtime Stabilization Sprint 1

Read the entire repository before making any modifications.

The architecture is COMPLETE.

Do NOT redesign the application.

Do NOT refactor modules.

Do NOT add new features.

Do NOT optimize code unless it directly fixes a runtime issue.

Your objective is ONLY to restore application stability.

---

## Current Status

The application runs but has runtime regressions.

The same runtime issues occur on:

- Linux Mint
- Windows 11
- 16 GB RAM machine

Therefore this is NOT a hardware or operating system issue.

Treat this as an application runtime debugging task.

---

## Known Runtime Issues

1.

Duplicate Streamlit widget keys.

Example:

StreamlitDuplicateElementKey

key="price_test"

2.

Onboarding sometimes stops after Preview.

The UI never advances.

3.

Heavy parsing appears to happen repeatedly.

4.

Preview appears to regenerate multiple times.

5.

Existing workflow throws errors after column mapping.

6.

Application eventually crashes during execution.

---

# IMPORTANT

Do NOT guess.

Trace the runtime.

Understand why each issue happens before modifying code.

Every fix must be minimal.

Every fix must preserve the existing architecture.

---

# Runtime Stabilization Order

## TASK 1

Duplicate Widget Keys

Review every Streamlit widget.

Check

- radio
- selectbox
- checkbox
- button
- text_input
- text_area
- multiselect
- file_uploader
- number_input

Requirements

Find duplicate keys.

Rename only duplicated keys.

Do not rename unrelated keys.

Run Streamlit.

Verify

No duplicate key errors remain.

STOP.

Wait for my testing.

---

## TASK 2

Detection Execution

Trace

detect_file_type()

Expected

Detection executes exactly ONE time per upload.

If detection executes multiple times

identify

- caller
- reason
- rerun trigger

Fix only the rerun issue.

Run Streamlit.

Verify.

STOP.

Wait for my testing.

---

## TASK 3

Preview Generation

Trace

preview_raw()

Expected

Preview generated exactly ONCE.

Preview cached.

Every rerun must reuse cached preview.

Never reread the uploaded file.

Never regenerate preview unless user uploads another file.

Run Streamlit.

Verify.

STOP.

Wait for my testing.

---

## TASK 4

Parser Execution

Parser must execute exactly once.

Current flow should be

Upload

↓

Detection

↓

Schema

↓

Parse

↓

Canonical Data

↓

Aggregation

↓

Validation

Parser must never rerun during Streamlit reruns.

Verify.

STOP.

Wait for testing.

---

## TASK 5

Onboarding State Machine

Review every onboarding phase.

Expected

Upload

↓

Detection

↓

Preview

↓

Column Mapping

↓

Processing

↓

Aggregation

↓

Validation

↓

Results

Find where state progression stops.

Fix only that transition.

Run Streamlit.

Verify.

STOP.

---

## TASK 6

Existing Workflow

Verify

Production

↓

Test

↓

Detection

↓

Preview

↓

Column Mapping

↓

Processing

↓

Validation

↓

Results

No validation should start before processing completes.

No stale mappings.

No duplicate widgets.

Run Streamlit.

Verify.

STOP.

---

## TASK 7

Memory Review

Do NOT optimize.

Only inspect.

Identify whether

ProcessingContext

session_state

or any cache

stores

- raw DataFrames
- preview DataFrames
- duplicated DataFrames

If yes

report

- object
- estimated size
- reason

Do NOT change it yet.

Wait for approval.

---

## Runtime Instrumentation

Temporarily print

Current Phase

Current Function

Elapsed Time

Memory Usage

Current Session State Keys

Current ProcessingContext Phase

Expected Output

------------------------------------------------

Upload Started

------------------------------------------------

Detection Started

Detection Finished

------------------------------------------------

Preview Started

Preview Finished

------------------------------------------------

Parser Started

Parser Finished

------------------------------------------------

Aggregation Started

Aggregation Finished

------------------------------------------------

Validation Started

Validation Finished

------------------------------------------------

Workflow Completed

------------------------------------------------

---

## Rules

Never modify more than ONE runtime issue at a time.

After every fix

Run tests.

Launch Streamlit.

Verify functionality.

Then STOP.

Wait for my confirmation before proceeding.

---

## Deliverables after each task

Provide

1. Root Cause

2. Files Modified

3. Functions Modified

4. Why the issue occurred

5. Why the fix is correct

6. Tests executed

7. Remaining runtime issues

Then STOP.

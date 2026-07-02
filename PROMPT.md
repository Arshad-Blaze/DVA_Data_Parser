# Regression Investigation Sprint

STOP ALL FEATURE DEVELOPMENT.

Do NOT implement new features.

Do NOT optimize performance.

Do NOT refactor architecture.

Do NOT clean up code.

The objective is ONLY to restore the application to a fully working state.

The recent architecture changes (Canonical Data Layer, ProcessingContext, Reports, Observability, etc.) are complete.

However, the application workflow has regressed.

==========================================================
MISSION
==========================================================

Investigate every regression introduced after the architecture refactoring.

Think like a senior debugging engineer.

Do NOT assume.

Trace the actual execution.

Only after identifying the root cause should code be modified.

==========================================================
KNOWN ISSUES
==========================================================

Issue 1

The UI is significantly slower than before.

Symptoms

- Slow page transitions.
- Streamlit reruns frequently.
- Long waits between phases.

Investigate

- unnecessary reruns
- unnecessary dataframe copies
- repeated aggregation
- repeated parsing
- ProcessingContext recreation
- excessive session_state updates
- excessive logging
- expensive UI rendering

==========================================================

Issue 2

ONBOARDING FLOW

Expected

Upload

↓

Detection

↓

Preview

↓

Column Mapping

↓

Save Mapping

↓

Process Files

↓

Aggregation

↓

Validation Selection

↓

Validation Results

Actual

Upload

↓

Detection

↓

Preview

↓

Workflow stops.

No next phase appears.

Investigate

- ProcessingContext lifecycle
- current processing phase
- session_state values
- button callbacks
- Streamlit reruns
- hidden exceptions
- UI conditional rendering

Questions

Where exactly does execution stop?

Which condition prevents the next screen?

Which state variable is incorrect?

Which architectural change introduced the problem?

==========================================================

Issue 3

EXISTING FLOW

Expected

Upload Production

↓

Upload Test

↓

Detection

↓

Preview

↓

Column Mapping

↓

Save Mapping

↓

Process Files

↓

Validation Selection

↓

Validation Results

Actual

Immediately after column mapping

↓

An error appears.

Even after correctly mapping every required column

↓

The error remains.

Investigate

- validation trigger timing
- ProcessingContext state
- canonical data availability
- aggregation cache
- session_state
- validation prerequisites

Questions

Why does validation execute before processing?

Why does the error persist?

Is validation using stale state?

Is ProcessingContext being recreated?

==========================================================

PROCESSING CONTEXT REVIEW

==========================================================

Trace the entire lifecycle.

Application Start

↓

Detection

↓

Preview

↓

Mapping

↓

Processing

↓

Aggregation

↓

Validation

↓

Reports

For every phase report

Current ProcessingContext fields

Current session_state keys

Current UI components

Current rerun

Current callbacks

Current buttons

Identify

missing values

incorrect values

unexpected resets

==========================================================

SESSION STATE REVIEW

==========================================================

Audit ALL Streamlit session_state variables.

Identify

unused variables

duplicated state

state overwritten

state cleared unexpectedly

variables recreated every rerun

variables with inconsistent naming

Recommend cleanup.

==========================================================

PERFORMANCE REVIEW

==========================================================

Profile

Detection

Preview

Column Mapping

Processing

Aggregation

Validation

Reports

For every stage report

Execution Time

Memory Usage

Number of reruns

DataFrame copies

LazyFrame collections

Repeated processing

Repeated rendering

==========================================================

DEBUG LOGGING

==========================================================

Temporarily add detailed debug logging.

Log

Application Started

Session Created

Session Restored

Detection Started

Detection Completed

Preview Generated

Mapping Saved

ProcessingContext Updated

Aggregation Started

Aggregation Finished

Validation Started

Validation Finished

Reports Generated

Every Streamlit rerun

Every button click

Every ProcessingContext update

Every session_state update

Every exception

These logs are temporary.

They should help locate the regression.

==========================================================

IMPLEMENTATION STRATEGY

==========================================================

FIRST

Investigate.

SECOND

Explain the root cause.

THIRD

List affected files.

FOURTH

Describe the smallest possible fix.

FIFTH

Wait for confirmation.

Do NOT immediately modify code.

==========================================================

WHEN IMPLEMENTING

==========================================================

Once root causes are confirmed

Fix ONLY the regression.

Do NOT redesign architecture.

Do NOT refactor unrelated code.

Do NOT introduce new abstractions.

Do NOT optimize anything unrelated.

Keep the fixes as small as possible.

==========================================================

AFTER FIXING

==========================================================

Run

- all unit tests
- integration tests
- onboarding workflow
- existing workflow

Verify

✓ Detection works

✓ Preview works

✓ Column Mapping works

✓ Process Files works

✓ Aggregation works

✓ Validation works

✓ Reports work

✓ Metrics work

✓ Observability works

Verify that both Onboarding and Existing complete end-to-end without manual intervention.

==========================================================

FINAL REPORT

==========================================================

Provide

1. Root cause for every issue.

2. Files modified.

3. Why the regression occurred.

4. Why the fix works.

5. Remaining risks.

6. Recommended follow-up improvements (if any).

Only after all regressions are resolved should we continue feature development.

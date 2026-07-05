# Runtime Stabilization Sprint

Read and understand the entire repository before making any modifications.

The parser architecture, canonical data layer, validation engine, aggregation layer and reporting flow are COMPLETE.

Do NOT redesign the architecture.

Do NOT refactor modules unless absolutely necessary.

Do NOT optimize code that is already working.

This sprint is ONLY for runtime stabilization, UX improvements and regression elimination.

All Playwright tests must continue to pass after every change.

------------------------------------------------------------

## Current Status

The application is functionally complete.

Playwright E2E framework is integrated.

Regression suite is available.

Architecture review is complete.

The objective is to eliminate runtime issues before implementing multiline record support.

------------------------------------------------------------

## General Rules

1.

Do NOT introduce architectural changes.

2.

Do NOT rewrite parser logic.

3.

Do NOT change validation calculations.

4.

Do NOT change report generation.

5.

Do NOT change canonical DataFrame structure.

6.

Fix only confirmed runtime issues.

7.

Every change must preserve existing functionality.

8.

After every fix

Run

pytest

Playwright

Verify no regression

Stop

------------------------------------------------------------

# TASK 1

Smart Column Auto Mapping

Current issue

Every mapping dropdown defaults to the first column.

Users can accidentally map

Store -> Store

Units -> Store

Price -> Store

etc.

causing DuplicateError.

Implement intelligent default mapping.

Match columns using

case-insensitive

substring matching

synonyms where applicable

Examples

Store

Store Number

Store_ID

STORE

↓

Store

UPC

UPC_CODE

Item UPC

↓

UPC

Description

Item Description

DESC

↓

Description

Units

Qty

Quantity

↓

Units

Price

Total Price

Sales

Amount

↓

Price

If no confident match exists

leave the dropdown unselected.

------------------------------------------------------------

# TASK 2

Column Mapping Validation

Before allowing

Confirm Mapping

validate

Required fields selected

No duplicate column selection

All required mappings exist

If validation fails

show friendly Streamlit error.

Never expose Polars exceptions.

Disable Confirm Mapping until validation succeeds.

------------------------------------------------------------

# TASK 3

Friendly Runtime Errors

Replace technical exceptions with user friendly messages.

Examples

Missing Store List

Duplicate Mapping

Missing Required Column

Aggregation Failure

Invalid Layout

Invalid Delimiter

Missing Header

Unknown File Type

Unexpected Parsing Failure

Every error should explain

What happened

Why

How to fix it

------------------------------------------------------------

# TASK 4

Processing Feedback

Every long running phase must display progress.

Detection

Preview

Parsing

Canonical Conversion

Aggregation

Validation

Report Generation

Use

st.spinner()

or

st.status()

or

st.progress()

Display current phase.

Example

Reading File...

Parsing Records...

Generating Canonical Dataset...

Aggregating Store Data...

Running Validation...

Generating Reports...

Completed

------------------------------------------------------------

# TASK 5

Execution Timing

Capture timings for

Detection

Preview

Column Mapping Load

Parsing

Canonical Conversion

Aggregation

Validation

Reports

Display timings

inside a collapsed

Processing Metrics

expander.

Do not clutter the main UI.

------------------------------------------------------------

# TASK 6

Runtime Diagnostics

Create expandable sections

Detection Details

Parser Details

Schema Details

Validation Details

Processing Metrics

Runtime Logs

Default

Collapsed

Only populate expensive diagnostics when the user expands them.

Do not render unnecessary large tables automatically.

------------------------------------------------------------

# TASK 7

Workflow State Review

Review both

Onboarding

Existing

Verify

Every phase transition

Every session_state variable

ProcessingContext

Navigation

Reset

History

No stale state

No duplicated state

No unnecessary reruns.

------------------------------------------------------------

# TASK 8

Performance Review

Review

Detection

Preview

Column Mapping

Processing

Validation

Find

Repeated parsing

Repeated preview generation

Repeated aggregation

Repeated detection

Repeated folder scanning

Repeated file reading

If repeated work exists

remove it

without changing architecture.

------------------------------------------------------------

# TASK 9

Playwright Expansion

Extend Playwright suite.

Verify

Detection

Preview

Column Mapping

Validation

Reports

Timing metrics

Friendly errors

Processing spinner

Column auto mapping

Regression cases

Capture screenshots after every phase.

Generate HTML report.

------------------------------------------------------------

# TASK 10

Final Engineering Review

Produce

Engineering Review.md

Include

Architecture score

Maintainability

Performance

Memory usage

UI responsiveness

Parser quality

Validation quality

Test coverage

Technical debt

Immediate improvements

Future roadmap

Multiline readiness

------------------------------------------------------------

# Deliverables

Updated application

Passing pytest suite

Passing Playwright suite

Runtime issues resolved

Engineering review

Updated HTML report

Regression report

Execution summary

------------------------------------------------------------

# DO NOT

Do not redesign architecture.

Do not implement multiline yet.

Do not refactor parser.

Do not change validation calculations.

Do not optimize unrelated code.

Do not introduce breaking changes.

------------------------------------------------------------

# Success Criteria

The application should feel production-ready.

Users should be able to complete both Onboarding and Existing workflows without crashes, confusion or unnecessary waiting.

Only after this sprint is complete should multiline record handling begin.

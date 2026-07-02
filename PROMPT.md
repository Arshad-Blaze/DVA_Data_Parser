Release Engineering Sprint

The core architecture is now complete.

Completed

✓ Detection Layer

✓ Parsing Layer

✓ Canonical Data Layer

✓ ProcessingContext

✓ Aggregation Layer

✓ Validation Layer

✓ Reports Layer

✓ Observability Layer

✓ Benchmark Suite

✓ Configuration Layer

✓ Regression Tests

The objective is now to stabilize the application and prepare it for production use as an internal desktop application.

==========================================================
GENERAL RULES
==========================================================

You are acting as the lead software engineer.

Do not redesign the architecture.

Do not introduce new frameworks.

Do not rewrite working code.

Do not remove features.

Make only targeted improvements.

Every change must preserve existing behaviour.

Run all tests after every change.

Update technical documentation whenever necessary.

==========================================================
TASK 1
Fix Known Bugs
==========================================================

Review the engineering report.

Fix every confirmed bug.

Current known items include

- Unit Price bug in normalize_store_chunk()

- Any confirmed regression discovered during benchmarks

Do not introduce behavioural changes.

Explain the root cause before implementing.

==========================================================
TASK 2
Code Cleanup
==========================================================

Remove

- dead code

- unused imports

- obsolete helper functions

- abandoned dataclasses

- duplicate code

Only remove code that is confirmed unused.

==========================================================
TASK 3
Refactor Large Modules
==========================================================

Review

ui/existing.py

ui/onboarding.py

Split overly large functions into smaller helpers.

Keep behaviour identical.

Do not move business logic into UI.

==========================================================
TASK 4
Execution Summary
==========================================================

After processing completes,

display an Execution Summary inside Streamlit.

Include

Files Processed

Rows Processed

Unique Stores

Unique UPCs

Parse Time

Aggregation Time

Validation Time

Report Time

Total Execution Time

Peak Memory

Peak CPU

Warnings

Errors

==========================================================
TASK 5
Developer Diagnostics
==========================================================

Create a Developer Mode.

When enabled

show

Current Phase

Current File

Current Chunk

Parser Type

Detected Layout

Canonical Schema

ProcessingContext

Current Memory

Peak Memory

Current CPU

Aggregations

Validation Status

When disabled

hide all diagnostics.

==========================================================
TASK 6
Terminal Execution Log
==========================================================

The terminal used to launch Streamlit should display live execution progress.

Log

Application Started

Session Started

Folder Selected

Files Found

Detection Started

Detection Completed

Schema Generated

Column Mapping Saved

Processing File X of N

Current Chunk

Rows Parsed

Rows Aggregated

Validation Started

Validation Completed

Reports Generated

Execution Summary

Display

Current Time

Current Phase

Elapsed Time

Rows Processed

Current Memory

Peak Memory

CPU Usage

Warnings

Errors

Keep logs readable.

Avoid excessive verbosity.

==========================================================
TASK 7
Processing History
==========================================================

Maintain a Processing History.

Store the last 10 executions.

Each execution should include

Timestamp

Files Processed

Rows Processed

Execution Time

Peak Memory

Peak CPU

Warnings

Errors

Allow viewing history from the UI.

==========================================================
TASK 8
Large Dataset Validation
==========================================================

Benchmark using progressively larger datasets.

Measure

100 MB

500 MB

1 GB

5 GB

Folders containing many files

Record

Parse Time

Aggregation Time

Validation Time

Report Time

Rows Per Second

Peak Memory

Peak CPU

Document the results.

==========================================================
TASK 9
Final Code Review
==========================================================

Review the entire repository.

Identify

Critical

High

Medium

Low

issues.

For each issue provide

- File
- Description
- Risk
- Suggested Fix

Only implement Critical and High issues.

Leave Medium and Low as recommendations.

==========================================================
TASK 10
Release Candidate Review
==========================================================

When all work is complete,

produce a Release Candidate report.

Include

Architecture Summary

Performance Summary

Benchmark Results

Memory Behaviour

Test Results

Remaining Technical Debt

Known Limitations

Future Improvements

Overall Quality Score

Production Readiness Score

Recommendation

Ready for Internal Release

or

Requires Further Work

==========================================================
WORKFLOW
==========================================================

For every task

1. Review the current implementation.

2. Explain the implementation plan.

3. Implement.

4. Run tests.

5. Run benchmarks where applicable.

6. Update documentation.

7. Summarize changes.

8. Wait before moving to the next task.

Never perform multiple tasks simultaneously.

Keep every commit focused and reversible.

PROJECT ROADMAP

The core architecture of this project is now complete.

Completed

✓ Detection Layer

✓ Canonical Data Layer

✓ ProcessingContext

✓ Single Normalization Layer

✓ Aggregation Cache

✓ Validation consumes canonical data

✓ All tests passing

The objective now is to make the application production-quality while preserving the architecture.

==========================================================

GENERAL RULES

==========================================================

You are now acting as the lead software engineer for this project.

Before every sprint

1. Review current implementation.

2. Explain current architecture.

3. Identify affected modules.

4. Explain implementation strategy.

5. Estimate risks.

6. Wait for approval if assumptions are required.

Never

- rewrite working code

- change architecture unnecessarily

- introduce unnecessary dependencies

- change UI behaviour unless required

- remove existing functionality

Always

- preserve backward compatibility

- make small incremental changes

- run all tests

- update documentation

- update architecture documentation if required

==========================================================

SPRINT 4

REPORTS LAYER

==========================================================

Goal

Create a dedicated Reports layer.

Move all report-generation responsibilities from Aggregator into Reports.

Requirements

- No behaviour changes

- Same API

- Same outputs

- All tests pass

==========================================================

SPRINT 5

PERFORMANCE OPTIMIZATION

==========================================================

Review

_merge_accumulate()

Chunk merging

DataFrame concatenation

Lazy execution

Streaming

Memory allocations

Optimize only after benchmarking.

Avoid premature optimization.

==========================================================

SPRINT 6

BENCHMARK SUITE

==========================================================

Create benchmark utilities.

Benchmark

100 MB

500 MB

1 GB

5 GB

Folder Processing

Measure

Parse Time

Aggregation Time

Validation Time

Report Time

Peak Memory

Peak CPU

Rows Per Second

Generate benchmark reports.

==========================================================

SPRINT 7

OBSERVABILITY LAYER

==========================================================

Create a centralized observability framework.

This sprint includes

Logging

Metrics

Progress Reporting

Performance Timing

Memory Tracking

CPU Tracking

Warnings

Errors

All processing stages should automatically report their execution.

Create

ProcessingMetrics

Fields

files_processed

rows_processed

stores_processed

upcs_processed

chunks_processed

parse_time

aggregation_time

validation_time

report_time

total_execution_time

peak_memory

current_memory

peak_cpu

current_cpu

warnings

errors

files_failed

rows_failed

Expose ProcessingMetrics through ProcessingContext.

==========================================================

COMMAND PROMPT OUTPUT

==========================================================

While Streamlit is running,

the terminal from which Streamlit was launched should continuously display progress.

Examples

Application Started

Session Started

Folder Selected

Files Discovered

Detection Started

Detection Completed

Schema Generated

Column Mapping Saved

Processing File 1 of N

Rows Parsed

Rows Aggregated

Validation Started

Validation Completed

Reports Generated

Execution Summary

The command prompt should act as a live execution log.

It should clearly show

Current Phase

Current File

Current Chunk

Rows Processed

Elapsed Time

Current Memory

Peak Memory

CPU Usage

Warnings

Errors

Completed Tasks

Avoid excessive spam.

Use structured logging.

==========================================================

STREAMLIT UI

==========================================================

Keep Streamlit responsive.

Continue showing

Progress Bars

Status Text

Current File

Completion Percentage

Execution Summary

The terminal logging should complement the UI,

not replace it.

==========================================================

SPRINT 8

CONFIGURATION MANAGEMENT

==========================================================

Centralize configuration.

Review

Chunk Size

Encoding

Memory Limits

Logging Level

Benchmark Settings

Validation Thresholds

Parser Defaults

Avoid hardcoded values.

==========================================================

SPRINT 9

REGRESSION TESTING

==========================================================

Expand testing.

Include

Large Files

Large Folders

Corrupt Files

Invalid Layouts

Mixed Encodings

Duplicate Stores

Duplicate UPCs

Empty Files

Empty Folders

Memory Regression

ProcessingContext

Canonical Layer

Reports

Observability

Benchmark Utilities

==========================================================

SPRINT 10

FINAL ENGINEERING REVIEW

==========================================================

Perform a complete engineering review.

Evaluate

Architecture

Performance

Scalability

Maintainability

Memory

Code Quality

Observability

Testing

Documentation

Technical Debt

Provide

Overall Score

Production Readiness Score

Strengths

Weaknesses

Future Roadmap

Do not implement anything.

Only produce the final review.

==========================================================

WORKFLOW

For every sprint

Review

↓

Explain

↓

Implement

↓

Run Tests

↓

Benchmark (if applicable)

↓

Update Documentation

↓

Summarize

↓

Recommend Next Sprint

Only work on one sprint at a time.

Do not automatically continue to the next sprint without confirmation.

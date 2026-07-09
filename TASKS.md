# DVA Evolution Sprint

Read the entire repository before making any modifications.

The current application is considered Version 1.0 and is functionally complete.

Current components are stable:

✓ Parser
✓ Canonical Data Layer
✓ Validation Engine
✓ Aggregation Engine
✓ Reports
✓ Runtime Stabilization
✓ Playwright
✓ Regression Tests

The objective of this sprint is divided into TWO STAGES.

Stage 1 MUST be completed before Stage 2 begins.

Do not work on Stage 2 until Stage 1 has been verified.

===========================================================
STAGE 1
MEMORY PROFILING AND OPTIMIZATION
===========================================================

Problem

Current observation on Windows 11

16 GB RAM

BAU File ≈ 120 MB

TEST File ≈ 120 MB

During Column Mapping

Python consumes approximately

7.5 GB RAM

Overall system reaches

93–98% memory usage.

Processing then consumes approximately

4 GB RAM.

This is unacceptable.

-----------------------------------------------------------

Objective

Identify the ROOT CAUSE.

Do NOT guess.

Measure first.

-----------------------------------------------------------

Investigate

1.

Every DataFrame created.

2.

Every Polars LazyFrame.

3.

Every DataFrame stored inside

session_state

ProcessingContext

cache

temporary variables

4.

Repeated parsing.

5.

Repeated preview generation.

6.

Repeated folder scanning.

7.

Repeated file reading.

8.

Repeated aggregation.

9.

Repeated canonical generation.

10.

Repeated dataframe cloning.

-----------------------------------------------------------

For every DataFrame report

Variable Name

Rows

Columns

Estimated Memory

Current Lifetime

Owner

Duplicate Exists

Can be released?

-----------------------------------------------------------

Optimise

Remove duplicate DataFrames.

Release temporary DataFrames immediately.

Store metadata instead of large DataFrames where possible.

Preview should only keep

N sample rows.

Never keep entire dataset for preview.

Reuse schema.

Reuse metadata.

Never parse the same dataset twice.

Read full dataset only when required.

-----------------------------------------------------------

Instrumentation

Print

Current Phase

Current RAM

Peak RAM

DataFrames Alive

Largest DataFrame

Memory Released

Display

Terminal

Processing Metrics Expander

-----------------------------------------------------------

Success Criteria

Peak RAM during Column Mapping should reduce significantly.

Application behaviour must remain unchanged.

Playwright must continue to pass.

===========================================================
STAGE 2
CONFIGURATION BUILDER
===========================================================

Objective

Separate

Configuration Discovery

from

Data Processing.

The parser should no longer infer everything during processing.

Instead

processing should execute using a generated configuration.

-----------------------------------------------------------

New Workflow

User selects

File

or

Folder

↓

If Fixed Width

Ask for Layout

↓

Read only a SAMPLE

Never process the full dataset.

↓

Generate Configuration

↓

Display Configuration

↓

User Reviews

↓

User Accepts

↓

Configuration Locked

↓

Process Full Dataset ONCE

↓

Validation

↓

Reports

-----------------------------------------------------------

Configuration Builder

Generate

File Information

Encoding

Delimiter

Header

Record Type

Multiline

Fixed Width

Layout

Schema

Detected Columns

Detected Data Types

Suggested Mapping

Business Rules

Validation Configuration

Output Configuration

-----------------------------------------------------------

Validation Configuration

Allow each validation to define

Enabled

Required Columns

Aggregation Columns

If aggregation columns are omitted

use current default implementation.

Configuration overrides defaults.

Never replace them.

-----------------------------------------------------------

Configuration Review

User must be able to

Review

Edit

Accept

Download

Configuration.

Do NOT force download/upload.

Configuration should be editable directly inside the application.

-----------------------------------------------------------

Processing

After user accepts configuration

Lock configuration.

Stop all automatic inference.

Read complete dataset exactly once.

Use only the accepted configuration.

Validation and aggregation must rely entirely on configuration.

-----------------------------------------------------------

Memory Requirements

Configuration Builder should only inspect

sample records.

Never load the complete dataset.

Configuration generation must remain lightweight.

-----------------------------------------------------------

Playwright

Extend tests for

Configuration Generation

Configuration Review

Configuration Acceptance

Configuration Driven Processing

Configuration Driven Validation

Regression tests must continue to pass.

===========================================================
FUTURE (DO NOT IMPLEMENT)

Design the configuration model so future versions can support

Data Source Profiles

Profile Repository

Profile Versioning

Profile Import/Export

Automatic Profile Detection

These are future enhancements only.

Do NOT implement them now.

===========================================================
DELIVERABLES

Stage 1

Memory Profile Report

Root Cause Analysis

Memory Before

Memory After

Optimization Summary

Stage 2

Configuration Builder

Configuration Review UI

Configuration Driven Processing

Configuration Driven Validation

Updated Playwright Tests

Updated Documentation

Migration Notes

===========================================================
IMPORTANT

Do NOT redesign the architecture.

Do NOT rewrite the parser.

Do NOT change canonical data structures.

Do NOT change validation calculations.

Do NOT change report generation.

Extend the current architecture.

Maintain backward compatibility.

Complete Stage 1 first.

Proceed to Stage 2 only after memory optimization is verified.

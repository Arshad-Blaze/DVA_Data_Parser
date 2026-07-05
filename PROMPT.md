# DVA Parser Roadmap - Phase 2 Onwards

Read and understand the current repository before making any modifications.

The current application is considered Version 1.0.

Current state:

- Parser architecture complete
- Canonical Data Layer complete
- Validation Engine complete
- Aggregation Engine complete
- Runtime Stabilization complete
- Playwright Regression Suite complete
- Engineering Review complete

The objective from this point forward is to EXTEND parser capability without changing the existing architecture.

------------------------------------------------------------

# IMPORTANT RULES

Do NOT redesign the architecture.

Do NOT rewrite the parser.

Do NOT modify validation logic.

Do NOT modify aggregation logic.

Do NOT modify reporting.

Do NOT modify canonical dataframe structure.

Do NOT refactor unrelated modules.

Every feature must integrate into the existing pipeline.

All Playwright tests must continue to pass.

Every feature must preserve backward compatibility.

------------------------------------------------------------

# Development Strategy

Every new feature must be developed in isolation.

Treat the existing implementation as the production baseline.

Every implementation must:

Review

↓

Implement

↓

Unit Test

↓

Playwright Test

↓

Regression Test

↓

Manual Verification

↓

Commit

------------------------------------------------------------

# Phase 2

Multiline Record Support

This is the highest priority feature.

Objective

Support files where a logical record spans multiple physical lines.

Current parser

Physical Line

↓

Canonical Row

New parser

Multiple Physical Lines

↓

Logical Record

↓

Canonical Row

Requirements

1.

Detect multiline record format.

2.

Group physical lines into logical records.

3.

Flatten logical records.

4.

Generate exactly the same canonical dataframe as single-line parsing.

5.

Do NOT change downstream processing.

Validation

Aggregation

Reports

must remain unchanged.

The multiline parser must simply produce canonical rows.

------------------------------------------------------------

# Phase 3

Header Based Record Support

Support files such as

HDR

DTL

DTL

DTL

TRL

Convert them into one logical transaction.

Reuse the canonical data pipeline.

Do not duplicate parsing logic.

------------------------------------------------------------

# Phase 4

Configuration Driven Parsing

The parser must become configuration driven.

Instead of retailer specific logic,

load parsing behavior from configuration.

Example

record_type

delimiter

header

continuation_record

layout_file

record_start

record_end

field_mapping

This should allow new retailers to be onboarded without changing code.

------------------------------------------------------------

# Phase 5

Golden Dataset Framework

Create a regression dataset.

Structure

tests/

golden/

expected/

For every supported format

store

Input File

Expected Canonical Output

Every parser change must compare

Generated Canonical Output

against

Expected Canonical Output

No parser regression should be allowed.

------------------------------------------------------------

# Phase 6

Performance Improvements

Only after parser functionality is complete.

Review

Memory

CPU

Repeated Parsing

Repeated Preview

Repeated Aggregation

Large File Processing

Folder Processing

Batch Size

Parallel Processing

Polars Optimisation

No premature optimisation before parser completion.

------------------------------------------------------------

# Phase 7

Enterprise Readiness

Improve

Installer

Logging

Configuration Repository

Application Versioning

Error Reporting

Documentation

Packaging

Deployment

------------------------------------------------------------

# Testing Requirements

Every phase must include

Unit Tests

Playwright Tests

Regression Tests

Golden Dataset Validation

Performance Metrics

Screenshots

HTML Report

No feature is complete until all tests pass.

------------------------------------------------------------

# Development Rules

Never implement multiple parser features together.

Complete one feature.

Test completely.

Merge.

Then start the next feature.

------------------------------------------------------------

# Expected Workflow

Review

↓

Design

↓

Implement

↓

Unit Test

↓

Playwright

↓

Regression

↓

Golden Dataset Validation

↓

Manual Test

↓

Performance Review

↓

Commit

------------------------------------------------------------

# Deliverables for Every Feature

Architecture Impact

Files Modified

Functions Modified

Unit Tests

Playwright Tests

Regression Tests

Golden Dataset Results

Performance Results

Known Limitations

Future Improvements

------------------------------------------------------------

# DO NOT

Do not redesign the application.

Do not modify working modules.

Do not introduce breaking changes.

Do not bypass Playwright.

Do not bypass regression tests.

Do not skip manual verification.

------------------------------------------------------------

# Success Criteria

The application must evolve by extending parser capability while preserving the stability of Version 1.0.

Every new parser feature should seamlessly integrate into the existing canonical pipeline without affecting validation, aggregation, reporting, or existing user workflows.

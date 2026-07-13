# DVA Platform 1.0 RC1
# Sprint A - RC1 Integration

Read BOTH branches completely.

Branch A
Phase 4 - Stable Streaming Workflow

Branch B
Phase 5 - Data Operations

DO NOT begin coding immediately.

First compare both branches and generate an internal implementation matrix.

============================================================

MISSION

DVA is a Retail Data Integration & Certification Platform.

It supports

1. New Retailer Integration

2. Existing Retailer Format Certification

The architecture is frozen.

Do NOT redesign the architecture.

Do NOT add experimental features.

Merge the best implementation from both branches.

============================================================

KEEP FROM PHASE 4

✓ Connection Manager inside collapsible Expander

✓ Single Page Configuration

✓ Streaming workflow improvements

✓ UX improvements discovered through real user testing

============================================================

KEEP FROM PHASE 5

✓ Data Operations Framework

✓ Operation Registry

✓ Aggregate Operation

✓ Statistics

✓ Export

✓ Preview

✓ Operation Architecture

============================================================

WORKFLOW

Connection Manager

↓

RAW Preview

↓

Discovery Summary

↓

Single Page Configuration

↓

Configuration Validation

↓

Streaming Processing

↓

Data Operations

↓

Validation (optional)

↓

Reports

============================================================

RAW PREVIEW

Connection Manager must show

RAW FILE CONTENT

Exactly as stored.

No parsing.

No delimiter split.

No flattening.

Structured Preview belongs ONLY after Configuration.

============================================================

DISCOVERY

Discovery happens exactly once.

Connection Manager owns

Connection

Browse

Sample

Discovery

RAW Preview

DiscoveryResult

Discovery page becomes Discovery Summary.

No duplicate detection.

No duplicate preview.

No duplicate flattening.

============================================================

CONNECTION MANAGER UX

Connection Manager automatically collapses after

Connection

Dataset Selection

Discovery

RAW Preview

Collapsed view shows

Connection

Dataset

Encoding

Delimiter

Discovery Status

Expand only on demand.

============================================================

CONFIGURATION

Keep Single Page Configuration.

Do NOT restore wizard.

Organize into sections

General

Structure

Schema

Business Rules

Validation

Review

============================================================

TESTING

Run after every logical merge

Unit Tests

Regression Tests

Playwright

Memory Tests

Streaming Tests

============================================================

OUTPUT

MERGE_REPORT.md

Files merged

Conflicts

Tests

Remaining issues

Architecture preserved

No regressions.

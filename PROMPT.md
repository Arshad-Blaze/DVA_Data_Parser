# DVA Platform v5
# Data Operations Framework Sprint

Read the ENTIRE repository before making ANY modifications.

Read the latest architecture review.

Read CHANGELOG_STABILIZATION.md.

Understand the current architecture completely before coding.

============================================================

OBJECTIVE

The platform is no longer only a validation tool.

It is becoming an Enterprise Data Onboarding Platform.

This sprint introduces a reusable Data Operations Framework.

Validation will become one consumer of this framework instead of owning aggregation logic.

DO NOT redesign the architecture.

DO NOT rewrite existing parser logic.

DO NOT rewrite workflow.

DO NOT duplicate code.

Build on top of the existing platform.

============================================================

CURRENT ARCHITECTURE

Connection Manager

↓

Discovery

↓

Configuration Builder

↓

Configuration Validator

↓

Streaming Processing

↓

Canonical Dataset

↓

Validation

↓

Reports

TARGET ARCHITECTURE

Connection Manager

↓

Discovery

↓

Configuration Builder

↓

Configuration Validator

↓

Streaming Processing

↓

Canonical Dataset

↓

Data Operations Framework

        ├── Aggregate

        ├── Filter

        ├── Sort

        ├── Sample

        ├── Statistics

        ├── Export

        └── Preview

↓

Validation

↓

Reports

Validation must become a client of Data Operations.

============================================================

RULES

Do NOT duplicate aggregation code.

Move reusable logic.

Keep backward compatibility.

Every new operation must work with the Canonical Dataset.

Operations must NOT know retailer-specific columns.

Everything comes from Configuration.

============================================================

PHASE 1

Repository Review

Review

workflow

validation

calculations

reports

processing

canonical layer

configuration

aggregation

Understand every place aggregation currently exists.

Generate an internal dependency map.

============================================================

PHASE 2

Create Data Operations Framework

Create

operations/

or

core/operations/

depending on existing architecture.

Introduce

IDataOperation

AbstractOperation

OperationResult

OperationOptions

OperationRegistry

Do NOT over engineer.

Keep interfaces clean.

============================================================

PHASE 3

Aggregation Operation

Extract aggregation into a reusable service.

Input

Canonical Dataset

Group By Columns

Aggregation Columns

Aggregation Functions

Output

Aggregated Dataset

Support

SUM

COUNT

AVG

MIN

MAX

FIRST

LAST

Support multiple aggregation columns.

Support multiple Group By columns.

NO validation logic here.

============================================================

PHASE 4

Filtering Operation

Support

Equals

Contains

StartsWith

EndsWith

GreaterThan

LessThan

In List

Null

Not Null

Configuration driven.

============================================================

PHASE 5

Sorting Operation

Support

Multiple columns.

Ascending.

Descending.

Stable sorting.

============================================================

PHASE 6

Sampling Operation

Support

First N

Last N

Random

Percentage

Useful for Discovery.

============================================================

PHASE 7

Statistics Operation

Generate

Row Count

Column Count

Null Count

Distinct Count

Min

Max

Mean

Median

Std Dev

Top Values

Memory Usage

Dataset Size

This replaces ad-hoc statistics.

============================================================

PHASE 8

Export Operation

Support exporting any intermediate result.

CSV

Parquet

Excel

Future formats easily extendable.

User should be able to download

Canonical Dataset

Aggregated Dataset

Filtered Dataset

Statistics

Validation Results

============================================================

PHASE 9

Preview Operation

Current Preview

↓

Operation

↓

UI

Preview should become reusable.

Support

Raw Preview

Canonical Preview

Aggregated Preview

Filtered Preview

Statistics Preview

============================================================

PHASE 10

Validation Refactoring

Validation must consume

Aggregate Operation

instead of implementing aggregation itself.

Validation should only perform

Comparison

Difference

Difference %

Tolerance

Ranking

Sorting

Everything else belongs to Operations.

============================================================

PHASE 11

Configuration Integration

Configuration should define

Operations

Group By

Aggregation

Filters

Sorting

Sampling

Validation Rules

Output

If user chooses Aggregate Only

Validation is skipped.

Reports are skipped.

Export becomes available.

============================================================

PHASE 12

UI

Add

Data Operations

section.

Operations available

Aggregate Only

Aggregate + Export

Statistics

Preview

Validation

Keep UI simple.

Do NOT overwhelm user.

============================================================

PHASE 13

Memory

Operations must stream wherever possible.

Avoid DataFrame duplication.

Release temporary objects.

Reuse canonical dataset.

Support future large datasets.

============================================================

PHASE 14

Testing

Every operation

Unit Tests.

Regression Tests.

Playwright.

Large Dataset Tests.

Memory Tests.

Verify operations independently.

============================================================

PHASE 15

Documentation

Update

Architecture

User Guide

Engineering Docs

Workflow

Explain

Operations Framework

Configuration

Aggregate Only

Validation Flow

============================================================

DELIVERABLES

Reusable Data Operations Framework.

Aggregate Operation.

Filter Operation.

Sort Operation.

Sample Operation.

Statistics Operation.

Export Operation.

Preview Operation.

Validation consuming Operations.

Aggregate Only workflow.

Documentation.

Regression Tests.

Playwright.

============================================================

SUCCESS CRITERIA

The platform should now support

Connect

↓

Discover

↓

Configure

↓

Process

↓

Choose Operation

↓

Aggregate

OR

Statistics

OR

Export

OR

Validation

OR

Reports

Validation becomes only one possible operation.

Every operation is reusable.

Every operation is configuration driven.

Every operation works on Canonical Data.

No retailer-specific logic exists inside Data Operations.

============================================================

MANDATORY QUALITY GATES

Before modifying any module

perform impact analysis.

For every file modified

identify

Imports

Dependencies

Affected tests

Affected workflows

Potential regressions

Run

Unit Tests

Regression Tests

Playwright

Memory Benchmarks

Performance Benchmarks

No regression is acceptable.

============================================================

COMMIT STRATEGY

Never implement everything in one commit.

Commit 1

Core Operations Framework

Commit 2

Aggregation Operation

Commit 3

Filter + Sort

Commit 4

Statistics + Export

Commit 5

Validation Integration

Commit 6

UI

Commit 7

Testing

Commit 8

Documentation

Each commit must pass all tests before continuing.

Generate CHANGELOG_DATA_OPERATIONS.md documenting

Problem

Root Cause

Implementation

Files Modified

Impact Analysis

Tests Executed

Performance Comparison

Regression Status

Final Verification

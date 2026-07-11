# DVA Platform v3 - Workflow Refactoring Sprint

Read the ENTIRE repository before modifying any code.

Read all architecture review documents generated during the audit.

Do NOT ignore the existing implementation.

This is NOT a rewrite.

This is an evolution of the current architecture.

The parser, aggregation engine, validation engine and reporting engine are considered stable and must be reused.

============================================================

OBJECTIVE

Transform the current parser-driven application into a workflow-driven platform.

The workflow should orchestrate every component.

The parser should become one service inside the workflow.

============================================================

CORE PRINCIPLES

1.

Do NOT rewrite working code.

2.

Reuse existing modules whenever possible.

3.

Reduce coupling.

4.

Reduce memory usage.

5.

Move business logic out of UI.

6.

Configuration should drive processing.

7.

Connection Manager becomes the primary entry point.

8.

Support streaming-first architecture.

============================================================

CURRENT PROBLEMS TO ADDRESS

Based on the architecture review:

• UI contains business logic.

• onboarding.py and existing.py have become orchestration layers mixed with rendering.

• Parameter explosion exists throughout aggregation.

• ValidationConfig is only partially driving processing.

• Large DataFrames remain alive too long.

• Configuration is not yet the single source of truth.

• Workflow still revolves around parser instead of configuration.

Do NOT attempt to solve everything at once.

============================================================

GOAL OF THIS SPRINT

The purpose of this sprint is NOT feature development.

The purpose is architectural stabilization.

============================================================

STEP 1

Review Current Workflow

Understand both workflows completely.

Onboarding

Existing

Connection Manager

Configuration Builder

Processing

Validation

Reports

Document how data flows today.

Identify duplicated orchestration.

Do not modify parser logic.

============================================================

STEP 2

Introduce Workflow Layer

Create a dedicated workflow layer.

The workflow layer owns

Connection

↓

Discovery

↓

Configuration

↓

Configuration Validation

↓

Processing

↓

Validation

↓

Reports

UI pages should only render workflow state.

UI must no longer orchestrate processing directly.

============================================================

STEP 3

Separate Business Logic From UI

Move

column normalization

implied decimal logic

mapping validation

configuration transformation

processing preparation

into service modules.

UI should only

display

collect user input

call workflow services

============================================================

STEP 4

Configuration Driven Processing

Configuration becomes the processing contract.

Everything required for processing must exist inside the configuration.

Parser must not infer information again after configuration has been accepted.

If configuration exists

parser trusts it.

============================================================

STEP 5

Processing Context Cleanup

Review ProcessingContext.

Only retain objects required by the current phase.

Release intermediate DataFrames immediately after use.

Store only

Aggregated Results

Validation Results

Execution Metrics

Reports

Never retain unnecessary intermediate objects.

============================================================

STEP 6

Parameter Refactoring

Replace large parameter lists.

Create

ParserOptions

ConnectionOptions

ProcessingOptions

ValidationOptions

AggregationOptions

These objects become immutable.

Aggregation functions should receive option objects rather than 20+ parameters.

============================================================

STEP 7

Validation Refactoring

Separate validation into two engines.

Aggregation Engine

Input

Group By

Aggregation Columns

Output

Aggregated Data

Calculation Engine

Input

Aggregated BAU

Aggregated TEST

Output

Difference

Difference %

Tolerance

Ranking

Sorting

Validation Results

Validation configuration should define

Group By Columns

Aggregation Columns

Enabled

Required Columns

The engine should consume configuration rather than hardcoded logic.

============================================================

STEP 8

Streaming Architecture

The MFT server is the source of truth.

Avoid copying files locally whenever practical.

Use streaming readers.

Process sequentially.

Release memory continuously.

Parser should support IDataSource streams directly.

============================================================

STEP 9

Connection Manager

Connection Manager becomes the first step of every workflow.

Local mode remains supported for development.

Remote mode becomes the preferred production workflow.

Parser must remain completely independent of the connection implementation.

============================================================

STEP 10

Memory Optimization

Review every DataFrame lifecycle.

Remove duplicate DataFrames.

Avoid repeated parsing.

Avoid repeated previews.

Avoid repeated canonical conversion.

Release objects aggressively.

Keep developer diagnostics.

Improve the DataFrame registry instead of removing it.

============================================================

STEP 11

Workflow Navigation

The workflow becomes

Connection

↓

Discovery

↓

Progressive Configuration

↓

Configuration Validation

↓

Processing

↓

Validation

↓

Reports

Each phase has a single responsibility.

Avoid hidden transitions.

Avoid duplicated processing paths.

============================================================

STEP 12

Do NOT Implement Future Features

Do NOT implement

Retailer Profiles

Cloud Storage

Authentication

CI/CD

Deployment

RBAC

Monitoring

Those belong to later milestones.

============================================================

EXPECTED DELIVERABLES

1.

Workflow Layer

2.

Cleaner UI

3.

Configuration-driven processing

4.

Reduced memory footprint

5.

Option objects replacing parameter explosion

6.

Cleaner ProcessingContext lifecycle

7.

Improved validation architecture

8.

Updated architecture documentation

============================================================

SUCCESS CRITERIA

The application should no longer feel like

Parser

↓

Validation

Instead it should feel like

Connection

↓

Discovery

↓

Configuration

↓

Processing

↓

Validation

↓

Reports

Every module should have one responsibility.

The workflow should orchestrate the platform.

The parser should simply execute the processing contract defined by the configuration.

Maintain backward compatibility wherever possible.

Work incrementally.

Run existing Playwright tests and regression tests after each significant change.

Commit changes in logical, reviewable increments rather than one massive refactor.

# DVA Platform Evolution
# Streaming Configuration Driven Data Onboarding Platform

Read the COMPLETE repository before making ANY modifications.

Understand the architecture first.

Do NOT immediately begin coding.

------------------------------------------------------------

CURRENT STATE

The repository already contains

✓ Parser Engine

✓ Canonical Data Layer

✓ Validation Engine

✓ Aggregation Engine

✓ Reporting

✓ Configuration Builder

✓ Connection Manager

✓ Local Data Source

✓ Remote SSH Data Source

✓ Runtime Metrics

✓ Playwright

✓ Regression Framework

✓ Documentation

The project is NOT being restarted.

The project must EVOLVE.

Reuse as much existing implementation as possible.

------------------------------------------------------------

OBJECTIVE

Transform the application into a Streaming Configuration Driven Data Onboarding Platform.

The parser should no longer drive the workflow.

The workflow should drive the parser.

------------------------------------------------------------

FIRST PRINCIPLE

The MFT Server is the ONLY Source of Truth.

The application should not require users to manually move retailer files.

Everything should happen directly against the MFT server.

Local mode remains available for testing only.

------------------------------------------------------------

NEW ARCHITECTURE

Presentation Layer

↓

Workflow Engine

↓

Data Source Layer

↓

Discovery Engine

↓

Configuration Builder

↓

Configuration Validator

↓

Streaming Parser

↓

Canonical Data Layer

↓

Aggregation Engine

↓

Calculation Engine

↓

Reports

------------------------------------------------------------

DO NOT

Redesign working parser modules.

Redesign validation.

Redesign aggregation.

Redesign reporting.

Reuse them.

------------------------------------------------------------

PHASE 1

Repository Review

Review the entire repository.

Understand

Parser

Workflow

Configuration Builder

Connection Manager

Validation

Aggregation

Reporting

Playwright

UI

State Management

Documentation

Identify reusable components.

Produce an internal implementation plan.

Do NOT code yet.

------------------------------------------------------------

PHASE 2

Workflow Refactoring

The application should now follow this workflow.

STEP 1

Launch

↓

Choose Workflow

Onboarding

Existing

↓

STEP 2

Choose Data Source

Local

Remote (SSH)

↓

STEP 3

If Remote

Connect

Authenticate

Browse MFT

Select Folder(s)

↓

STEP 4

If Fixed Width

Ask for Layout

Otherwise continue.

↓

STEP 5

Discovery

Read only SAMPLE data.

Never process the complete dataset.

Discovery must inspect only enough logical records to identify

Encoding

Delimiter

Header

Record Type

Multiline

Header Based

Schema

Possible Data Types

Possible Column Names

Display RAW Preview.

Raw Preview must display exactly what exists in source data.

No canonical conversion.

No validation.

No parsing.

------------------------------------------------------------

PHASE 3

Progressive Configuration Builder

Configuration should NOT appear all at once.

It should be built gradually.

Stage A

File Information

↓

User confirms

↓

Stage B

Record Information

↓

User confirms

↓

Stage C

Schema

↓

User confirms

↓

Stage D

Business Rules

↓

User confirms

↓

Stage E

Validation Configuration

↓

User confirms

↓

Configuration Complete

At every stage

Auto detect

Suggest

Allow correction

Continue

Configuration grows progressively.

------------------------------------------------------------

PHASE 4

Configuration Structure

Configuration must contain

GENERAL

FILE

SCHEMA

BUSINESS RULES

VALIDATION

OUTPUT

Validation section must define

Enabled

Required Columns

Group By Columns

Aggregation Columns

If omitted

Current default validation logic remains.

Configuration overrides defaults.

------------------------------------------------------------

PHASE 5

Configuration Validation

Before processing begins

Validate

Required mappings

Aggregation columns

Group By columns

Layouts

Delimiter

Business Rules

Configuration completeness

Only after successful validation

allow processing.

------------------------------------------------------------

PHASE 6

Streaming Processing

This is the most important phase.

DO NOT

Download the dataset.

DO NOT

Create local copies.

DO NOT

Load entire file unnecessarily.

Instead

Open remote stream

↓

Read sequentially

↓

Parse

↓

Canonical

↓

Aggregation

↓

Release memory

↓

Continue

Implement streaming architecture wherever practical.

Large datasets should never require local staging.

------------------------------------------------------------

PHASE 7

Validation Architecture

Separate validation into two independent engines.

ENGINE 1

Aggregation Engine

Input

Group By Columns

Aggregation Columns

Output

Aggregated Dataset

Only aggregation.

No calculations.

------------------------------------------------------------

ENGINE 2

Calculation Engine

Input

Aggregated BAU

Aggregated TEST

Calculate

Difference

Difference %

Sorting

Ranking

Tolerance

Output

Validation Results

This engine should become reusable across all validations.

------------------------------------------------------------

PHASE 8

UI

The UI should guide the user.

One logical page per phase.

1

Connection

↓

2

Discovery

↓

3

Configuration

↓

4

Validation of Configuration

↓

5

Processing

↓

6

Validation

↓

7

Reports

Avoid hidden functionality.

Avoid jumping between unrelated pages.

------------------------------------------------------------

PHASE 9

Memory

During discovery

Only sample records.

During processing

Streaming.

Release temporary DataFrames.

Never duplicate large DataFrames.

Never reread datasets unnecessarily.

Continue displaying runtime memory metrics.

------------------------------------------------------------

PHASE 10

Playwright

Update E2E tests.

Verify

Connection

Discovery

Configuration Builder

Configuration Validation

Streaming Processing

Validation

Reports

Regression

------------------------------------------------------------

FUTURE

Do NOT implement now.

Only prepare architecture.

Future features

Reusable Data Source Profiles

Configuration Repository

Profile Versioning

Cloud Data Sources

Enterprise Authentication

------------------------------------------------------------

IMPORTANT

Reuse existing modules.

Move functionality only if necessary.

Do not duplicate code.

Do not rewrite working components.

Integrate them into the new workflow.

If existing modules already solve a problem

reuse them.

------------------------------------------------------------

DELIVERABLES

Updated Workflow

Integrated Connection Manager

Streaming Discovery Engine

Progressive Configuration Builder

Configuration Validator

Streaming Processing

Separated Aggregation Engine

Separated Calculation Engine

Updated UI

Updated Playwright

Updated Documentation

Architecture Diagram

Migration Notes

Memory Report

------------------------------------------------------------

SUCCESS CRITERIA

The application should evolve from

Data Validation Tool

into

Streaming Configuration Driven Data Onboarding Platform

where

Data Source

↓

Discovery

↓

Configuration

↓

Streaming Processing

↓

Validation

↓

Reports

is the complete user journey.

Every module should have a single responsibility.

The parser should become just one component of the workflow rather than controlling the workflow itself.
Do this by seperatng tasks into milestone and finish it one by one


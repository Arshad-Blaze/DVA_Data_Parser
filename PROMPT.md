# DVA Platform Sprint
## Architecture Refactoring + Record-Based Parser (HEB)

This sprint is NOT about adding new features.

This sprint is about correcting a fundamental architectural flaw that is affecting onboarding, preview, layout building, flattening and retailer support.

The objective is to make the DVA Platform parser-driven instead of UI-driven.

The UI must never participate in parsing.

The parser must completely understand the input before the UI renders downstream steps.

==========================================================
PRIMARY GOAL
==========================================================

Refactor the architecture so that:

Connection

↓

Discovery

↓

Parser

↓

Canonical Dataset

↓

Column Mapping

↓

Validation

↓

Reports

becomes the ONLY processing pipeline.

Every retailer must follow this pipeline.

No retailer-specific workflow should exist inside the UI.

==========================================================
PROBLEM 1
Current Architecture
==========================================================

The current architecture leaks parser logic into the UI.

Example

User selects HEB

↓

Detection

↓

UI asks for Record Types

↓

User clicks Flatten

↓

Parser resumes

↓

Preview

This architecture is incorrect.

The parser is waiting for UI interaction before it can continue.

The UI should NEVER participate in parser decisions.

==========================================================
REQUIRED ARCHITECTURE
==========================================================

The new architecture must be

Connection

↓

Discovery

↓

Parser Factory

↓

Specific Parser

↓

Canonical Dataset

↓

Column Mapping

↓

Validation

↓

Reports

The UI simply consumes results.

==========================================================
DISCOVERY
==========================================================

Discovery becomes the intelligence layer.

Discovery must determine

• File Type
• Encoding
• Delimiter
• Record Length
• Header
• Trailer
• Disclaimer
• Metadata
• Blank Lines
• Record Types
• Parent Child Relationships
• Multi-file Relationships
• Join Keys
• Candidate Layouts
• Data Start Line
• Parser Recommendation
• Confidence
• Detection Reasoning

Discovery MUST NOT parse.

Discovery MUST NOT flatten.

Discovery MUST ONLY understand the file.

==========================================================
PARSER FACTORY
==========================================================

Create a ParserFactory.

ParserFactory selects parser automatically.

Examples

DelimitedParser

FixedWidthParser

RecordBasedParser

ParentChildParser

ExcelParser

SalesProductParser

No UI logic decides parser.

ParserFactory owns parser selection.

==========================================================
RECORD-BASED PARSER
==========================================================

HEB is NOT a multiline problem.

HEB is a Record-Based file.

Implement a dedicated RecordBasedParser.

Pipeline

Read

↓

Identify Record Types

↓

Build Record Tree

↓

Resolve Relationships

↓

Flatten

↓

Generate Parsed Dataset

↓

Infer Schema

↓

Generate Canonical Dataset

↓

Return

The parser must complete all these stages automatically.

==========================================================
RECORD TREE
==========================================================

Build an internal hierarchical model.

Example

File

├── Disclaimer

├── Header

├── Store

│      ├── Detail

│      ├── Detail

│      └── Detail

├── Store

│      ├── Detail

│      └── Detail

└── Trailer

The tree is INTERNAL.

The UI must never know it exists.

==========================================================
FLATTENING
==========================================================

Flattening is NOT a UI action.

Flattening is an internal parser stage.

Remove the "Flatten Records" concept from the UI.

The parser automatically flattens whenever required.

Users should never manually flatten data.

==========================================================
DISCOVERY RESULT
==========================================================

DiscoveryResult becomes the single contract.

DiscoveryResult must contain

File Architecture

Record Types

Relationships

Candidate Layouts

Data Start

Confidence

Recommended Parser

Warnings

Metadata

DiscoveryResult is passed downstream.

No downstream phase performs detection again.

==========================================================
CANONICAL DATASET
==========================================================

Every parser returns

CanonicalDataFrame

CanonicalMetadata

DiscoveryResult

Every parser must return identical contracts.

No retailer-specific schemas beyond this point.

==========================================================
COLUMN MAPPING
==========================================================

Retailer columns are mapped only once.

Examples

Store

Store_Number

Location

Site

↓

STORE_NUMBER

UPC

Barcode

SKU

↓

UPC_CODE

Description

Item Description

Product

↓

PRODUCT_DESCRIPTION

Units

Qty

Sales Qty

↓

UNITS_SOLD

Weight

Weight Qty

↓

WEIGHT_QTY

Sales

Retail

Total

↓

TOTAL_DOLLARS

After mapping

Validation

Aggregation

Reports

must ONLY use canonical names.

==========================================================
HEB REQUIREMENTS
==========================================================

The HEB retailer must process automatically.

Parser responsibilities

Ignore disclaimer.

Ignore metadata.

Detect HDR.

Detect Store records.

Detect Detail records.

Detect Trailer.

Build hierarchy.

Flatten hierarchy.

Generate Parsed Preview.

Generate Canonical Preview.

No user interaction required.

The UI must never ask

Record Prefixes

Flatten

Record Types

Parser Selection

These are parser responsibilities.

==========================================================
LAYOUT BUILDER
==========================================================

Layout Builder is moved later.

Correct flow

Discovery

↓

Parser

↓

Determine Detail Record

↓

Candidate Layout

↓

Layout Builder

↓

Parsed Preview

↓

Canonical Mapping

Do NOT ask users to build layouts before parser understands the records.

==========================================================
PREVIEW PIPELINE
==========================================================

Preview stages

Raw Preview

↓

Discovery Summary

↓

Parsed Preview

↓

Canonical Preview

No duplicate previews.

No stale previews.

No reruns.

==========================================================
UI RESPONSIBILITIES
==========================================================

UI should ONLY

Display previews

Display discovery summary

Display parser results

Allow column mapping

Allow validation

The UI never decides

Parser

Flattening

Relationships

Hierarchy

Record Types

==========================================================
RETAILER SUPPORT
==========================================================

The platform MUST successfully support

Retailer 1

Delimited with Units + Weight

Retailer 2

Pure Fixed Width

Retailer 3

HEB Record-Based

Retailer 4

Simple Delimited

Sales + Product Master

Parent Child

Header Detail Trailer

Different header/data delimiters

Metadata before data

Disclaimer blocks

Blank lines

Mixed record types

Variable layouts

Future retailers should require ONLY parser extensions.

No UI modifications.

==========================================================
ACCEPTANCE CRITERIA
==========================================================

The sprint is complete ONLY when

✓ UI contains no parser logic.

✓ No Flatten button exists.

✓ ParserFactory selects parser automatically.

✓ RecordBasedParser handles HEB completely.

✓ Discovery produces a complete DiscoveryResult.

✓ Parser consumes DiscoveryResult.

✓ Parser builds an internal record tree.

✓ Flattening happens automatically.

✓ Canonical Dataset is generated for every retailer.

✓ Validation receives identical schema regardless of retailer.

✓ Onboarding flow is identical for every retailer.

✓ No retailer-specific UI code exists.

✓ All four retailer samples complete end-to-end without runtime errors.

✓ Sales + Product relationship scenario completes successfully.

Do not stop when the code compiles.

Continue until the complete onboarding workflow successfully processes every retailer sample and the architecture matches the design described above.

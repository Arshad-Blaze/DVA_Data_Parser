# DVA Platform RC2.1
# Fixed Width UX & Numeric Processing Stabilization Sprint

Read the complete repository before making any changes.

Do NOT immediately start coding.

First understand the current implementation of:

- Detection
- Layout Builder
- Canonical Layer
- Processing
- Aggregation
- Numeric Parsing

Identify where the current implementation differs from the target workflow below.

============================================================
MISSION
============================================================

This sprint has TWO objectives only.

1.

Complete the Fixed Width onboarding experience.

2.

Make numeric conversion robust enough for production retailer datasets.

Do NOT introduce unrelated features.

Do NOT redesign the architecture.

Keep backward compatibility.

============================================================
PART 1
FIXED WIDTH USER EXPERIENCE
============================================================

Current implementation still assumes users already possess a Layout CSV.

Although an interactive Layout Builder exists, the workflow is still centered around uploading layouts.

The desired workflow is different.

------------------------------------------------------------

TARGET WORKFLOW

Connection

↓

Detection

↓

RAW Preview

↓

(If multiline)

Flatten

↓

Flattened Preview

↓

Interactive Layout Builder

↓

Canonical Schema

↓

Configuration

↓

Processing

------------------------------------------------------------

STEP 1

Connection Layer

Read only the first few records.

Display RAW Preview exactly as stored.

No parsing.

No delimiter split.

No layout.

No canonicalization.

RAW Preview exists only for understanding the incoming data.

------------------------------------------------------------

STEP 2

Detection

Detect

- Fixed Width
- Multiline
- HDR
- Record Types

Build DiscoveryResult.

Do not create DataFrames.

------------------------------------------------------------

STEP 3

If the dataset is multiline fixed width

Automatically flatten sample records.

Display

Flattened Preview

while keeping

RAW Preview

inside an expandable section for reference.

Users should always be able to compare

Original

↓

Flattened

------------------------------------------------------------

STEP 4

Layout Builder

Do NOT immediately ask users for a Layout CSV.

Instead present an interactive Layout Builder.

Uploading an existing Layout CSV becomes OPTIONAL.

The primary workflow is creating layouts inside the application.

------------------------------------------------------------

Layout Builder should support

Column Name

Start Position

End Position

Length (auto calculated)

Data Type

Nullable

Description

------------------------------------------------------------

BONUS (Preferred)

Provide a character ruler above the preview.

Example

123456789012345678901234567890

000012345ABCDE123456789XYZ

Selecting a character range should automatically populate

Start Position

End Position

Length

If Streamlit limitations prevent true drag-selection,

provide

Start Position

End Position

with live highlighting inside the preview.

------------------------------------------------------------

Layout validation

Detect

Overlapping columns

Duplicate names

Invalid ranges

Missing names

Zero lengths

Show immediate feedback.

------------------------------------------------------------

STEP 5

Generate Layout CSV automatically.

Support

Download

Save

Reuse

Upload Existing Layout

Uploading should remain optional.

------------------------------------------------------------

STEP 6

Generate Canonical Schema immediately after layout confirmation.

Do NOT continue using generic names such as

COL001

COL002

Instead create meaningful canonical names.

Business Mapping should consume Canonical Schema.

============================================================
PART 2
NUMERIC PROCESSING PIPELINE
============================================================

Current implementation fixes strict float casting by using

strict=False

This solves the symptom but not the overall design.

Implement a reusable Numeric Processing Pipeline.

------------------------------------------------------------

Pipeline

Raw Text

↓

Trim

↓

Normalize Whitespace

↓

Handle NULL Patterns

↓

Remove Currency Symbols

↓

Remove Thousands Separators

↓

Normalize Decimal Separator

↓

Handle Scientific Notation

↓

Validate Numeric Pattern

↓

Convert

↓

Aggregation

------------------------------------------------------------

Support values such as

100

100.25

1,234.56

$100.50

₹1000

NULL

N/A

NA

NaN

-

--

(empty)

Scientific notation

2.5e3

------------------------------------------------------------

Conversion must never crash aggregation.

Behaviour should be configurable.

AS_NULL

AS_ZERO

REJECT

Log invalid values.

Continue processing whenever possible.

============================================================
CONFIGURATION
============================================================

Allow Numeric Parsing configuration.

Examples

Decimal Separator

Thousands Separator

Currency Symbols

Negative Format

Locale (future)

Default behaviour should continue working for current retailers.

============================================================
TESTING
============================================================

Test Fixed Width

Single Line

Multiline

HDR

Large Layout

Uploaded Layout

Generated Layout

Mixed Record Types

------------------------------------------------------------

Test Numeric Parsing

Integers

Decimals

Currency

Thousands

Scientific

NULL

N/A

Spaces

Empty Strings

Negative Numbers

Invalid Text

------------------------------------------------------------

Run

Regression

Playwright

Streaming

Memory

Onboarding

Format Change

============================================================
DOCUMENTATION
============================================================

Update

Architecture

Execution Flow

Developer Guide

User Guide

Describe the new Layout Builder workflow.

Describe the Numeric Processing Pipeline.

============================================================
OUTPUT
============================================================

Generate

RC2_1_Report.md

Include

Architecture Changes

Workflow Changes

Fixed Width Improvements

Numeric Pipeline

Performance Impact

Regression Results

Known Limitations

============================================================
IMPORTANT
============================================================

Keep the solution simple.

Do not over-engineer.

Everything must remain configuration-driven.

Everything downstream must continue consuming Canonical Data.

Processing should never depend on retailer-specific parsing logic.

The objective is to make onboarding intuitive for business users while making numeric processing resilient for real-world retailer datasets.

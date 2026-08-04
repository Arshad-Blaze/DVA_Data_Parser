# DVA Platform RC2 - Functional Prototype Completion Sprint

This is NOT a code cleanup sprint.

This is NOT an architecture audit sprint.

This is NOT a documentation sprint.

This sprint exists for ONE purpose:

Build a completely working DVA prototype capable of onboarding and processing every retailer scenario collected during design without runtime errors.

Architecture Bible remains the ONLY source of truth.

============================================================
PRIMARY OBJECTIVE
============================================================

Do not optimize.

Do not refactor for style.

Do not clean documentation.

Do not change architecture unless absolutely necessary.

Instead, complete the functional pipeline.

A sprint is complete ONLY when every retailer scenario finishes end-to-end.

============================================================
SUCCESS CRITERIA
============================================================

The platform MUST successfully process all of the following.

Retailer 1

✓ Pipe delimited
✓ Header
✓ Mixed Units
✓ Mixed Weight
✓ Blank values
✓ Type IDs

Retailer 2

✓ Pure Fixed Width
✓ No Header
✓ Layout Builder

Retailer 3

✓ Confidential text
✓ Metadata
✓ Blank lines
✓ HDR
✓ S
✓ U
✓ Fixed Width
✓ Multiline
✓ Parent → Child

Retailer 4

✓ Standard Pipe Delimited

Retailer 5

✓ Sales file
✓ Product Master
✓ Automatic relationship detection
✓ Join
✓ Canonical dataset

Prototype is NOT complete until every scenario succeeds.

============================================================
PHASE 1
REDESIGN DISCOVERY
============================================================

Discovery is NOT parsing.

Discovery only understands the file.

Discovery should determine:

File Type

Delimiter

Encoding

Header

Metadata

Blank Lines

Trailer

Record Width

Record Types

Data Start Line

Parent/Child

Multiple Layouts

Candidate Business Keys

Candidate Join Keys

Flatten Required

Relationship Required

Confidence

Warnings

Recommendations

Discovery produces

DiscoveryResult

and NOTHING else.

============================================================
PHASE 2
DISCOVERY WORKFLOW
============================================================

The onboarding workflow should become

Connection

↓

Discovery

↓

Discovery Report

↓

Record Analysis

↓

Layout Selection

↓

Layout Builder

↓

Parsed Preview

↓

Canonical Mapping

↓

Configuration

↓

Processing

↓

Validation

↓

Reports

The Layout Builder must NEVER open before Discovery finishes.

============================================================
PHASE 3
RECORD ANALYSIS
============================================================

After Discovery,

analyze records.

Support

HDR

H

S

D

U

T

TRL

Parent

Child

Parent → Multiple Children

Determine

Header Records

Detail Records

Trailer Records

Default Data Record

If multiple layouts exist,

identify them.

Do NOT parse yet.

============================================================
PHASE 4
LAYOUT BUILDER
============================================================

The Layout Builder should consume ONLY

DiscoveryResult.

Never inspect the raw file again.

Builder should only contain

Column Name

Start

Length

Type

End Position is calculated automatically.

Uploaded layouts and manually built layouts must generate the same LayoutDefinition.

Only show ACTUAL DATA rows.

Do NOT display

Confidential text

Metadata

Headers

Blank lines

============================================================
PHASE 5
PARSER
============================================================

Parser consumes

DiscoveryResult

+

LayoutDefinition

Support

Delimited

Quoted CSV

Header/Data different delimiters

Fixed Width

Multiple Layouts

Parent/Child

Multiline

Flattening

Corrupted Rows

Embedded Delimiters

Variable Row Length

Reject bad rows into rejection report.

Never crash.

============================================================
PHASE 6
RELATIONSHIP ENGINE
============================================================

Support

Sales

+

Product

+

Store

+

Promotion

Discovery identifies

Relationship

Join Keys

Confidence

Parser performs joins.

Produce ONE Canonical Dataset.

============================================================
PHASE 7
CANONICAL MAPPING
============================================================

Every retailer must map into ONE schema.

Retailer column names disappear completely.

Canonical fields include

STORE_NUMBER

UPC_CODE

PRODUCT_DESCRIPTION

UNITS_SOLD

WEIGHT_QTY

WEIGHT_UOM

TOTAL_DOLLARS

SALES_DATE

CATEGORY

BRAND

DEPARTMENT

Every downstream module consumes ONLY these canonical fields.

============================================================
PHASE 8
QUANTITY RESOLUTION
============================================================

Implement

IF WeightQty > 0

ResolvedQuantity = WeightQty

QuantityType = WEIGHT

ELSE IF Units > 0

ResolvedQuantity = Units

QuantityType = UNIT

ELSE

ResolvedQuantity = 0

Carry

ResolvedQuantity

QuantityType

WeightUOM

OriginalUnits

through the entire pipeline.

============================================================
PHASE 9
PREVIEW PIPELINE
============================================================

Expose five distinct previews.

1 Raw Preview

2 Discovery Preview

3 Parsed Preview

4 Flatten Preview (when applicable)

5 Canonical Preview

Each preview represents one stage.

Preview must NEVER rerun Discovery.

============================================================
PHASE 10
STREAMLIT STABILITY
============================================================

Fix

Repeated reruns

Repeated Detection

Repeated Preview

Repeated Parsing

Duplicate widgets

Session corruption

Detection executes ONCE.

Preview reuses cached results.

============================================================
PHASE 11
ERROR HANDLING
============================================================

No runtime exceptions.

No

NoneType

list.to_dict

UnboundLocalError

KeyError

AttributeError

Handle

Wrong delimiter

Wrong encoding

Missing layout

Invalid layout

Missing columns

Permission errors

Connection loss

Gracefully.

============================================================
PHASE 12
VALIDATION
============================================================

Drive every retailer scenario through

Discovery

↓

Parser

↓

Canonical

↓

Aggregation

↓

Validation

↓

Reports

Verify every stage succeeds.

============================================================
PHASE 13
TESTING
============================================================

Build regression tests for

Retailer 1

Retailer 2

Retailer 3

Retailer 4

Retailer 5

Header/Data different delimiters

Parent/Child flattening

Multiple layouts

Mixed Weight

Mixed Units

Missing headers

Duplicate headers

Large streaming files

Do not claim support without automated tests.

============================================================
FINAL ACCEPTANCE
============================================================

The sprint is complete ONLY if:

✓ All five retailer scenarios complete successfully.

✓ Discovery correctly classifies every file.

✓ Layout Builder only opens after Discovery.

✓ Parser never crashes.

✓ Parent/Child files flatten correctly.

✓ Sales + Product merge correctly.

✓ One Canonical Dataset is produced.

✓ Validation begins from Canonical Dataset.

✓ No unnecessary Streamlit reruns.

✓ No runtime exceptions remain.

============================================================
DO NOT
============================================================

Do NOT perform documentation cleanup.

Do NOT reorganize markdown files.

Do NOT optimize imports.

Do NOT refactor for style.

Do NOT perform package cleanup.

Do NOT perform architecture scoring.

Those activities belong to the next sprint.

The ONLY goal of this sprint is to produce a stable, end-to-end, fully working DVA prototype capable of handling every real retailer scenario collected during design.

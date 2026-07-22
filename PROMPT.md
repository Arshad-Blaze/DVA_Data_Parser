MISSION: Improve the DVA Platform into a production-quality, retailer-agnostic data validation platform while preserving the existing layered architecture.

The Architecture Bible remains the ONLY source of truth.

DO NOT introduce shortcuts.
DO NOT bypass layers.
DO NOT break existing functionality.
Every change must improve architecture, maintainability and retailer coverage.

===========================================================
PHASE 1 - COMPLETE ENGINEERING AUDIT
===========================================================

Perform a COMPLETE audit before making any code changes.

Review:

• Architecture
• Package structure
• Module responsibilities
• Import structure
• Dependency versions
• Preview pipeline
• Detection pipeline
• Parser pipeline
• Canonical pipeline
• Aggregation
• Validation
• Reports
• Logging
• Exception handling
• Tests
• Documentation

Generate reports for:

Architecture
Detection
Preview
Canonical
Processing
Dependencies
Documentation
Business Logic
Retailer Coverage

List:

- Dead code
- Duplicate code
- Circular imports
- Unused imports
- Local imports inside functions
- Version incompatibilities
- Deprecated APIs
- Missing exception handling
- Missing logging
- Missing tests
- Layer violations
- Performance bottlenecks

DO NOT modify code yet.

===========================================================
PHASE 2 - DEPENDENCY & VERSION COMPATIBILITY
===========================================================

Verify every dependency.

Requirements:

• Verify Python version compatibility.
• Recommend one supported Python version.
• Every dependency must support that version.
• Remove unnecessary libraries.
• Remove duplicate packages.
• Remove abandoned libraries.
• Remove hidden dependencies.

Investigate:

pyiceberg

Determine:

- Why it is requested
- Where it is imported
- Whether it is actually required
- Remove it if unused

I cannot install Visual Studio Build Tools.

Avoid packages requiring native compilation whenever possible.

Update:

requirements.txt
requirements-dev.txt
pyproject.toml

Pin compatible versions.

===========================================================
PHASE 3 - IMPORT CLEANUP
===========================================================

All imports must exist ONLY at module level.

NO imports inside:

functions
methods
loops
conditions
callbacks

unless absolutely unavoidable.

Group imports:

1 Standard Library

2 Third Party

3 Local Modules

Remove:

unused imports
duplicate imports
wildcard imports

Run import validation.

===========================================================
PHASE 4 - DETECTION ENGINE REVIEW
===========================================================

Review the detection engine against every retailer scenario discussed.

It must support:

✓ Delimited

✓ Fixed Width

✓ Fixed Width Multiline

✓ HDR

✓ Disclaimer

✓ Trailer

✓ Header

✓ No Header

✓ Multiple Headers

✓ Multiple Record Types

✓ Record Type Selection

✓ Multiple File Inputs

✓ Sales + Product files

✓ Start Line Detection

✓ Record Length Detection

✓ Candidate Layout Detection

✓ Business Key Detection

✓ Relationship Key Detection

✓ Encoding Detection

✓ Delimiter Detection

✓ Date Detection

✓ UPC Detection

✓ Store Detection

✓ Quantity Detection

✓ Weight Detection

✓ UOM Detection

✓ Confidence Scoring

The detection layer should automatically recommend:

layout

record types

join keys

quantity columns

weight columns

uom

business keys

header

start line

encoding

delimiter

Generate confidence scores.

===========================================================
PHASE 5 - PARSER REVIEW
===========================================================

Review every parser.

Delimited

Fixed Width

Multiline

HDR

Flattening

Streaming

Chunking

Validate against retailer scenarios.

Retailer 1

Retailer 2

Retailer 3

Retailer 4

Sales + Product relationship

No unnecessary rereads.

No duplicate parsing.

===========================================================
PHASE 6 - PREVIEW REVIEW
===========================================================

Preview is critical.

Review for bugs.

Verify:

Raw Preview

Parsed Preview

Flattened Preview

Canonical Preview

Streaming Preview

Relationship Preview

Quantity Preview

Very large files

Cache invalidation

Memory usage

Source changes

Preview should NEVER crash.

Gracefully handle:

None

Empty DataFrame

Missing Layout

Wrong Layout

Unsupported Encoding

Unexpected delimiter

Preview must always display useful diagnostics.

===========================================================
PHASE 7 - QUANTITY ENGINE
===========================================================

Implement quantity resolution exactly as follows:

IF Weight > 0

Use Weight

ELSE IF Weight == 0 AND Units > 0

Use Units

ELSE IF Weight is NULL

Use Units

ELSE

0

Carry through:

QuantityType

UOM

PreferredQuantity

Weight

Units

through

Canonical

Aggregation

Validation

Reports

Do NOT lose metadata.

===========================================================
PHASE 8 - AGGREGATION REVIEW
===========================================================

Review aggregation.

Store

UPC

Item

Category

Brand

Support future configurable aggregation.

Generate summaries:

Top 5 Stores

Bottom 5 Stores

Top Categories

Top Brands

Top UPCs

Largest Sales

Largest Quantity

Validation Summary

Business KPIs

Each validation output should contain an additional Summary worksheet.

DO NOT break current outputs.

===========================================================
PHASE 9 - EXCEPTION HANDLING
===========================================================

Every module must have robust exception handling.

No raw tracebacks should reach the UI.

Catch:

File errors

Permission errors

Encoding errors

Missing layout

Parser errors

Type conversion

Invalid mapping

Missing columns

SSH failures

Memory issues

Network failures

Return meaningful messages.

===========================================================
PHASE 10 - LOGGING
===========================================================

Implement structured logging.

Every major stage should log:

Detection

Discovery

Preview

Parser

Canonical

Aggregation

Validation

Output

Flush

Log:

execution time

memory

warnings

errors

selected options

retailer profile

Never spam logs.

===========================================================
PHASE 11 - DOCUMENTATION CLEANUP
===========================================================

Review every markdown.

Move documentation into:

docs/

architecture/

developer/

user/

audit/

release/

historical/

Archive obsolete OpenCode reports.

Keep only necessary root files.

Update architecture diagrams.

Update developer guide.

Update user guide.

===========================================================
PHASE 12 - TESTING
===========================================================

Create tests for:

Retailer 1

Retailer 2

Retailer 3

Retailer 4

Sales + Product

Mixed Weight

Mixed Units

HDR

Multiline

Disclaimer

Large Files

Streaming

Relationship Join

Preview

Canonical

Aggregation

Validation

Regression

No existing tests may fail.

===========================================================
FINAL VALIDATION
===========================================================

Before any commit:

Run:

Architecture Audit

Dependency Audit

Import Audit

Detection Audit

Preview Audit

Canonical Audit

Processing Audit

Retailer Coverage Audit

Documentation Audit

Business Logic Audit

Regression Tests

Performance Tests

Memory Tests

Provide a final report containing:

Architecture Score

Retailer Coverage Score

Detection Score

Preview Score

Engineering Score

Production Readiness Score

Remaining Risks

Recommended Next Sprint

Only after every validation passes:

Commit

Push

Prepare next sprint plan.

The objective is not simply to make the code work.

The objective is to produce a clean, maintainable, extensible, production-quality DVA Platform capable of handling diverse retailer data feeds with strong architecture, robust detection, reliable previews, clean engineering practices, and comprehensive reporting.

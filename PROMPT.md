# DVA Platform
## RC3 - Architecture Finalization & Retailer Certification Sprint

STOP.

Do not introduce any new architectural abstractions.

Do not redesign Workflow Engine.

Do not redesign Pipeline Registry.

Do not redesign Pipeline Context.

The architecture has reached sufficient maturity.

This sprint focuses on proving that the architecture works with real retailer datasets and filling the last architectural gaps.

====================================================================
PRIMARY OBJECTIVE
====================================================================

The platform must become a fully working retailer-agnostic ingestion platform.

The objective is NOT code compilation.

The objective is NOT documentation.

The objective is NOT architecture experimentation.

The objective is to prove that the current architecture successfully supports every retailer scenario discussed.

Every retailer must successfully execute

Connection

↓

Discovery

↓

Dataset Graph

↓

Transformation Planner

↓

Transformation Engine

↓

Parser Pipeline

↓

Canonical Mapping

↓

Quantity Resolution

↓

Canonical Dataset

↓

Data Quality

↓

Aggregation

↓

Validation Rule Engine

↓

Insights Engine

↓

Reporting

↓

Downloads

Every retailer must use the SAME architecture.

Only DiscoveryResult, DatasetGraph and TransformationPlan should differ.

====================================================================
ARCHITECTURAL COMPLETION ITEMS
====================================================================

Complete the remaining missing architecture.

------------------------------------------------------------
1. Canonical Mapping Stage
------------------------------------------------------------

Introduce an explicit Canonical Mapping stage.

Current

Parser

↓

Canonical Dataset

Required

Parser

↓

Canonical Mapper

↓

Canonical Dataset

Responsibilities

Map retailer-specific physical columns into platform canonical columns.

Support aliases.

Support confidence scoring.

Support mapping suggestions.

Support user overrides.

Canonical schema must include

STORE_NUMBER

UPC_CODE

PRODUCT_DESCRIPTION

TRANSACTION_DATE

UNITS_SOLD

WEIGHT_QTY

WEIGHT_UOM

TOTAL_DOLLARS

CATEGORY

BRAND

DEPARTMENT

STORE_NAME

ITEM_SIZE

ITEM_UOM

No downstream layer may depend on retailer column names.

------------------------------------------------------------
2. Quantity Resolution Stage
------------------------------------------------------------

Create an explicit Quantity Resolution stage.

Responsibilities

Resolve mixed quantity retailers.

Rules

IF WeightQty > 0

    Use WeightQty

ELSE IF WeightQty == 0 AND Units > 0

    Use Units

ELSE

    Use Units

Preserve

OriginalUnits

OriginalWeight

ResolvedQuantity

QuantitySource

WeightUOM

Support every retailer.

No aggregation layer should implement quantity rules.

------------------------------------------------------------
3. Data Quality Stage
------------------------------------------------------------

Introduce a Data Quality stage.

Run BEFORE Aggregation.

Checks include

Duplicate Keys

Missing Mandatory Columns

Missing UPC

Missing Store

Invalid Dates

Invalid Quantity

Negative Sales

Invalid UOM

Corrupted Records

Malformed Rows

Unsupported Encoding

Unexpected Nulls

Output

DataQualityReport

Warnings

Reject Dataset

Data Quality should NOT stop the pipeline unless configured.

------------------------------------------------------------
4. Insights Engine
------------------------------------------------------------

Separate Insights from Reporting.

Insights Engine responsibilities

Top 5 Stores by Sales

Top 5 Stores by Quantity

Bottom 5 Stores

Top Categories

Top Brands

Top Departments

Sales Distribution

Quantity Distribution

Missing Store Statistics

Validation Summary KPIs

Insights Engine outputs

InsightsDataset

Reporting only renders.

------------------------------------------------------------
5. Reporting
------------------------------------------------------------

Reporting consumes

ValidationDataset

InsightsDataset

Reporting never calculates business metrics.

Reporting only formats.

Support

CSV

Excel (future)

Summary Sheets

Downloads

====================================================================
RETAILER CERTIFICATION
====================================================================

Run complete certification against all known scenarios.

Scenario 1

Retailer 1

Delimited

Weight

Units

Scenario 2

Retailer 2

Pure Fixed Width

Scenario 3

Retailer 3

HEB Record-Based

Disclaimer

HDR

Store

Detail

Trailer

Scenario 4

Retailer 4

Simple Delimited

Scenario 5

Sales + Product

Scenario 6

Header delimiter different from detail delimiter

Scenario 7

Parent Child

Scenario 8

Header Trailer

Scenario 9

Metadata Blocks

Scenario 10

Blank Lines

Scenario 11

Mixed Quantity

Scenario 12

Different Encodings

Scenario 13

Variable Width Records

Scenario 14

Large Files

Scenario 15

Quoted Delimiters

Scenario 16

Missing Headers

Scenario 17

Duplicate Headers

Scenario 18

Multiple Sheets

Scenario 19

Relationship Datasets

Scenario 20

Future Unknown Retailer

Every scenario must be executed.

Every scenario must be documented.

====================================================================
END-TO-END CERTIFICATION
====================================================================

For every retailer generate

Connection Report

↓

Discovery Report

↓

Dataset Graph

↓

Transformation Plan

↓

Transformation Summary

↓

Parser Report

↓

Canonical Mapping Report

↓

Quantity Resolution Report

↓

Data Quality Report

↓

Aggregation Report

↓

Validation Report

↓

Insights Report

↓

Reporting Output

Every stage must indicate

Input

Output

Execution Time

Warnings

Errors

Recovery

====================================================================
PIPELINE VALIDATION
====================================================================

Validate

No duplicate detection.

No duplicate parsing.

No duplicate transformations.

No duplicate previews.

No duplicate joins.

No duplicated mapping.

No retailer-specific logic beyond Discovery, DatasetGraph and TransformationPlan.

====================================================================
FRONTEND VALIDATION
====================================================================

Confirm

UI performs only presentation.

UI never performs

Detection

Flattening

Joining

Transformation

Aggregation

Validation

Reporting

Parser selection

Record selection

====================================================================
PERFORMANCE VALIDATION
====================================================================

Measure

Discovery Time

Transformation Time

Parser Time

Canonical Time

Aggregation Time

Validation Time

Report Time

Memory Usage

Peak Memory

Streaming Behaviour

Chunk Processing

====================================================================
OUTPUT DOCUMENTS
====================================================================

Generate

Retailer_Certification_Report.md

Architecture_Completion_Report.md

Canonical_Mapping_Design.md

Quantity_Resolution_Design.md

Data_Quality_Design.md

Insights_Engine_Design.md

Pipeline_Performance_Report.md

End_To_End_Certification.md

Regression_Test_Report.md

Production_Readiness_Report.md

====================================================================
FINAL SCORECARD
====================================================================

Produce a scorecard.

Architecture

Discovery

Dataset Graph

Transformation Planner

Transformation Engine

Parser Pipeline

Canonical Mapping

Quantity Resolution

Data Quality

Aggregation

Validation

Insights

Reporting

Frontend / Backend Separation

Retailer Agnosticism

Performance

Scalability

Maintainability

Test Coverage

Production Readiness

Give each score out of 100.

====================================================================
SUCCESS CRITERIA
====================================================================

The sprint is complete ONLY if

✓ Every retailer sample completes successfully.

✓ All four real retailer datasets execute without manual intervention.

✓ Sales + Product relationship works.

✓ HEB works automatically.

✓ Canonical Mapping is explicit.

✓ Quantity Resolution is isolated.

✓ Data Quality runs before Aggregation.

✓ Insights are separated from Reporting.

✓ Reporting performs rendering only.

✓ UI contains zero business logic.

✓ No duplicate pipeline execution exists.

✓ No retailer-specific logic exists outside Discovery, DatasetGraph and TransformationPlan.

✓ Every architectural document matches the actual implementation.

Only after ALL of the above pass should RC3 be considered complete.

Do not mark the sprint complete because the code compiles.

Mark it complete only when the platform demonstrates end-to-end success on every retailer scenario and the architecture is functionally validated.

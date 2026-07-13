# DVA Platform 1.0 RC1
# Sprint B - Configuration & Canonical Model

MISSION

Complete the Configuration System.

The configuration becomes the contract that drives the entire platform.

============================================================

Implement proper schema separation.

Physical Schema

↓

Canonical Schema

↓

Business Mapping

============================================================

Physical Schema

Represents exactly what Discovery found.

Never changes.

============================================================

Canonical Schema

Editable by the user.

Business-friendly names.

Immediately propagates to

Business Rules

Operations

Validation

Reports

============================================================

Business Mapping

Maps business concepts

Store

UPC

Description

Quantity

Price

to Canonical Schema.

============================================================

VALIDATOR

Validator validates

Canonical Schema

NOT Physical Schema.

Never require mapping of unused columns.

Validate only required mappings for the selected operation.

============================================================

OPERATION-AWARE VALIDATION

Validation

Requires

Store

UPC

Description

Quantity

Price

Aggregate

Requires

Group By

Aggregation Columns

Statistics

No mappings required.

Export

No mappings required.

============================================================

QUANTITY ABSTRACTION

Support

Units

Weight

Mixed datasets

Configuration

Units Column

Weight Column

Weight UOM

Resolution Rule

Canonical Dataset exposes

EFFECTIVE_QUANTITY

QUANTITY_TYPE

Original retailer columns remain.

============================================================

TESTING

Header

No Header

Delimited

Fixed Width

Multiline

Units Only

Weight Only

Mixed

============================================================

OUTPUT

CONFIGURATION_REVIEW.md

Schema propagation report

Validator report

Quantity architecture

Regression report

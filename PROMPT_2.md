I want to improve state management without changing application behaviour.

Do NOT change validation logic.

Do NOT change parsing behaviour.

Do NOT change UI.

Goal
-----

Replace scattered session state variables with a single Processing Context.

Current State
-------------

Session state currently stores many independent objects such as

schema

mapping

layout

store aggregation

item aggregation

metadata

preview

etc.

This makes the processing pipeline harder to maintain.

Desired Design
--------------

Create one ProcessingContext object.

Example

ProcessingContext

- parser configuration
- detected file type
- encoding
- delimiter
- layout
- schema
- column mapping
- processing metadata
- statistics
- store aggregation
- item aggregation
- report metadata

The ProcessingContext becomes the single source of truth for the processing pipeline.

Execution Flow

User

↓

Detection

↓

Schema

↓

Column Mapping

↓

Processing Context

↓

Parser

↓

Canonical Data

↓

Aggregation

↓

Validation

↓

Reports

Requirements
------------

1. Minimize changes.

2. Existing validation modules should continue to work.

3. Existing parser should continue to work.

4. UI should simply read/write ProcessingContext.

5. No behavioural changes.

6. No unnecessary refactoring.

Questions to answer before coding

1. Which current session state variables belong inside ProcessingContext?

2. Which modules should own ProcessingContext?

3. Should ProcessingContext be a dataclass or another structure?

4. Explain the recommended design before implementing.

After implementation

Provide

- class diagram
- execution flow
- files changed
- migration summary
- regression risks

Run all tests.

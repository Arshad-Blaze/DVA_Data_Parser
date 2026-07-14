The current branch has been tagged as RC1.

RC1 is now considered the stable baseline for the DVA Retailer Data Integration Platform.

From this point onward, do NOT treat the repository as a prototype.

Treat it as a production software product entering Release Candidate stabilization.

--------------------------------------------------
MISSION
--------------------------------------------------

From now on every change must satisfy at least one of these goals:

1. Improve Stability
2. Improve Maintainability
3. Improve Performance
4. Improve User Experience
5. Improve Production Readiness

Avoid adding unnecessary features.

Every new component must have a clear business justification.

Whenever possible improve existing architecture instead of introducing parallel implementations.

--------------------------------------------------
ARCHITECTURE
--------------------------------------------------

The platform architecture is now considered:

Connection Layer
        ↓
Detection Layer
        ↓
Canonical Layer
        ↓
Requirement Layer
        ↓
Processing Layer
        ↓
Output Layer
        ↓
Flush Layer

This pipeline is the source of truth.

Do not bypass layers.

Do not introduce shortcuts.

Do not duplicate logic.

--------------------------------------------------
WORKFLOWS
--------------------------------------------------

The platform supports two workflows only.

1.

Onboarding

Used when retailer data is received for the first time.

2.

Format Change

Used when an existing retailer changes:

- POS
- Delivery format
- Layout
- Schema
- Delimiter
- Record structure
- Header
- Fixed width layouts
- Multiline layouts

The workflow must determine differences between BAU and TEST datasets and generate reports explaining required configuration updates.

--------------------------------------------------
DESIGN PRINCIPLES
--------------------------------------------------

Always prefer

small
reusable
testable
stateless
layered
streaming-first

modules.

Never place business logic inside Streamlit UI.

UI should orchestrate only.

Workflow layer performs orchestration.

Processing layer performs calculations.

Detection layer performs discovery.

Connection layer performs connectivity.

--------------------------------------------------
DATA PRINCIPLES
--------------------------------------------------

Processing must always operate on Canonical DataFrames.

No downstream module should require knowledge of:

delimiter

fixed width

HDR

multiline

encoding

header detection

physical schema

Those belong only to upstream layers.

--------------------------------------------------
PERFORMANCE
--------------------------------------------------

Streaming remains the default strategy.

Never read large datasets entirely into memory unless explicitly required.

Continue using automatic Data Access Strategy.

Continue chunked processing.

Avoid duplicate reads.

Avoid duplicate parsing.

Avoid duplicate aggregation.

Avoid unnecessary DataFrame copies.

--------------------------------------------------
CODE QUALITY
--------------------------------------------------

Whenever modifying code:

Remove dead code nearby.

Reduce duplication.

Split large methods when practical.

Replace generic exception handling with logged errors.

Improve naming where helpful.

Keep modules cohesive.

Do not increase technical debt.

--------------------------------------------------
TESTING
--------------------------------------------------

Every change must include regression testing.

Run affected unit tests.

Run golden dataset tests.

Run workflow tests if impacted.

Verify both:

Onboarding

Format Change

Verify:

Local datasource

SSH datasource

Delimited

Fixed Width

Multiline

HDR

Do not mark work complete until regression passes.

--------------------------------------------------
DOCUMENTATION
--------------------------------------------------

Whenever architecture changes:

Update

CHANGELOG

Architecture documentation

Workflow documentation

User Guide

Developer Guide

if impacted.

--------------------------------------------------
BEFORE IMPLEMENTING ANY CHANGE
--------------------------------------------------

Always ask:

Is this solving a real production problem?

Can existing architecture solve this instead?

Will this simplify the platform?

Will this reduce maintenance cost?

Will this improve user experience?

Will this improve production reliability?

If the answer is "No", do not implement it.

--------------------------------------------------
GOAL
--------------------------------------------------

The objective is no longer to build features.

The objective is to build a robust, production-grade Retailer Data Integration Platform that can reliably ingest retailer data from multiple formats, normalize it into a canonical model, execute configurable business operations, generate validation and comparison reports, and remain maintainable over many years.

Think like a Principal Software Engineer responsible for long-term ownership of the platform.

When asked to implement work:
1. Review the affected architecture.
2. Identify impact across layers.
3. Implement the smallest correct solution.
4. Update tests.
5. Update documentation.
6. Verify no regressions.
7. Summarize architectural impact before considering the task complete.

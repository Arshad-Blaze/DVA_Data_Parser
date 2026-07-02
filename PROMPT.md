# Runtime Regression Investigation

STOP ALL DEVELOPMENT.

Do NOT implement new features.

Do NOT refactor.

Do NOT optimize.

Do NOT clean up code.

The architecture is considered complete.

The application currently does not function correctly.

Your ONLY objective is to determine why the runtime behaviour has regressed.

==========================================================
REAL OBSERVATIONS
==========================================================

These observations come from actual execution.

Observation 1

Onboarding

User selects file.

↓

Detection executes.

↓

Preview is generated.

↓

Nothing appears in the UI afterwards.

↓

Terminal becomes idle.

↓

After approximately 5 seconds

↓

The entire machine freezes or reboots.

----------------------------------------------------------

Observation 2

The terminal shows

File received

File type detection

Detection

Preview generation

executing THREE TIMES.

This should only happen ONCE.

----------------------------------------------------------

Observation 3

After the third execution

nothing more happens.

No exception.

No traceback.

No Streamlit error.

The terminal simply stops.

A few seconds later

the system crashes.

----------------------------------------------------------

Observation 4

Existing workflow

Immediately after column mapping

an error appears.

Even after correctly mapping every column

the error remains.

==========================================================
YOUR TASK
==========================================================

Do NOT guess.

Trace the actual execution path.

I want to know WHY detection executes three times.

==========================================================
PART 1

STREAMLIT RERUN ANALYSIS

==========================================================

Find

Every location that causes

- st.rerun()

- implicit reruns

- callback reruns

- widget reruns

- session_state updates

For every rerun explain

What triggered it.

Why it occurred.

Which functions execute again.

==========================================================
PART 2

EXECUTION TRACE

==========================================================

Trace the onboarding workflow.

Application Start

↓

Upload

↓

Detection

↓

Preview

↓

Mapping

↓

Processing

↓

Aggregation

↓

Validation

↓

Reports

For every phase report

Current function

Current ProcessingContext

Current session_state

Current callback

Current button

Current rerun

==========================================================
PART 3

PROCESSING CONTEXT

==========================================================

Review the lifecycle.

Determine

How many ProcessingContext objects are created.

When they are recreated.

When they are discarded.

Whether they survive reruns.

Whether they are accidentally replaced.

==========================================================
PART 4

SESSION STATE

==========================================================

Audit every session_state write.

Identify

State recreated

State overwritten

State deleted

State copied

Large DataFrames stored

Large DataFrames duplicated

Expensive objects recreated

==========================================================
PART 5

PERFORMANCE TRACE

==========================================================

Find every expensive operation.

Examples

Detection

Preview

Parser

Normalizer

Aggregation

Validation

Reports

Metrics

Logging

Determine

How many times each executes

during ONE upload.

Expected

Detection

1

Preview

1

Parser

1

Aggregation

1

Validation

1

Report

1

If any executes multiple times

identify why.

==========================================================
PART 6

MEMORY TRACE

==========================================================

Find

Large DataFrames

LazyFrame collections

collect()

write_csv()

concat()

group_by()

join()

session_state storage

ProcessingContext storage

Determine

Whether memory continually increases

between reruns.

==========================================================
PART 7

DEBUG INSTRUMENTATION

==========================================================

Temporarily instrument the application.

Every rerun should print

==================================================
STREAMLIT RERUN
==================================================

Timestamp

Current Phase

Current ProcessingContext id()

Current Session id

Current File

Current Callback

Current Button

Current Memory

Peak Memory

--------------------------------------------------

Every expensive function should print

ENTER

EXIT

Elapsed Time

Rows

Memory

==========================================================
PART 8

ROOT CAUSE

==========================================================

After tracing everything

identify

Why detection runs three times.

Why onboarding never advances.

Why Existing errors immediately.

Why the machine eventually crashes.

==========================================================
IMPLEMENTATION

==========================================================

DO NOT FIX YET.

First provide

Root Cause

Evidence

Affected Files

Smallest Possible Fix

Risk

Only after identifying the exact regression

should code be modified.

Do not implement speculative fixes.

Think like a debugging engineer, not a feature developer.

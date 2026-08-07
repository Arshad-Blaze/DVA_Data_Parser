# HEB Architecture Report

**Status:** Sprint 3 deliverable — zero-manual-interaction record-based flow

---

## 1. The Flaw That HEB Exposed

The HEB retailer (record-based / multiline files with `H`/`D`/`T` records)
exposed the architectural flaw: transformation decisions were spread across
Discovery, the UI (flatten button, record-prefix textbox, parser dropdown),
and the parser itself.

### Current implementation (rejected)

```
Discovery → UI → Flatten → Parser
```

The UI asked the user for a record prefix, whether to flatten, the hierarchy,
and the parser type.

### New implementation (Sprint 3)

```
Discovery
   ↓
DatasetGraph
   ↓
TransformationPlan
   ↓
TransformationEngine
   ↓
RecordBasedParser
   ↓
ParsedDataset
   ↓
CanonicalDataset
```

---

## 2. What the User Is Never Asked

Per PROMPT.md HEB Acceptance Criteria, the user must NEVER be asked for:

- Record Prefix
- Flatten
- Hierarchy
- Parser Type

The sample processes automatically:

```
File Selected
   ↓
Discovery Summary
   ↓
Transformation Summary
   ↓
Parsed Preview
   ↓
Canonical Preview
   ↓
Column Mapping
   ↓
Validation
```

The Transformation Summary is derived from the `TransformationPlan`
produced before any execution.

---

## 3. How the HEB File Flows

A sample H|D|T file:

```
H|S001|2024-01-15
D|S001|100001|Widget A|10|99.90
D|S001|100002|Gadget B|5|49.95
T|2|149.85
```

| Stage | What happens |
|-------|--------------|
| Discovery | Detects `file_type="multiline"`, `ml_record_types=["H","D","T"]`, `trailer_prefix="T"`, delimiter `\|` |
| Dataset Graph | `record_types=["H","D","T"]`, `hierarchy={"H":"D"}`, `file_roles` |
| Transformation Planner | `flatten_operations` (parent H, children [D]), `trailer_removal=["T"]` |
| Transformation Engine | Flattens: parent fields replicated onto D rows; T dropped; 2 rows out; ops `("flatten_hierarchy",)` |
| Parser | Reads already-flattened rows; applies column names; `transformed: True` |
| Canonical Dataset | Normalizes to canonical schema |
| Aggregation / Validation / Reporting | Unchanged, retailer-agnostic |

---

## 4. No Flatten Button

There is no flatten button, record-prefix textbox, or parser dropdown in the
UI. The UI only displays results. All hierarchy decisions are derived
automatically by Discovery → Dataset Graph → Planner.

---

## 5. Verification

- `test_full_pipeline_runs_transformation_end_to_end` drives a real H|D|T
  file through the **full 10-stage pipeline** (connection → reporting) with
  zero manual inputs: `transformed.operations == ("flatten_hierarchy",)`,
  2 detail rows, parsed row count 2, canonical + aggregation succeed.
- `test_dataset_graph_stage_captures_record_types_and_layout` asserts
  `record_types=["H","D","T"]` and `hierarchy={"H":"D"}`.
- `test_transformation_engine_flattens_multiline_delimited` asserts the
  engine alone reproduces the flatten.

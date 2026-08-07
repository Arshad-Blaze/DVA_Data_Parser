# Transformation Planner Design

**Status:** Sprint 3 deliverable — plans only, never executes

---

## 1. Purpose

The Transformation Planner converts

```
DiscoveryResult
   +
DatasetGraph
   ↓
TransformationPlan
```

It captures **intent**: an ordered set of operations that the Transformation
Engine will execute. The planner MUST NOT execute anything — it only builds
the execution plan.

---

## 2. Contract

Defined in `dav_tool/pipeline/contracts.py` (frozen dataclass).

```python
@dataclass(frozen=True)
class TransformationPlan:
    flatten_operations: Tuple[Dict[str, Any], ...]   # record tree config
    join_operations: Tuple[Dict[str, Any], ...]      # enrichment left-joins
    header_removal: int                              # lines to skip at top
    trailer_removal: Tuple[str, ...]                 # prefixes marking trailers
    metadata_removal: Tuple[str, ...]                # pure-metadata prefixes
    parent_replication: Tuple[str, ...]              # parents to replicate
    child_expansion: Tuple[str, ...]                 # child types to expand
    column_normalization: Dict[str, str]             # physical → canonical hints
```

---

## 3. Operations Supported

The plan can express the full operation catalogue required by PROMPT.md:

| Operation | Plan field |
|-----------|------------|
| Remove disclaimer / header | `header_removal` |
| Remove metadata sections | `metadata_removal` |
| Ignore trailer | `trailer_removal` |
| Flatten parent/child | `flatten_operations` |
| Expand headers | `parent_replication` / `child_expansion` |
| Merge Sales/Product | `join_operations` |
| Merge Store / Department | `join_operations` (multi-file) |
| Select record types | derived from `flatten_operations` + discovery |
| Apply fixed width layout | `metadata_removal`-free; layout carried by discovery |
| Apply delimiter | carried by discovery (never in the plan) |

---

## 4. Builder (Transformation Planning Stage)

`dav_tool/pipeline/stages/transform_plan.py`:

| Signal | Plan output |
|--------|-------------|
| `graph.hierarchy` non-empty | `flatten_operations` with parent/children |
| `discovery.trailer_prefix` | `trailer_removal` |
| `discovery.header_prefix` | `parent_replication` |
| `discovery.fixed_width_detail_prefixes` | `child_expansion` |
| `ml_record_types` containing trailer (T/TRL) | `trailer_removal` |
| `graph.relationships` | `join_operations` (target_role="product") |
| `discovery.start_line` | `header_removal` |
| Primary node columns | `column_normalization` via role map |

The stage requires a `DatasetGraph`; without one it raises
`FatalStageError`.

---

## 5. What the Planner Does NOT Do

- No file reading.
- No flattening, joining, or reshaping.
- No normalization — `column_normalization` only records *intent*; the
  actual rename happens later in the Canonical Dataset Stage.
- No parser selection — that stays in the Parser Registry.

---

## 6. Why a Separate Planner + Engine

Separating plan from execution gives:

- **Auditability** — the plan is a declarative record of what *should*
  happen, comparable against what actually did (see `TransformedDataset`).
- **Reuse** — the same plan shape serves every retailer; only the planner
  inputs differ.
- **Testability** — plans can be unit-tested without touching files.
- **Observability** — the UI can display a Transformation Summary from the
  plan before any execution (HEB acceptance flow).

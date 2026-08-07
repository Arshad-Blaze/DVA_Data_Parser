# DatasetGraph Design

**Status:** Sprint 3 deliverable — descriptive, no parsing

---

## 1. Purpose

`DatasetGraph` is a **purely descriptive** model of the logical relationships
between datasets. It is produced by the Dataset Graph Stage from a
`DiscoveryResult` and consumed by the Transformation Planner to derive a
`TransformationPlan`.

No parsing occurs in the graph. It contains no data — only structure,
metadata, and relationship intent.

---

## 2. Contract

Defined in `dav_tool/pipeline/contracts.py` (frozen dataclass).

```python
@dataclass(frozen=True)
class DatasetGraph:
    datasets: Tuple[DatasetNode, ...]            # ordered, primary (sales) first
    relationships: Tuple[Dict[str, str], ...]    # source column → target column
    hierarchy: Dict[str, str]                    # parent record type → child type
    join_keys: Tuple[Dict[str, Any], ...]        # candidate join keys
    file_roles: Dict[str, str]                   # path → role
    parser_recommendation: str
    confidence: float
    metadata: Dict[str, Any]
```

`DatasetNode` describes one dataset: role (`sales`, `product`, ...), file
paths, detected columns, file type, and delimiter.

---

## 3. What It Captures

Per PROMPT.md, the graph carries:

- **Join keys** — candidate key columns (`candidate_keys` from discovery).
- **Primary / foreign keys** — surfaced through `relationships`
  (source → target) derived from `suggested_joins` and `candidate_keys`.
- **Hierarchy** — parent → child record type mapping for multiline files.
- **Record types** — `metadata["record_types"]` (e.g. `["H", "D", "T"]`).
- **Metadata sections** — `metadata["file_type"]`, `file_architecture`,
  `delimiter`, `encoding`.
- **Layout metadata** — `metadata["layout"]` with the fixed-width detail
  layout (or candidate layout fallback), plus header/detail prefixes.
- **Discovery confidence** — `confidence` (0.0–1.0).
- **Parser recommendation** — `parser_recommendation`.

---

## 4. Builder (Dataset Graph Stage)

`dav_tool/pipeline/stages/dataset_graph.py` converts a `DiscoveryResult`
into a `DatasetGraph`:

| Helper | Produces |
|--------|----------|
| `_build_nodes` | Primary (sales) node + optional product-master node |
| `_build_relationships` | Join candidates from `suggested_joins` + `candidate_keys` |
| `_build_hierarchy` | Parent → child mapping (trailers excluded) |
| `_build_file_roles` | Path → role map |
| `_build_record_types` | Record type prefixes (multiline / fixed-width / header+detail) |
| `_build_layout` | Fixed-width layout metadata |

The stage requires a `DiscoveryResult`; without one it raises
`FatalStageError` ("Discovery has not completed.").

---

## 5. Multi-File Relationships

The graph models multiple datasets so multi-file pipelines (Sales + Product
+ Department + Promotion + Store) can be described:

```
Sales ──► Product ──► Department ──► Promotion ──► Store
```

Each dataset becomes a `DatasetNode`; the join key between them is recorded
in `relationships` and consumed by the Transformation Planner as a
`join_operation`. The Transformation Engine performs the joins; the Parser
only parses.

Current implementation models **Sales + Product**. The Product master is
discovered via `DiscoveryResult.product_master_path` and appears as a second
node with `role="product"`.

---

## 6. Primary Dataset

`DatasetGraph.primary` returns the sales dataset node (or the first node).
It is used by the Transformation Planner to build column normalization hints
and by downstream stages to address the primary input.

---

## 7. Consistency Rules

- The graph is frozen — nothing downstream can mutate it.
- Trailer record types are **excluded** from the hierarchy (they are removal
  targets, not children).
- Flat delimited files produce an empty `record_types` and empty `hierarchy`.
- Confidence is carried from discovery, never computed in the graph.

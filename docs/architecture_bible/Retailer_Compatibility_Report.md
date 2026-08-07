# Retailer Compatibility Report

**Status:** Sprint 3 deliverable — one architecture, four retailers

---

## 1. Principle

> Every retailer must use exactly the same architecture.
> Only Discovery and TransformationPlan should differ.

All four retailer scenarios share the identical stage chain
(Connection → Discovery → Dataset Graph → Planner → Engine → Parser →
Canonical → Aggregation → Validation → Reporting). The differences are
confined to what Discovery detects and what the Planner plans.

---

## 2. Retailer Matrix

| Retailer | Shape | Pipeline | Discovery signals | Plan produced |
|----------|-------|----------|-------------------|---------------|
| Retailer 1 | Delimited + weight | `standard_delimited` | delimiter, columns, quantity column | header_removal (if disclaimers), normalization hints |
| Retailer 2 | Fixed width | `fixed_width` | header_prefix, detail layout, detail prefixes | parent_replication, child_expansion, layout via discovery |
| Retailer 3 | Record based (HEB) | `record_based` | ml_record_types H/D/T, trailer T | flatten_hierarchy, trailer_removal |
| Retailer 4 | Simple delimited, Sales + Product | `sales_product` | delimiter + product_master_path | join_operations (UPC ↔ UPC) |

Common complexities handled by the shared architecture:

- **Sales + Product** — modelled in the DatasetGraph; joined by the Engine.
- **Header/Data with different delimiters** — captured by discovery fields;
  the engine uses the detected delimiter per file.
- **Parent/Child** — `hierarchy` in the graph → flatten op in the plan.
- **Header/Trailer** — parent_replication + trailer_removal.
- **Mixed quantity** — resolved downstream in the Canonical/quantity layer.
- **Metadata blocks** — `metadata_removal` in the plan.
- **Disclaimer blocks** — `header_removal` in the plan.
- **Blank lines** — skipped by the reusable chunk readers.

---

## 3. What Differs Per Retailer

Only two artifacts differ:

1. **Discovery** — which file type, record types, layouts, and relationships
   are detected.
2. **TransformationPlan** — which operations are planned.

Everything downstream (Parser → Canonical → Aggregation → Validation →
Reporting) is retailer-agnostic and consumes contracts only.

---

## 4. Sales + Product (Multi-file)

The DatasetGraph models the Sales → Product relationship:

```
DatasetNode(role="sales",    file_paths=[sales.csv])
DatasetNode(role="product",  file_paths=[product_master_path])
relationships: [{"source": "UPC", "target": "UPC"}]
```

The Planner converts the relationship into a `join_operation`; the Engine
performs a left-join, adding product attributes (e.g. `Brand`) to the sales
rows. The Parser only parses.

Future datasets (Department, Promotion, Store) follow the same pattern:
add a node + relationship; the Engine performs the join.

---

## 5. Coverage Verification

`docs/architecture_bible/Retailer_Coverage.md` tracks retailer scenarios.
Sprint 3 adds `sales_product` as a first-class pipeline and proves the
record-based (HEB) flow end-to-end without UI input.

Full suite: **314 passed** (`tests/`, excluding `tests/e2e`).

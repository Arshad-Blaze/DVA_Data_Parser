# Architecture Readiness Report

Final assessment of the DVA Platform against the intended architecture, with scores and
explicit answers to the 8 closing questions.

---

## Architecture Scores

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **Overall Architecture** | **58 / 100** | Solid pipeline skeleton and rich parsing/detection engines, but the declared workflow abstraction is bypassed and several declared capabilities are missing. |
| **Layer Separation** | 65 / 100 | UI owns the state machine (C1); Config→Detection re-run (H1); Parser→join (M11). Resolved this sprint: UI→ParserFactory bypass (H2), Validation→Reports (H5), Reports→Aggregation fallback (H6). UI now calls `bootstrap()` at startup and reads the `WorkflowEngine` via the presentation-layer accessor `ui/platform.py`; onboarding phases are aligned 1:1 with `WorkflowPhase`. |
| **Frontend/Backend Integration** | 55 / 100 | Clean `OutputResult`/`CanonicalDataset` contracts, but direct backend calls from UI, KPI label mismatch (H9), TEST-side summary dropped (H10), duplicate mapping UIs (M3), hand-rolled caching (M17). `autoparse_context` now routes through `workflow.parsing.parse_from_discovery`. |
| **Discovery** | 75 / 100 | Strong heuristic engine (delimiter/encoding/header/trailer/record-types/fixed-width/multiline/relationships/layouts/confidence). Penalized by re-detection in Config (H1), repeated scans (M9), empty columns for multiline (M10). |
| **Parser** | 65 / 100 | Both a fast engine (`_parsers.py`) and a rich parser package work well for delimited/fixed-width/parent-child. Penalized by in-memory HEB (H4), Excel inconsistency (H12), headerless unsupported (M16), dead FlattenEngine (L1). |
| **Canonical** | 70 / 100 | Normalization, mapping, quantity resolution, weight→lb and metadata are implemented and enforced on the main path. Penalized by the `from_discovery` divergence (C2), `schema_template` not forwarded (M1), dead `CanonicalSchema` (M2). |
| **Validation** | 50 / 100 | Store/item comparison and summary logic exist, but no tolerance thresholds, no duplicate-UPC / missing-UPC checks (H3), store-list compare ignored in existing flow (H8), inert flags (M8). H5 (Validation→Reports) resolved via workflow orchestration. |
| **Reporting** | 50 / 100 | CSV + summary sheets + downloads are solid, but there is **no Excel generation** (H7), KPI label mismatch renders 0s (H9), TEST-side sheets dropped (H10). H6 (re-aggregation fallback) resolved — precomputed summaries required. |
| **Retailer Coverage** | 65 / 100 | Retailers 1–3 and most format variants certified and working end-to-end. Retailer 4 (Sales + Product) is unreachable (H11); mixed-quantity only unit-tested; Excel partial (H12). |
| **Maintainability** | 55 / 100 | Heavy dead code (L1–L18), duplicated logic (M12), god modules (`ui/helpers.py` ~1070 lines, `detection.py` ~1504, `_parsers.py` ~759). On the plus side: focused packages, lazy imports, no hard circular imports. |
| **Production Readiness** | 50 / 100 | No tolerance rules, HEB parsing not scalable past memory, no Excel output, KPI panel shows zeros, Sales+Product unsupported, detection re-runs on large files. |

---

## Explicit Answers to the Final Questions

### 1. Is the architecture correct?

**Partially — the declared architecture is not what runs.** The declared 7-phase
workflow with a `WorkflowState` and a strict UI→Workflow→Operations→Canonical→Validation
→Reports separation is never actually executed as declared. In practice the UI owns the
state machine (`ctx.phase` ints), calls the `ParserFactory` directly, and drives every
phase. The intended pipeline (detect once → parse → canonicalize → aggregate → validate →
report) is real and matches the actual data path for the delimited local flow, but
several stages re-run or bypass abstractions. It is best described as a **correct
pipeline wrapped in an unenforced, partially bypassed architecture**.

### 2. Is the frontend performing any backend responsibilities?

**Yes, substantially.** The UI:
- calls `default_factory.create(discovery).parse(...)` directly instead of a workflow
  parse service (`ui/helpers.autoparse_context`) — **resolved this sprint (H2):** now
  routed through `workflow.parsing.parse_from_discovery`,
- mutates workflow phase numbers directly (~2,000+ lines across onboarding/existing) —
  onboarding phase ints now match `WorkflowPhase`; the `WorkflowState` driver migration (C1)
  is still pending,
- re-runs aggregation (store/item) when mappings change,
- reads source files directly for local previews,
- performs column validation and detection-triggering inside page code.

### 3. Is the backend dependent on UI logic?

**No, with one exception.** The backend packages do not import Streamlit for behavior —
except `workflow/flush.py`, which imports Streamlit (guarded) for the temp-file flush.
`workflow/output.py` does not import Streamlit (it returns serializable results), and
parsers/operations/validation are UI-free. The dependency is effectively one-directional
(UI → backend), which is the correct direction.

### 4. Does every layer have a single responsibility?

**No.** Violations:
- Config (`config_builder.py`) performs detection.
- Validation (`workflow/validation.py`) performs report generation.
- Reports (`_reports.generate_file_review`) perform aggregation when summaries are absent.
- `SalesProductParser` performs a join (an aggregation/relationship concern).
- UI combines rendering + workflow state + parser invocation + column validation.
- `ui/helpers.py` is a ~1,070-line multi-responsibility grab-bag.

Progress this sprint: parser invocation moved out of the UI (H2), and the UI now bootstraps
the platform once and reads the engine from the ServiceRegistry via `ui/platform.py`.

### 5. Can every retailer be handled through parser implementations alone?

**Not today.** Retailers 1–3 (delimited, fixed-width, HEB record-based) and all format
variants are handled by parsers. Retailer 4 (Sales + Product) **cannot** be reached
through the normal flow because discovery never sets `product_master_path`, the parser is
never recommended by the UI, and the enrichment join lives inside the parser rather than
a separate aggregation/relationship stage. Mixed-quantity and Excel are also partial
(unit-tested / unrecommended respectively).

### 6. Is the platform truly retailer-agnostic?

**Mostly, yes — with caveats.** The platform treats retailers as file-format scenarios:
any format that resolves through detection → parser → canonicalization → aggregation →
validation works identically. The caveats: (a) two canonical entry paths behave
differently (one skips normalization), (b) the canonical names `Store`/`UPC`/`Units`/
`Totalprice` are **hard-coded** rather than schema-driven, (c) KPI labels are
hard-coded "Prod"/"Test", (d) the `sales_product` scenario is not retailer-agnostic at
all (unreachable), and (e) category aggregation is really product-description grouping.

### 7. Are there any architectural bottlenecks?

Yes, four are structural:
1. **Single Streamlit process + in-memory RecordTree for HEB** — 500 MB+ HEB files will
   exceed memory.
2. **UI-as-state-machine** — every new workflow step requires UI edits; the declared
   workflow layer cannot enforce invariants.
3. **Repeated detection/parsing** — config re-detects; file-review fallback re-parses;
   on multi-hundred-MB files this is repeated full I/O.
4. **One page driving two full workflows** — Onboarding and Existing are two parallel
   implementations of the same spine, so fixes must be applied twice.

### 8. What would you redesign before calling this Production Ready?

Ranked:
1. **Introduce a real workflow state machine** — a `Workflow` service that owns phase
   transitions; UI only calls `advance()`/`goto()`; remove `ctx.phase` mutation from UI
   code (C1). **Started:** UI now calls `bootstrap()` and reads the `WorkflowEngine`;
   onboarding phase ints already equal `WorkflowPhase` values, so `WorkflowState` can take
   over onboarding rendering without changes. Existing's 9-phase scheme needs a mapping to
   the 7 `WorkflowPhase` values first.
2. **Unify canonicalization** — drop `from_discovery` or route it through the same
   normalizer; forward `schema_template`; delete the dead `CanonicalSchema` (C2/M1/M2).
3. **Make HEB parsing streaming** — replace the in-memory RecordTree with a chunked
   engine path, honoring `ParseOptions.chunk_size` and the detected encoding (H4/M15).
4. **Consume Discovery once** — have `build_config` consume the full `DiscoveryResult`
   (including encoding) and stop re-detecting in Config (H1/M9).
5. **Add the missing business rules** — tolerance thresholds, duplicate-UPC and
   missing-UPC validation; wire `ValidationOptions.run_summary` (H3/M8).
6. **Fix Reporting** — add Excel generation, align KPI labels (`prod_label`/`test_label`)
   and the `Total Time` key, pass TEST-side summaries, remove the re-aggregation fallback
   (H7/H9/H10/H6).
7. **Make Sales + Product real** — add a discovery signal + UI product-master input,
   certified fixture, and move the join to `RelationshipEngine` (H11/M11).
8. **Resolve the Excel inconsistency** — align `recommend_parser` and
   `config_validator` with detection's `"excel"` file_type (H12).
9. **Consolidate the two workflows** — share the orchestration spine between Onboarding
   and Existing (M3/M12).
10. **Decommission dead code** — remove `flatten.py` FlattenEngine, `layout_registry.py`,
    unused stage builders, dormant observability metrics, etc. (L1–L18) to cut the
    maintainability burden and remove misleading signals from new developers.

---

## Verdict

The platform has a strong parsing/detection core and a mostly-sound data path, and the
majority of certified retailer scenarios work end-to-end today. However, it is **not yet
Production Ready**: the workflow layer is bypassed by the UI, HEB parsing is not
scalable, key validation rules and Excel output are missing, and reported KPIs are
incorrectly rendered. The redesign items above — especially the workflow state machine,
streaming HEB, discovery-consume-once, and reporting corrections — should be completed
before production sign-off.

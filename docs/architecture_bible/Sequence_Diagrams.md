# Sequence Diagrams

Detailed Mermaid sequence diagrams for every Phase-15 interaction, traced from the
actual implementation.

Legend: `ctx` = `ProcessingContext` / `ExistingContext`; actor names match the real
modules. "SIDE" = the store side (Onboarding) or the BAU/TEST pair (Existing).

---

## 1. Application Startup

```mermaid
sequenceDiagram
    participant User
    participant CLI as dav_tool CLI
    participant Main as dav_tool.__main__.main
    participant Streamlit
    participant App as ui/app.py main()
    participant Boot as pipeline/bootstrap
    participant Session as st.session_state

    User->>CLI: `dav-tool` or `python -m dav_tool`
    CLI->>Main: execute()
    Main->>Main: rewrite sys.argv to <br/>["streamlit","run", UI_PATH]
    Main->>Streamlit: os.execvp("streamlit", argv)
    Streamlit->>App: run script ui/app.py (top-to-bottom)
    App->>Boot: ensure_bootstrap()
    Boot->>Boot: register standard pipelines + workflow engine
    App->>Session: init page key = "onboarding"
    App->>Session: init ctx = ProcessingContext(), config, metrics, observability
    alt page == "onboarding"
        App->>onboarding.render: ctx
    else page == "existing"
        App->>existing.render: ctx
    else page == "certification_suite"
        App->>certification_suite.render: None
    end
```

Notes:
- Pipeline bootstrap (standard pipelines + workflow engine) runs at app
  startup via `dav_tool/pipeline/bootstrap.py` (see `Application_Bootstrap.md`).
- Logging/metrics/observability are initialized **inside** the session context object
  (ProcessingContext), not at app import time.

---

## 2. Onboarding Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant P as ui/onboarding.py
    participant CM as ui/connection_manager.py
    participant Detect as detection.py
    participant Factory as parser.default_factory
    participant W as workflow.parsing.parse_from_options
    participant Op as OperationExecutor
    participant Val as workflow.validation
    participant Out as workflow.output

    U->>P: page onboarding (source = local / sftp)
    P->>CM: connect_remote / load local
    P->>P: set ctx.file_paths
    P->>Detect: detect_file_type, detect_encoding, has_header
    P->>Detect: auto_detect columns (safe_read_csv head)
    P->>CM: create DiscoveryResult (file_type, delimiter, encoding, columns)
    P->>P: store discovery in session (invalidate previous previews)

    Note over P,Factory: "Parse & Continue" / multiline branch
    P->>Factory: default_factory.create(discovery).parse(...)
    Factory-->>P: ParsedDataset
    P->>W: parse_from_options(parsed, options)
    W->>W: Build CanonicalDataset.from_parse_options
    W-->>P: CanonicalDataset (column_mapping_df, dataset, store_agg, item_agg)

    P->>P: mapping UI (assign Name / ignore / merge)
    P->>Op: store_aggregation / item_aggregation (recompute)
    P->>Val: run_validation(prod=ctx)
    Val-->>P: ValidationResult (store compare, summary, file review)
    P->>Out: generate_onboarding_output(ctx)
    Out-->>P: OutputResult (CSV strings + summary sheets)
    P->>U: st.download_button for upc_summary_csv, file_review_csv
```

---

## 3. Existing Workflow (Format Change)

```mermaid
sequenceDiagram
    participant U as User
    participant P as ui/existing.py
    participant CM as ui/connection_manager.py
    participant Detect as detection.py
    participant Factory as parser.default_factory
    participant Ctx as ExistingContext
    participant Op as OperationExecutor
    participant Val as workflow.validation
    participant Out as workflow.output

    U->>P: page existing (BAU file + TEST file)
    P->>CM: _cm_bau_discovery / _cm_test_discovery (reads only — never written)
    P->>Detect: auto_detect for BAU and TEST (per-file discovery)
    P->>P: build ctx (phase=1)
    P->>P: full path selection (remote/global/local)

    loop both sides
        P->>Factory: create(discovery).parse(parsed_options)
        Factory-->>P: ParsedDataset
        P->>P: canonicalize via workflow.parsing.parse_from_options
        P->>Op: store_aggregation, item_aggregation
    end

    P->>Val: compare_store_summary / run_validation both
    Val-->>P: ValidationResult (store_df, comparison_df, summary, file reviews)
    P->>Out: generate_existing_output(ctx)
    Out-->>P: OutputResult (BAU+TEST CSVs, migration report JSON)
    P->>U: downloads (store_df_csv, comparison_df_csv, summary, fr_prod, fr_test, migration JSON)
```

---

## 4. Discovery

```mermaid
sequenceDiagram
    participant UI as UI caller
    participant D as detection.py
    participant R as DiscoveryResult
    participant Rec as parser.recommend_parser

    UI->>D: detect_file_type(path, datasource)
    D->>D: read first chunk; headerless guess
    D-->>UI: "delimited" | "fixed_width" | "excel" | "multiline"
    UI->>D: detect_encoding(path)
    D-->>UI: "cp1252" | "utf-8"
    UI->>D: delimiter scoring (comma/tab/semicolon/caret/pipe)
    D-->>UI: delimiter + has_header
    UI->>D: detect_trailer_prefix / detect_hdr_prefix / detect_record_types
    UI->>D: detect_record_length + detect_candidate_layout (fixed width)
    UI->>D: is_multiline_record + detect_multiline_record_types (HEB)
    UI->>R: assemble DiscoveryResult(32 fields)
    R-->>UI: discovery
    UI->>Rec: recommend_parser(discovery)
    Rec-->>UI: recommended_parser ("delimited"|"fixed_width"|"multiline"|"record_based"|"sales_product")
    UI->>UI: store discovery in ctx.session / _discovery cache
```

---

## 5. Parser Selection

```mermaid
sequenceDiagram
    participant UI as UI / workflow
    participant F as parser.default_factory
    participant R as recommend_parser
    participant P as Concrete Parser

    UI->>F: default_factory.create(discovery)
    F->>R: recommend_parser(discovery)
    R->>R: decision tree over discovery hints
    alt discovery.file_type == "multiline"
        R-->>F: "record_based"
        F->>P: RecordBasedParser
    else layout present and fixed_width
        R-->>F: "fixed_width"
        F->>P: FixedWidthParser
    else sales_product or product_master_path
        R-->>F: "sales_product"
        F->>P: SalesProductParser
    else header_prefix + detail_layout
        R-->>F: "parent_child"
        F->>P: ParentChildParser
    else
        R-->>F: "delimited"
        F->>P: DelimitedParser
    end
    P-->>UI: ParsedDataset
```

---

## 6. Record-Based Parsing (HEB)

```mermaid
sequenceDiagram
    participant P as RecordBasedParser
    participant F as File (open)
    participant Tree as RecordTree
    participant C as canonical_chunk_stream (engine path) OR in-memory flatten

    P->>F: _open() (hardcoded utf-8)
    P->>P: build tree from file_paths[0]
    Note over P,Tree: parent keys: HDR; detail keys: S/U; boundary: T (trailer)
    P->>Tree: add_record(row) for each line
    Tree-->>P: RecordTree
    P->>P: flatten tree → details list
    P-->>UI: ParsedDataset (raw columns: S/U fields)
```

Intended architecture vs implementation:
- **Intended:** chunked streaming flatten then canonicalization.
- **Actual:** full file → Python RecordTree → list → DataFrame (in-memory); only
  `file_paths[0]` is parsed; encoding is hardcoded utf-8 (app default is cp1252).

---

## 7. Canonical Mapping

```mermaid
sequenceDiagram
    participant UI as UI / workflow
    participant CD as CanonicalDataset
    participant Map as column mapping (config)
    participant Norm as _normalizer / normalize()
    participant Op as OperationExecutor

    UI->>CD: parse_from_options(parsed, options)
    CD->>CD: build column_mapping_df (Name/Ignore/Merge + suggested mapping)
    CD->>Map: apply mapping (rename, ignore, merge, custom)
    CD->>CD: canonical name resolution
    CD->>CD: dataset.polish (canonical cols, uppercase, numeric strings, enums)
    CD->>CD: expose(): normalizer + chunked scan (local)
    CD-->>UI: CanonicalDataset (dataset, store_agg, item_agg, column_mapping_df)

    alt column mapping edited in UI
        UI->>Map: updated mapping (assign / ignore / merge)
        UI->>Op: store_aggregation / item_aggregation re-run
    end
```

Divergence note: the parser-driven path `from_discovery` streams raw parser output and
**does not apply** the canonical normalization/renaming that `from_parse_options`
applies.

---

## 8. Validation

```mermaid
sequenceDiagram
    participant P as UI
    participant V as workflow.validation
    participant Calc as calculations.core
    participant Report as _reports.generate_file_review
    participant Out as OutputResult

    P->>V: run_validation(prod=..., test=...)
    V->>Calc: compare_store_summary (missing → ±100%)
    V->>Calc: compare_item_summary (join on UPC + description)
    V->>Report: generate_file_review (precomputed store_agg + upc_summary)
    Report-->>V: file_review_df
    V->>V: compare summary (Presence counts, growth rates)
    V-->>P: ValidationResult (store_df, comparison_df, summary, file_review)
    P->>Out: store_validation_summary worksheet (Units Variance %, Sales Variance %)
```

Layer-violation note: Validation invokes Report generation directly (crosses the
Validation → Reports boundary).

---

## 9. Report Generation & Downloads

```mermaid
sequenceDiagram
    participant P as UI
    participant O as workflow.output
    participant S as _reports.generate_summary_analytics
    participant H as ui/helpers

    P->>O: generate_onboarding_output(ctx) / generate_existing_output(ctx)
    O->>O: assemble OutputResult (CSV strings via df.write_csv)
    O->>S: generate_summary_sheets(store_agg, upc_summary, prod_label, test_label)
    S-->>O: summary_kpis (Store Count (Prod), Total Sales (Prod), ...)
    O->>O: top/bottom stores/UPCs, top brands, category summary, store validation
    O-->>P: OutputResult (all CSV strings + sheet frames)
    P->>H: _display_summary_sheets + display_execution_summary
    H->>H: render st.metric KPIs (reads {side_label} keys — see gap H9)
    P->>P: st.download_button(label, data=csv, file_name="*.csv")
```

---

## 10. Frontend ↔ Backend Communication

```mermaid
sequenceDiagram
    participant UI as Streamlit pages
    participant SS as st.session_state
    participant Backend as workflow/operations/validation/output
    participant Parser as parser.*
    participant Cache as hand-rolled caches (id(source) keys)

    UI->>SS: read/write ctx.phase, config, session
    UI->>Backend: direct service calls (parse_from_options, aggregate, validate, output)
    Backend->>Parser: create(discovery).parse(...) (via UI bypass, gap H2)
    Parser-->>Backend: ParsedDataset
    Backend-->>UI: CanonicalDataset / OutputResult / ValidationResult
    UI->>Cache: preview caches keyed by id(source) (no st.cache_data)
    UI->>UI: navigation via page radio; progress via st.progress + metrics
```

Communication contract summary:
- **Data contracts:** `DiscoveryResult` → `ParsedDataset` → `CanonicalDataset` →
  `OutputResult`; session-level `ProcessingContext` / `ExistingContext`.
- **Caching:** hand-rolled per-session dicts; no `st.cache_data`/`st.cache_resource`.
- **Progress:** phase numbers + `st.progress`; execution metrics written to
  `ctx.session` and rendered by `display_execution_summary`.

---

## 11. Data Pipeline (Sprint 3) — Full Chain

The new data-centric pipeline (`dav_tool/pipeline/`). Every standard pipeline
shares this exact chain; only Discovery and the TransformationPlan differ.

```mermaid
sequenceDiagram
    participant App as ui/app.py
    participant Boot as pipeline/bootstrap
    participant Reg as pipeline/registry
    participant Eng as WorkflowEngine
    participant Con as ConnectionStage
    participant Disc as DiscoveryStage
    participant G as DatasetGraphStage
    participant Plan as TransformationPlanningStage
    participant T as TransformationEngineStage
    participant Par as ParserPipelineStage
    participant Can as CanonicalDatasetStage
    participant Agg as AggregationStage
    participant Val as ValidationStage
    participant Rep as ReportingStage

    App->>Boot: ensure_bootstrap()
    Boot->>Reg: register_standard_pipelines(reg, full=True)
    App->>Eng: get_workflow_engine()
    App->>Eng: engine.run(ctx)
    Eng->>Con: run(ctx)
    Con-->>Eng: ctx.connection (ConnectionResult)
    Eng->>Disc: run(ctx)
    Disc-->>Eng: ctx.discovery (DiscoveryResult)
    Eng->>G: run(ctx)
    G-->>Eng: ctx.graph (DatasetGraph: nodes, relationships, hierarchy, record_types, layout)
    Eng->>Plan: run(ctx)
    Plan-->>Eng: ctx.plan (TransformationPlan: flatten/join/removal ops)
    Eng->>T: run(ctx)
    T-->>Eng: ctx.transformed (TransformedDataset: reshaped records)
    Eng->>Par: run(ctx) with transformed=ctx.transformed
    Par-->>Eng: ctx.parsed (ParsedDataset)
    Eng->>Can: run(ctx)
    Can-->>Eng: ctx.canonical (CanonicalDataset)
    Eng->>Agg: run(ctx)
    Agg-->>Eng: ctx.aggregated (AggregatedDataset)
    Eng->>Val: run(ctx)
    Val-->>Eng: ctx.validation (ValidationDataset)
    Eng->>Rep: run(ctx)
    Rep-->>Eng: ctx.report (ReportDataset)
    Eng-->>App: PipelineRun (stages_completed, metrics)
```

Notes:
- The engine only orchestrates; every stage owns its business logic.
- Fatal stage failures stop the run; recoverable transformation failures
  (missing product master, missing join key, flatten errors) become
  `TransformedDataset.warnings` and the pipeline continues.
- All five standard pipelines (`standard_delimited`, `fixed_width`,
  `record_based`, `sales_product`, `excel`) share this chain via
  `standard_pipelines.py::_base_stages`.

---

## 12. HEB Record-Based Flow (Sprint 3)

Replaces the rejected `Discovery → UI → Flatten → Parser` flow. Zero manual
interaction — the user is never asked for a record prefix, flatten toggle,
hierarchy, or parser type.

```mermaid
sequenceDiagram
    participant User
    participant UI as ui/app.py
    participant Disc as Discovery
    participant G as DatasetGraph
    participant Plan as TransformationPlanner
    participant T as TransformationEngine
    participant P as RecordBasedParser
    participant CD as CanonicalDataset

    User->>UI: select H|D|T file
    UI->>Disc: detect_file(paths)
    Disc-->>UI: DiscoveryResult (multiline, ml_record_types=[H,D,T], trailer=T)
    UI->>G: build graph
    G-->>UI: DatasetGraph (hierarchy={H:D}, record_types=[H,D,T])
    UI->>Plan: build plan
    Plan-->>UI: TransformationPlan (flatten_hierarchy, trailer_removal=[T])
    UI->>T: execute(discovery, plan)
    T->>T: flatten_multiline_chunks(parent=H, children=[D])
    T-->>UI: TransformedDataset (2 detail rows, ops=(flatten_hierarchy,))
    UI->>P: parse(discovery, transformed=ctx.transformed)
    P-->>UI: ParsedDataset (transformed: True)
    UI->>CD: canonicalize(parsed)
    CD-->>UI: CanonicalDataset
    UI->>UI: display Discovery Summary → Transformation Summary → Parsed Preview → Canonical Preview → Mapping → Validation
```

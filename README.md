# DAV Tool — Data Analysis & Validation Tool

DAV Tool compares retail/POS data files (BAU vs Test) to find differences in sales, units, and store coverage. It handles **plain CSV**, **fixed-width text**, **multi-line HDR-format** files (with optional trailer line support), and **configuration-driven parsing** — all with streaming, no database or intermediate files.

---

## For Non-Technical Users

### What it does
- Upload two sets of sales data (your current file and a new/test file)
- Pick which columns hold store numbers, UPCs, descriptions, units, and prices
- Run validations to see:
  - **Store-level comparison** — which stores differ in units/dollars, and by how much
  - **Item-level comparison** — which UPCs differ between the two files
  - **Store list compare** — stores present in one file but missing from the other
  - **File review report** — per-file summary of store count, UPC count, units, and dollars

### Supported file formats
| Format | Description |
|---|---|
| **Delimited** | CSV, pipe-delimited, tab-delimited, semicolon (auto-detected) |
| **Fixed-width** | Columns at fixed character positions (requires a layout CSV) |
| **Multi-line HDR (delimited)** | POS data with record-type prefixes (e.g. `H\|store\|date`, `D\|upc\|desc\|units\|price`) |
| **Multi-line HDR (fixed-width)** | POS data with multi-character header prefix (e.g. `HDR`) followed by fixed-width records; requires **two** layout CSVs (header + detail) |
| **HDR + Trailer** | Extends HDR fixed-width with optional TRL (trailer) lines — TRL lines act as transaction boundaries; trailer fields attached to each detail row |
| **Config-driven** | Load all parsing settings from a single JSON config file — bypasses manual setup for repeatable onboarding |

### How to run

```bash
# Option 1 — via pip-installed CLI (after pip install)
dav-tool

# Option 2 — via python module
python -m dav_tool

# Option 3 — direct streamlit
streamlit run dav_tool/ui/app.py
```

### Before you run: get input specs from your data team
DAV Tool needs to know the structure of your files before it can process them. Before running, confirm with your data team:
- **Layout CSV** for any fixed-width file (column positions)
- **Header + Detail layout CSVs** for HDR fixed-width files (separate layouts for header and detail records)
- **Trailer layout CSV** for HDR files with trailer lines (optional — attaches trailer fields to detail rows)
- **Delimiter** for delimited files (comma, pipe, tab, semicolon)
- **Record-type prefixes** for multiline files (e.g. `H`, `D`, `U`)
- **Column mapping** — which columns hold Store, UPC, Description, Units, Price
- **Implied decimals** — whether `9999` means `99.99` (divide by 100)
- **Price type** — Total Price or Unit Price (multiplied by units sold)

> **Pro tip:** Once configured, save your settings as a **Format Config** (JSON) file. Next time you run the tool, load the config to skip the entire setup flow — just point to your folder and go.

---

## For Technical Users

### Installation

```bash
pip install dav-tool
```

Or install from source:

```bash
git clone <repo-url>
cd DVA_Data_Parser
pip install .
```

No additional setup required — just run `dav-tool`.

### Docker

```bash
docker build -t dav-tool .
docker run -p 8501:8501 dav-tool
```

Open `http://localhost:8501` in your browser.

### Project structure

```
dav_tool/
├── _parsers.py          Raw file I/O: fixed-width, delimited, multiline flattening
├── _aggregators.py      Streaming aggregations: store, item, UPC, file review
├── _normalizer.py       Canonical column normalisation
├── _reports.py          File review report generation
├── _observability.py    Metrics, timers, and logging
├── detection.py         File-type and multiline detection
├── io.py                Safe CSV reader with encoding fallback
├── config.py            Shared constants
├── format_config.py     Config-driven parsing (load/save JSON configs)
├── config_builder.py    Build FormatConfig from detected files
├── config_validator.py  Progressive validation of config completeness
├── processing_context.py Dataclass definitions
├── options.py           ParseOptions, ColumnMapping, AggregationOptions, ValidationOptions
├── datasource/          Data source abstraction (local, SSH/SFTP)
│   ├── base.py          IDataSource interface
│   ├── local.py         LocalDataSource
│   ├── ssh.py           SSHDataSource
│   └── manager.py       ConnectionManager singleton
├── workflow/            Workflow layer (phases, state, discovery, processing, validation)
│   ├── __init__.py      WorkflowPhase enum, WorkflowState, Workflow protocol
│   ├── discovery.py     File detection, preview, DiscoveryResult
│   ├── processing.py    Aggregation orchestration
│   └── validation.py    Validation orchestration
├── validation/
│   ├── store.py         Store-level validation logic
│   └── item.py          Item-level validation logic
└── ui/
    ├── app.py           Streamlit entry point (page dispatch)
    ├── connection_manager.py  Connection Manager UI
    ├── helpers.py       Shared UI helpers (progressive wizard, phase progress)
    ├── onboarding.py    Onboarding page logic
    └── existing.py      Existing/BAU page logic
```

### Key design decisions

- **Polars streaming** (`streaming=True`, chunked generators) — handles files larger than RAM
- **No intermediate files** — data flows directly from source files through aggregators
- **Multiline handling** — record-type prefixes (H, D, U, T) are detected, filtered, and flattened at preview time; user defines column names before schema is applied
- **Schema fix at preview** — users rename generic `Column_N` names before column mapping, avoiding downstream failures
- **Parallel aggregation** — independent aggregation calls (BAU/Test, Store/Item) run concurrently via `ThreadPoolExecutor`, cutting wall-clock time by up to 75%
- **Memory observability** — DataFrame registry tracks live references; peak-memory snapshots and per-phase release logging via `ProcessingMetrics`
- **Config builder** — reads only 100 sample rows to detect encoding, delimiter, schema, data types, and column mapping; config is locked after acceptance, then full dataset is read exactly once
- **Progressive config wizard** — 6 sections (General, File, Schema, Business Rules, Validation, Output) presented one at a time; each must be confirmed before proceeding
- **CM discovery consumption** — Discovery phase reuses Connection Manager's DetectionResult without re-detection
- **Per-side discovery keys** — Existing page stores BAU and Test discoveries separately (`_cm_bau_discovery`, `_cm_test_discovery`)
- **Golden dataset** — 12 parametrized regression tests in `tests/test_golden.py` compare current pipeline output against saved golden CSVs for all formats; regenerate with `python -m tests.golden.generate_golden`

### Running tests

```bash
python -m pytest tests/ -v --ignore=tests/e2e    # 98 unit tests (including golden regression)
python -m pytest tests/e2e -v                     # Playwright E2E tests
python full_test.py                               # integration test
python -m tests.golden.generate_golden            # regenerate golden reference CSVs
```

E2E test benchmark results: [BENCHMARK.md](tests/e2e/BENCHMARK.md)

---

## Workflow Overview

```
=== Current Workflow (7-step) ===
1. Connection — Connect via local filesystem or SSH (Connection Manager)
2. Discovery — File detection, preview, column extraction (reuses CM's result)
3. Configuration — Progressive config wizard (6 sections: General, File, Schema, Business Rules, Validation, Output)
4. Validate Config — Review and accept configuration
5. Processing — Full dataset read, aggregation (Store + Item in parallel)
6. Validation — Run selected validations
7. Reports — Review results and download CSVs

=== Quick start (with pre-saved config file) ===
1. Connect via Connection Manager
2. Select files — DAV Tool detects file type
3. Load saved config JSON — wizard pre-fills all settings
4. Accept configuration
5. Confirm column mapping
6. Run validation
7. Review results

=== Config Builder (sample-based) ===
1. Connect via Connection Manager
2. Select files — DAV Tool detects file type
3. Click "Progressive Configuration" — reads only 100 sample rows
4. Walk through 6 config sections (General, File, Schema, Business Rules, Validation, Output)
5. Accept configuration — config is locked
6. Confirm column mapping and run processing
7. Review results and download CSVs
```

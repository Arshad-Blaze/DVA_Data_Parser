# Flow Samples — Walkthroughs from the UI

---

## Sample 1: Onboarding a Delimited CSV File (Local)

**Scenario:** A retailer sends a pipe-delimited file `retailer_sales_2024-03.csv` with columns `Store|UPC|Description|Units|Price`.

---

### Step 1 — Launch & Connect

```
APP LAUNCH
──────────
User runs:  python -m dav_tool

UI shows:   Streamlit app at localhost:8501
            Connection Manager panel at top
            [Onboarding]  [Existing]  buttons

USER ACTION:
  ┌──────────────────────────────────────────────────────────────┐
  │ Connection Manager                                           │
  │ ○ Local  ● Remote Server                                     │
  │ Host: ______________  Port: ____                             │
  │ Username: ___________  Password: ______                      │
  │ [ Connect ]                                                  │
  │                                                              │
  │ Remote Server: Connected (myhost:22)                         │
  │ ┌──────────────────────────────────────┐                     │
  │ │ /data/retailer_files/                │ ← browsing MFT     │
  │ │   retailer_sales_2024-03.csv         │                     │
  │ │   retailer_sales_2024-04.csv         │                     │
  │ └──────────────────────────────────────┘                     │
  │ [Use This Path]                                              │
  └──────────────────────────────────────────────────────────────┘

  → Connection Manager calls: connect_ssh(host="myhost", ...)
  → datasource/manager.py stores SSHDataSource as _ACTIVE_SOURCE
  → User clicks "Use This Path"
  → st.session_state["_cm_selected_path"] = "/data/retailer_files/"

USER ACTION:
  Clicks [Onboarding]
  → app.py dispatches to onboarding.run()
  → st.session_state.page = "onboarding"
```

---

### Step 2 — Discovery (Phase 1)

```
PHASE 1 — DISCOVERY
────────────────────
UI renders: "Step 2: Discovery — File Detection & Preview"

USER ACTION:
  Pastes path into text input:
  ┌─────────────────────────────────────────────────────────┐
  │ Folder Path: /data/retailer_files/                      │
  └─────────────────────────────────────────────────────────┘

  → helpers.get_file_list(path, source=active_source)
  → SSHDataSource.list_files("/data/retailer_files/")
  → sftp.listdir() → ["retailer_sales_2024-03.csv"]

BACKEND DETECTION (automatic, no user action required):
  ┌─────────────────────────────────────────────────────────┐
  │ detection.is_multiline_record(fp)                       │
  │   → reads 10 lines from remote via source.read_sample() │
  │   → checks: single-letter prefixes? NO                  │
  │              backslash continuations? NO                 │
  │              HDR alpha+digit pattern? NO                 │
  │   → returns False                                       │
  │                                                         │
  │ detection.detect_file_type(fp)                          │
  │   → reads 5 lines                                       │
  │   → scores: comma=0, pipe=120, tab=0, semicolon=0       │
  │   → returns ("delimited", "|")                          │
  │                                                         │
  │ detection.has_header(fp, "|")                           │
  │   → reads 1 line: "Store|UPC|Description|Units|Price"  │
  │   → 5/5 fields have alpha chars → returns True          │
  │                                                         │
  │ config_builder.build_config(fp, ...)                    │
  │   → source.read_sample(fp, n=100) → downloads 100 lines │
  │   → pl.read_csv(n_rows=100, separator="|")              │
  │   → infers columns and data types                       │
  │   → smart_column_indices finds:                         │
  │       Store → index 0                                   │
  │       UPC → index 1                                     │
  │       Description → index 2                              │
  │       Units → index 3                                   │
  │       Price → index 4                                   │
  │   → returns FormatConfig with all fields populated      │
  │                                                         │
  │ preview_raw(fp, "delimited", "|", n_rows=20)            │
  │   → reads 20 rows via source.open_stream()              │
  │   → returns DataFrame for display                       │
  └─────────────────────────────────────────────────────────┘

UI SHOWS:
  ✅ Delimited (|)
  ✅ Data Preview (20 rows in a table)
      Store | UPC        | Description       | Units | Price
      1001  | 490123456  | Widget A          | 10    | 49.99
      1001  | 490123457  | Widget B          | 5     | 29.99
      ...

  ✅ Parsing complete — 5 column(s) detected
     [Progressive Configuration →]

USER ACTION:
  Clicks [Progressive Configuration →]
  → ctx.file_paths = ["/data/retailer_files/retailer_sales_2024-03.csv"]
  → ctx.file_type = "delimited"
  → ctx.delimiter = "|"
  → ctx.columns = ["Store", "UPC", "Description", "Units", "Price"]
  → ctx.phase = PHASE_CONFIG
  → st.rerun()
```

---

### Step 3 — Progressive Configuration (Phase 2)

```
PHASE 2 — CONFIGURATION
────────────────────────
UI renders: "Step 3: Configuration"

  → build_config() re-reads sample (100 rows) via remote source
  → returns FormatConfig with detected settings

STAGE A — GENERAL INFORMATION
┌──────────────────────────────────────────────────────────────────┐
│ General Settings                                                 │
│ Configuration Name: [retailer_sales_config___________]           │
│ File Type: [delimited ▼]  Encoding: [cp1252________]            │
│ Has Header: [✅]                                                 │
│                                                                  │
│ [Confirm Stage A]                                                │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Confirm Stage A]
  → cfg.mark_section_complete(GENERAL)

STAGE B — FILE FORMAT
┌──────────────────────────────────────────────────────────────────┐
│ File Format Settings                                             │
│ Delimiter: [| ▼]                                                 │
│ Layout CSV (fixed-width only): [________________]                │
│                                                                  │
│ [Confirm Stage B]                                                │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Confirm Stage B]
  → cfg.mark_section_complete(FILE)

STAGE C — SCHEMA & COLUMNS
┌──────────────────────────────────────────────────────────────────┐
│ Schema & Columns                                                 │
│ Detected: Store, UPC, Description, Units, Price                  │
│                                                                  │
│ Rename columns (optional):                                       │
│   Store → [Store            ]                                    │
│   UPC   → [UPC              ]                                    │
│   Desc  → [Description      ]                                    │
│   Units → [Units            ]                                    │
│   Price → [Price            ]                                    │
│                                                                  │
│ [Confirm Stage C]                                                │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Confirm Stage C]
  → cfg.mark_section_complete(SCHEMA)

STAGE D — BUSINESS RULES
┌──────────────────────────────────────────────────────────────────┐
│ Business Rules                                                   │
│ Store Column:       [Store ▼]                                    │
│ UPC Column:         [UPC ▼]                                      │
│ Description Column: [Description ▼]                              │
│ Units Column:       [Units ▼]                                    │
│ Price Column:       [Price ▼]                                    │
│                                                                  │
│ Price Type:         ● Total Price  ○ Unit Price                   │
│ Implied Dollars:    [ ] (÷100)                                   │
│ Implied Units:      [ ] (÷100)                                   │
│                                                                  │
│ [Confirm Stage D]                                                │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Confirm Stage D]
  → cfg.store_col = "Store", cfg.upc_col = "UPC", ...
  → cfg.mark_section_complete(BUSINESS_RULES)

STAGE E — VALIDATION SETTINGS
┌──────────────────────────────────────────────────────────────────┐
│ Validation Settings                                              │
│ [✅] Store Level Validation                                      │
│ [✅] Item Level Validation                                       │
│ [✅] Compare Store List                                          │
│ [✅] File Review Report                                          │
│                                                                  │
│ [Confirm Stage E]                                                │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Confirm Stage E]
  → cfg.mark_section_complete(VALIDATION)

STAGE F — OUTPUT SETTINGS
┌──────────────────────────────────────────────────────────────────┐
│ Output Settings                                                  │
│ Format: [csv ▼]                                                  │
│ [✅] Include File Review                                         │
│ [✅] Include Validation Details                                  │
│                                                                  │
│ [Confirm Stage F]                                                │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Confirm Stage F]
  → cfg.mark_section_complete(OUTPUT)
  → all 6 sections complete
  → ctx.config_locked = True
  → ctx.store_col = "Store", ctx.upc_col = "UPC", ...
  → ctx.phase = PHASE_CONFIG_VALIDATED
  → st.rerun()
```

---

### Step 4 — Validate Configuration (Phase 3)

```
PHASE 3 — CONFIG VALIDATION
────────────────────────────
UI renders: "Step 4: Validate Configuration"

  → helpers.validate_config_before_processing(cfg, key_prefix="onb")
  → config_validator.validate_config(cfg)
  → checks:
      file_type = "delimited" ✅
      schema = ["Store", "UPC", ...] ✅
      store_col = "Store" ✅
      upc_col = "UPC" ✅
      desc_col = "Description" ✅
      units_col = "Units" ✅
      price_col = "Price" ✅
      all mapped columns exist in schema ✅
  → returns [] (no errors)

UI SHOWS:
  ✅ Configuration is valid
     [Proceed to Processing →]

USER ACTION:
  Clicks [Proceed to Processing →]
  → ctx.phase = PHASE_PROCESSING
  → st.rerun()
```

---

### Step 5 — Processing / Aggregation (Phase 4)

```
PHASE 4 — PROCESSING
─────────────────────
UI renders: "Step 5: Processing"

  → Shows Store List input and Column Selection dropdowns
  → User selects columns (pre-populated from config)

USER ACTION:
  Clicks [Proceed to Processing & Validation →]

BACKEND (parallel via ThreadPoolExecutor):
  ┌─────────────────────────────────────────────────────────────┐
  │ Thread 1: stream_store_aggregate()                         │
  │   file_paths = [remote_path]                                │
  │   file_type = "delimited"                                   │
  │   source = SSHDataSource (supports_direct_path = False)     │
  │                                                             │
  │   → Fast path blocked (remote source)                       │
  │   → Falls to chunked path:                                  │
  │     _iter_chunks() → parse_delimited_chunks(source=ssh)     │
  │       → ssh.open_stream(path) → SFTP file handle            │
  │       → csv.reader reads line by line                       │
  │       → Every 100K rows: yield pl.DataFrame                 │
  │                                                             │
  │     For each chunk:                                         │
  │       apply_column_names() → (no rename needed)             │
  │       normalize_store_chunk():                              │
  │         "Store" → STORE_NUMBER                              │
  │         safe_numeric("Units") → Units (f64)                 │
  │         safe_numeric("Price") → Totalprice (f64)            │
  │       group_by("STORE_NUMBER").sum(["Units", "Totalprice"]) │
  │       append to aggs list                                    │
  │       del chunk; gc.collect()                               │
  │                                                             │
  │     _merge_accumulate(aggs):                                │
  │       → pl.concat(aggs)                                     │
  │       → group_by("STORE_NUMBER").sum()                      │
  │       → return result                                       │
  │                                                             │
  │ Thread 2: stream_item_aggregate()                           │
  │   Same file, same chunked path:                             │
  │     normalize_item_chunk():                                 │
  │       "UPC" → UPC_CODE                                      │
  │       "Description" → PRODUCT_DESCRIPTION                    │
  │       safe_numeric("Units") → UNITS_SOLD                    │
  │       safe_numeric("Price") → TOTAL_DOLLARS                  │
  │     group_by(["UPC_CODE", "PRODUCT_DESCRIPTION"]).sum()     │
  │     _merge_accumulate_item()                                │
  │                                                             │
  │ Timing: ~3.2s for a 500MB file over SSH                     │
  │ Memory: peak ~120MB (never holds full dataset)              │
  └─────────────────────────────────────────────────────────────┘

  → ctx.store_agg = DataFrame(STORE_NUMBER, Units, Totalprice) [50 rows]
  → ctx.item_agg = DataFrame(UPC_CODE, PRODUCT_DESCRIPTION, UNITS_SOLD, TOTAL_DOLLARS) [500 rows]
  → ctx.phase = PHASE_VALIDATION
  → st.rerun()
```

---

### Step 6 — Validation (Phase 5)

```
PHASE 5 — VALIDATION
─────────────────────
UI renders: "Step 6: Validation"
  ┌────────────────────────────────────────────────────────────────┐
  │ Checkboxes:                                                    │
  │  [✅] Compare Store List                                       │
  │  [✅] Generate Unique UPC Summary                              │
  │  [✅] File Review Report                                       │
  │                                                                │
  │ [Validate Onboarding]                                          │
  └────────────────────────────────────────────────────────────────┘

USER ACTION:
  Clicks [Validate Onboarding]

BACKEND:
  ┌──────────────────────────────────────────────────────────────┐
  │ 1. compare_files(ctx.store_agg, ctx.store_agg,              │
  │                  "STORE_NUMBER", "STORE_NUMBER")             │
  │    → compares lowercase store numbers                       │
  │    → returns {"missing_in_test": "", "missing_in_prod": ""} │
  │                                                             │
  │ 2. stream_upc_summary() → UPC-level aggregation             │
  │    → from ctx.item_agg (group_by UPC)                       │
  │    → returns DataFrame(UPC, UNITS_SOLD, TOTAL_DOLLARS)      │
  │                                                             │
  │ 3. generate_file_review(                                    │
  │      precomputed_store_agg=ctx.store_agg,                   │
  │      precomputed_upc_summary=upc_summary)                   │
  │    → NO re-parse — uses already-aggregated data             │
  │    → returns DataFrame:                                     │
  │        filename: retailer_sales_2024-03.csv                 │
  │        store_count: 50                                      │
  │        upc_count: 500                                       │
  │        total_units: 125,000                                 │
  │        total_dollars: $2,450,000.00                         │
  └─────────────────────────────────────────────────────────────┘

UI SHOWS RESULTS:
  Store Comparison: ✅ All stores match
  UPC Summary: 500 unique UPCs, 125,000 units, $2,450,000.00
  File Review: 1 file processed

  [View Reports →]
```

---

### Step 7 — Reports (Phase 6)

```
PHASE 6 — REPORTS
──────────────────
UI renders: "Step 7: Reports"
  ╔══════════════════════════════════════════════════════════════╗
  ║                    Execution Summary                         ║
  ║ Files Processed: 1     Parse Time: 1.2s                     ║
  ║ Rows Processed: 50,000  Agg Time:  2.0s                     ║
  ║ Unique Stores: 50      Val Time:   0.3s                     ║
  ║ Unique UPCs: 500       Total Time: 3.5s                     ║
  ║                        Peak Mem:   120.0 MB                  ║
  ╚══════════════════════════════════════════════════════════════╝

  [Download Store Comparison CSV]
  [Download UPC Summary CSV]
  [Download File Review CSV]

  Processing History (last 10 executions):
    - 2024-03-15 14:32:01 — 1 file, 50,000 rows, 3.5s, 120MB peak

  [Start Over]
```

---

## Sample 2: Onboarding a Multiline HDR Fixed-Width File

**Scenario:** A retailer sends HDR-fixed-width files via SSH. The file has:
- `HDR` lines: header prefix `HDR`, fields: Date(8), Store(4), Invoice(6)
- `DTL` lines: detail prefix `DTL`, fields: UPC(12), Qty(5), Price(7)
- `TRL` lines: trailer prefix `TRL`, fields: RecordCount(6), TotalAmount(10)

Layout CSVs exist locally:
- `header_layout.csv`: from, length, field, type
- `detail_layout.csv`: from, length, field, type
- `trailer_layout.csv`: from, length, field, type

---

### Discovery Phase (What the User Sees)

```
PHASE 1 — DISCOVERY
────────────────────

USER ACTION:
  Connects via SSH, browses to folder, enters folder path.

BACKEND DETECTS:
  is_multiline_record(fp) → True
    (finds HDR lines starting with alpha prefix "HDR")
    (finds DTL lines starting with alpha prefix "DTL")

UI SHOWS:
  ⚠️ Multi-line structured file detected

  ┌──────────────────────────────────────────────────────────┐
  │ Raw Preview (with record-type prefixes)                  │
  │ HDR202403011001000123                                    │
  │ DTL490123456789  00010004999                             │
  │ DTL490123456790  0000502999                              │
  │ TRL00000200001249900                                      │
  │ HDR202403011001000124                                    │
  │ ...                                                      │
  └──────────────────────────────────────────────────────────┘

  HDR prefixes detected: HDR, DTL, TRL

  Header Layout CSV: [/home/user/layouts/header_layout.csv]  [Browse]
  Detail Layout CSV: [/home/user/layouts/detail_layout.csv]  [Browse]
  Trailer Prefix: [TRL]
  Trailer Layout CSV: [/home/user/layouts/trailer_layout.csv]

  [Flatten Records]

USER ACTION:
  Enters paths to layout CSV files, clicks [Flatten Records]

BACKEND:
  load_layout("header_layout.csv")
    → reads CSV, returns [{"field": "Date", "start": 3, "end": 11, "type": "date"},
                          {"field": "Store", "start": 11, "end": 15, "type": "text"},
                          {"field": "Invoice", "start": 15, "end": 21, "type": "text"}]
  load_layout("detail_layout.csv")
    → [{"field": "UPC", "start": 3, "end": 15, "type": "text"},
        {"field": "Qty", "start": 15, "end": 20, "type": "numeric"},
        {"field": "Price", "start": 20, "end": 27, "type": "numeric"}]
  load_layout("trailer_layout.csv")
    → [{"field": "RecordCount", "start": 3, "end": 9, "type": "numeric"},
        {"field": "TotalAmount", "start": 9, "end": 19, "type": "numeric"}]

  ctx.header_prefix = "HDR"
  ctx.header_layout = [...]
  ctx.detail_layout = [...]
  ctx.trailer_prefix = "TRL"
  ctx.trailer_layout = [...]
  ctx.ml_flattened = True

  preview_flattened_multiline_fixed(..., n_rows=10)
    → flatten_multiline_fixed_width() reads 10 rows:
      HDR202403011001000123 → header: Date=2024-03-01, Store=0010, Invoice=000123
      DTL490123456789  00010004999 → detail with header carried forward
      DTL490123456790  0000502999  → detail with header carried forward
      TRL00000200001249900 → trailer flushes buffer, adds RecordCount=2, TotalAmount=12499.00
    → returns DataFrame:
       Date       | Store | Invoice | UPC           | Qty  | Price    | RecordCount | TotalAmount
       2024-03-01 | 0010  | 000123  | 490123456789  | 100  | 499.00   | 2           | 12499.00
       2024-03-01 | 0010  | 000123  | 490123456790  | 50   | 2999.00  | 2           | 12499.00

UI SHOWS:
  ✅ Header layout loaded (3 fields)
  ✅ Detail layout loaded (3 fields)
  ✅ Trailer layout loaded (2 fields)

  Flattened Preview (10 rows):
  Date       | Store | Invoice | UPC           | Qty  | Price
  2024-03-01 | 0010  | 000123  | 490123456789  | 100  | 499.00
  2024-03-01 | 0010  | 000123  | 490123456790  | 50   | 2999.00
  ...

  Define Column Schema:
    Date → [Date]
    Store → [Store]
    UPC → [UPC]
    Qty → [Units]
    Price → [Price]
    Invoice → [Invoice] (optional mapping)

  [Apply Schema]

USER ACTION:
  Renames Qty→Units, Price→Price
  Clicks [Apply Schema]
  → ctx.schema = ["Date", "Store", "Invoice", "UPC", "Units", "Price"]
  → ctx.phase advances through remaining phases same as Sample 1
```

---

## Sample 3: Existing Workflow (Two-Sided Comparison)

**Scenario:** Compare BAU (production) data vs Test (new feed) data. Both local folders contain pipe-delimited files.

### Discovery Phase

```
PHASE 1 — DISCOVERY
────────────────────

UI renders two columns:
┌──────────────────────────┬──────────────────────────┐
│  BAU                     │  Test                    │
│                          │                          │
│ BAU Folder Path:         │ Test Folder Path:        │
│ [/data/bau/         ]    │ [/data/test/         ]   │
│                          │                          │
│ Optional: BAU Config:    │ Optional: Test Config:   │
│ [________________]       │ [________________]       │
│                          │                          │
│ ✅ Delimited (|)         │ ✅ Delimited (|)         │
│ ✅ Header detected       │ ✅ Header detected       │
│                          │                          │
│ Data Preview:            │ Data Preview:            │
│ Store|UPC|...            │ Store|UPC|...            │
│ 1001|490...              │ 1001|490...              │
└──────────────────────────┴──────────────────────────┘

BACKEND (per side, same as Onboarding):
  → get_file_list() for each path
  → detect_file_type() → ("delimited", "|")
  → has_header() → True
  → get_column_names() → ["Store", "UPC", "Description", "Units", "Price"]

USER ACTION:
  Clicks [Progressive Configuration →]
  → ctx.phase = PHASE_CONFIG
```

### Configuration (Sequential)

```
PHASE 2 — CONFIGURATION
────────────────────────

FIRST: BAU Configuration (same 6-stage wizard as Onboarding Sample 1)

UI SHOWS:
  ┌─────────────────────────────────────────────────────────┐
  │  BAU Configuration                                      │
  │  [Stage A General] [Stage B File] ... [Stage F Output]  │
  │  → User completes all 6 stages                          │
  │  ✅ BAU Configuration complete                          │
  └─────────────────────────────────────────────────────────┘

THEN: Test Configuration (same 6-stage wizard)

UI SHOWS:
  ┌─────────────────────────────────────────────────────────┐
  │  Test Configuration                                     │
  │  [Stage A General] [Stage B File] ... [Stage F Output]  │
  │  → User completes all 6 stages                          │
  │  ✅ Test Configuration complete                         │
  └─────────────────────────────────────────────────────────┘

  → ctx.prod.config_locked = True
  → ctx.test.config_locked = True
  → ctx.phase = PHASE_CONFIG_VALIDATED
```

### Validate Config (Phase 3)

```
PHASE 3 — CONFIG VALIDATION
────────────────────────────

BACKEND:
  validate_config(prod_cfg) → [] (valid)
  validate_config(test_cfg) → [] (valid)

UI SHOWS:
  ✅ BAU Configuration: Valid
  ✅ Test Configuration: Valid
  [Proceed to Processing →]
```

### Processing (Phase 4) — 4 Parallel Jobs

```
PHASE 4 — PROCESSING
─────────────────────

BACKEND: ThreadPoolExecutor(max_workers=4) submits:
  ┌─────────────────────────────────────────────────────────┐
  │ Thread 1: stream_store_aggregate(BAU paths)             │
  │ Thread 2: stream_store_aggregate(Test paths)            │
  │ Thread 3: stream_item_aggregate(BAU paths)              │
  │ Thread 4: stream_item_aggregate(Test paths)             │
  │                                                         │
  │ All 4 run in parallel on local files (fast path):       │
  │   scan_delimited() → pl.LazyFrame                       │
  │   with_columns(normalize_exprs)                         │
  │   group_by().agg(pl.sum())                              │
  │   collect(engine="streaming")                           │
  │                                                         │
  │ Timing: ~1.5s total (all 4 complete)                    │
  └─────────────────────────────────────────────────────────┘

  → ctx.prod.store_agg, ctx.prod.item_agg (DataFrames)
  → ctx.test.store_agg, ctx.test.item_agg (DataFrames)
  → ctx.phase = PHASE_VALIDATION
```

### Validation (Phase 5) — Comparison

```
PHASE 5 — VALIDATION
─────────────────────

BACKEND:
  storelevelvalidation(prod_summary, test_summary)
    → Already have pre-computed summaries
    → Calls store_diffs() from Calculation Engine
    → Full outer join on STORE_NUMBER
    → Computes: Units_Diff, Sales_Diff, Units_Diff_%, Sales_Diff_%

  run_item_validation(bau_summary, test_summary)
    → Already have pre-computed summaries
    → Calls item_comparison() from Calculation Engine
    → Full outer join on (UPC_CODE, PRODUCT_DESCRIPTION)
    → classify_presence() → "Present in Both" / "Only in BAU" / "Only in TEST"
    → Computes: Units Difference, Dollar Difference, Unit %, Dollar %

  generate_file_review(BAU, precomputed=True)
  generate_file_review(Test, precomputed=True)

UI SHOWS:
  ┌─────────────────────────────────────────────────────────┐
  │  Store-Level Validation                                 │
  │  STORE | Units_Prod | Units_Test | Diff | Diff_%       │
  │  0010  | 10,000     | 9,800      | 200  | 2.0%        │
  │  0020  | 5,000      | 5,200      | -200 | -4.0%       │
  │  ...                                                    │
  │                                                         │
  │  Item-Level Validation                                  │
  │  UPC   | BAU Units | Test Units | Diff | Present       │
  │  490.. | 100       | 95         | 5    | Both          │
  │  490.. | 0         | 50         | -50  | Only in TEST  │
  │  ...                                                    │
  │                                                         │
  │  File Review:                                           │
  │  BAU: 1 file, 50 stores, 500 UPCs, 125K units          │
  │  Test: 1 file, 48 stores, 520 UPCs, 128K units         │
  └─────────────────────────────────────────────────────────┘
```

---

## Sample 4: Remote Streaming (SSH) — What Happens Under the Hood

When processing a large file (2GB) over SSH, no local copy is made:

```
USER CONNECTS VIA SSH
  → SSHDataSource.connect() opens paramiko connection
  → st.session_state._ACTIVE_SOURCE = SSHDataSource

DISCOVERY (100 lines only):
  SSHDataSource.read_sample(path, n=100)
    → sftp.open(path) → readlines(100) → close → return str
    → ~5KB transferred

CONFIG BUILD (100 lines):
  Same pattern: read 100 lines, write to local temp file
  → Temp file deleted after detection (_cleanup_sample)

PROCESSING (full file):
  stream_store_aggregate()
    source = SSHDataSource (supports_direct_path = False)
    → chunked path selected

    _iter_chunks():
      → parse_delimited_chunks(file_paths, delimiter, source=ssh_source)
        → ssh_source.open_stream(path) → sftp.open(path, "rb")
        → io.TextIOWrapper(binary_stream, encoding="cp1252")
        → csv.reader(text_stream, delimiter="|")

    For each 100K-row chunk:
      → normalize_store_chunk(chunk)
      → group_by().sum()
      → append to aggs
      → del chunk; gc.collect()

    _merge_accumulate(aggs):
      → pl.concat(aggs)
      → group_by().sum()
      → return result

  MEMORY FOOTPRINT:
    Max per chunk: ~100K rows × 3 columns ≈ ~12MB
    Accumulated aggs: ~50 chunks × ~50 rows ≈ ~500KB
    Total peak: ~15MB + streaming buffer

  NETWORK:
    Sequential read via SFTP channel
    No local file ever created
    ~2GB transferred over network (sequential, not downloaded in bulk)
```

---

## UI State Flow Summary (Session State Transitions)

```
st.session_state.page = "onboarding" | "existing"
st.session_state["_cm_selected_path"] = "..."  (from Connection Manager)

ONBOARDING:
  st.session_state.onb_ctx: ProcessingContext
    .phase = 0 → 1 (Discovery) → 2 (Config) → 3 (Config Validated)
           → 4 (Processing) → 5 (Validation) → 6 (Reports)
    .file_paths, .file_type, .delimiter, ...
    .store_col, .upc_col, ..., .mapping_confirmed
    .store_agg, .item_agg
    .compare_result, .upc_summary, .file_review
    .done = True

EXISTING:
  st.session_state.ex_ctx: ExistingContext
    .phase = 0 → 6
    .prod: ProcessingContext (BAU side)
    .test: ProcessingContext (Test side)
    .store_df, .comparison_df, .summary_df (combined)
```

## Key Design Principle: Streaming Everywhere

| Scenario | Mechanism | Max Memory |
|----------|-----------|------------|
| Local delimited file | `pl.scan_csv()` + `collect(engine="streaming")` | ~50-100MB |
| Remote delimited file | `source.open_stream()` + chunked `csv.reader` (100K rows) | ~15MB |
| Fixed-width file | Line-by-line parse, 100K-row chunks | ~15MB |
| Multiline HDR file | Header-carried-forward, 100K-row chunks | ~15MB |
| Reports with pre-computed data | Zero re-parse — uses cached aggregations | ~0MB |
| Reports without pre-computed data | Streams each file, releases after each | ~15MB |

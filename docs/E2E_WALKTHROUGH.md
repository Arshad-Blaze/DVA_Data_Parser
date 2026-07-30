# DVA Data Parser — End-to-End Walkthrough

## Architecture

```
UI (Streamlit)
  ↓
Parser (file detection → chunk streaming → canonical normalization)
  ↓
Aggregator (group-by + sum at store / item / UPC level)
  ↓
Validation (store diffs, item comparison, store-list matching)
  ↓
Reports (summary analytics, file review, migration report)
```

Data flows **strictly one direction**. Each layer receives pre-computed output from the layer above — no layer re-parses, re-detects, or re-aggregates.

---

## Two Entry Points

| Page | Purpose | Sides | Phases |
|------|---------|-------|--------|
| **Onboarding** | Single dataset ingestion & validation | 1 (Retailer) | 6 phases |
| **Format Change** | Compare two datasets (BAU vs Test) | 2 (BAU + Test) | 9 phases |

Toggle between them via the **Onboarding / Format Change** buttons at the top of the app.

---

## Phase Map

### Onboarding (6 phases)

```
Discovery → Config → Config Validation → Processing → Validation → Reports
   1           2             3               4             5           6
```

### Format Change (9 phases)

```
Discovery → Discovery Compare → Config → Schema Compare → Config Validation
   1              2               3             4               5

    → Processing → Validation → Reports → Migration Report
         6             7           8             9
```

---

## Phase-by-Phase Detail

### Phase 1: Discovery

**What happens:** Auto-detects file type via heuristics (delimiter counting, fixed-width analysis, multiline pattern recognition). Produces a `DiscoveryResult` with file type, delimiter, candidate layout (for fixed-width), record types (for multiline), confidence score, and recommended columns.

**Options:**
- **Source:** Local folder path or remote data source (SSH) via Connection Manager
- **Config load:** Optionally load a saved JSON config to skip manual setup
- **File formats auto-detected:**

| Detected Format | UI Behavior | User Action Required |
|----------------|-------------|---------------------|
| Delimited | Shows raw preview + parsed preview | Select delimiter (auto-detected) |
| Fixed-width | Shows raw preview + detection info | Define layout via CSV upload or accept candidate |
| Multiline Delimited | Shows raw lines | Enter record type flags (e.g. `H,D,U,T`) + delimiter, then "Flatten Records" |
| Multiline Fixed (HDR) | Shows raw lines | Define header layout + detail layout + optional trailer, then "Flatten Records" |
| Excel | Converted to delimited internally | None |

**Output chaining:** `file_paths`, `file_type`, `delimiter`, `layout`, `start_line`, `record_type`, `columns` are stored on the processing context. All downstream phases read these — never re-detect.

---

### Phase 2: Configuration (Onboarding) / Discovery Compare (Existing)

**Onboarding — Config:** Map physical column names to canonical roles:
- Store, UPC, Description, Units, Price columns
- Price type: Total Price or Unit Price
- Implied Dollars / Implied Units (divide by 100)

**Existing — Discovery Compare:** Side-by-side comparison of BAU vs Test detection results:
- File type match check
- Delimiter match check
- Column count & name comparison
- Identifies columns only in BAU / only in Test

**Output chaining:** Column mapping (`store_col`, `upc_col`, etc.) and price settings stored on context for aggregation. Existing path stores per-side contexts (`ctx.prod`, `ctx.test`).

---

### Phase 3: Config (Existing only) / Schema Compare (Existing only)

**Existing — Config (Step 4):** Map columns for BAU and Test sides independently. Each side gets its own store/UPC/description/units/price mapping, price type, and implied-decimal flags. Sequential — BAU first, then Test.

**Existing — Schema Compare (Step 5):** After both sides mapped, compares their column schemas:
- Common columns count
- BAU-only columns
- Test-only columns
- Full table view of which columns exist on each side

**Output chaining:** Schema differences available for the Migration Report phase.

---

### Phase 4: Config Validation (both paths)

Validates the complete configuration before processing:
- Required columns present
- File paths accessible
- Fixed-width layouts defined
- No ambiguous settings

**Output chaining:** Once validated, context is marked ready for `PHASE_PROCESSING`.

---

### Phase 5: Processing — Aggregation

**Architecture:** `ExecutionEngine` → `OperationExecutor` → `WorkflowOperation` (registry-based dispatch) → `ProcessingService` → `CanonicalDataset` → `Aggregator`

**Onboarding:** 2 parallel aggregations:
- Store-level: `STORE_NUMBER` + `Units` + `Totalprice`
- Item-level: `UPC_CODE` + `PRODUCT_DESCRIPTION` + `UNITS_SOLD` + `TOTAL_DOLLARS`

**Existing:** 4 parallel aggregations:
| # | Side | Level | Output |
|---|------|-------|--------|
| 1 | BAU | Store | `prod.store_agg` |
| 2 | Test | Store | `test.store_agg` |
| 3 | BAU | Item | `prod.item_agg` |
| 4 | Test | Item | `test.item_agg` |

**Normalization pipeline applied to all chunks:**
- Column rename to canonical names
- Numeric parsing (handles currency symbols, thousands separators, parentheses for negatives, implied decimals)
- Quantity resolution (weight/units conversion with UOM table)
- Schema template: `minimal` (5 columns) or `enriched` (+ Brand, Category, Date, QuantityType, UOM)

**Output chaining:** Aggregated DataFrames stored on context. Used directly by Validation and Reports — no re-parsing.

---

### Phase 6: Validation

**Onboarding — 3 optional validations:**

| Validation | Input | Output |
|-----------|-------|--------|
| Compare Store List | Pre-computed store_agg + external store list CSV/Excel | Missing-in-Test / Missing-in-Prod sets |
| Generate UPC Summary | Pre-computed item_agg | UPC summary table + CSV download |
| File Review Report | Pre-computed store_agg + item_agg (avoids re-parse) | Per-file store/UPC/units/dollars stats |

**Existing — 5 optional validations:**

| Validation | Input | Output |
|-----------|-------|--------|
| Store Level Validation | BAU store_agg, Test store_agg | Store diffs (Units/Sales diff + % variance) |
| Item Level Validation | BAU item_agg, Test item_agg | UPC-by-UPC comparison with dollar & unit differences |
| Compare Store List | BAU store_agg, Test store_agg | Missing stores on each side |
| Summary | Item comparison result | Aggregated summary statistics |
| File Review Report | Pre-computed aggs (both sides) | Per-file stats for BAU and Test |

**Output chaining:** Validation results stored on context. Reports phase reads them by name.

---

### Phase 7: Reports (both paths)

**Output Layer** (`dav_tool.workflow.output`) builds an `OutputResult` dataclass with pre-computed DataFrames + CSV bytes. UI only renders.

**Summary worksheets generated for both paths:**
- Summary KPIs (store count, UPC count, total quantity/sales, averages)
- Top/Bottom 10 Stores (by sales, by quantity)
- Top/Bottom 10 UPCs (by dollars, by quantity)
- Category Summary (grouped by description)
- Store Validation Summary (variance % per store — Existing only)

**Sample outputs from full_test.py:**

Store-level aggregation result:
```
STORE_NUMBER | Units | Totalprice
S001         | 15.0  | 149.85
S002         | 8.0   | 79.92
```

Item-level aggregation result:
```
UPC_CODE | PRODUCT_DESCRIPTION | UNITS_SOLD | TOTAL_DOLLARS
100001   | Widget A            | 18.0       | 179.82
```

File Review:
```
filename   | store_count | upc_count | total_units | total_dollars
store1.csv | 3           | 3         | 43.0        | 429.57
```

### Phase 8 (Existing only): Migration Report

Compares schemas and operations between BAU and Test:
- Schema diff: columns added/removed
- Operation comparison: store counts, item counts
- JSON migration report with recommendations

---

## Case Counting

### Onboarding: Total file format cases per phase

| Phase | Delimited | Fixed-Width | Multiline Delimited | Multiline Fixed (HDR) | Excel |
|-------|-----------|-------------|---------------------|----------------------|-------|
| Discovery | ✓ | ✓ | ✓ | ✓ | ✓ (converted) |
| Config | ✓ | ✓ | ✓ | ✓ | ✓ |
| Config Validation | ✓ | ✓ | ✓ | ✓ | ✓ |
| Processing | ✓ | ✓ | ✓ | ✓ | ✓ |
| Validation | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reports | ✓ | ✓ | ✓ | ✓ | ✓ |

**5 file-format paths × 6 phases = 30 format-phase combinations**

Validation check selections (phase 5):
- Compare Store List: on/off
- UPC Summary: on/off
- File Review: on/off
- **8 validation option combinations** × 5 formats = 40

**Onboarding total: 30 (format-phase) + 40 (validation combo) = 70 distinct paths**

### Existing: Total cases per phase

| Phase | Delimited | Fixed-Width | Multiline Delimited | Multiline Fixed (HDR) | Excel |
|-------|-----------|-------------|---------------------|----------------------|-------|
| Discovery | ✓ | ✓ | ✓ | ✓ | ✓ |
| Discovery Compare | ✓ | ✓ | ✓ | ✓ | ✓ |
| Config | ✓ | ✓ | ✓ | ✓ | ✓ |
| Schema Compare | ✓ | ✓ | ✓ | ✓ | ✓ |
| Config Validation | ✓ | ✓ | ✓ | ✓ | ✓ |
| Processing | ✓ | ✓ | ✓ | ✓ | ✓ |
| Validation | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reports | ✓ | ✓ | ✓ | ✓ | ✓ |
| Migration Report | ✓ | ✓ | ✓ | ✓ | ✓ |

**5 format-side-pairs × 9 phases = 45 format-phase combinations**

Each side can have a different format (e.g., BAU delimited, Test fixed-width): **25 side-format pairs** × 9 phases = 225

Validation check selections (phase 7, Existing):
- Store Validation: on/off
- Item Validation: on/off
- Compare Store List: on/off
- Summary: on/off
- File Review: on/off
- **32 validation option combinations** × 25 side-format pairs = 800

**Existing total: 225 (format-phase) + 800 (validation combo) = 1,025 distinct paths**

### Grand Total

| Path | Format-Phase | Validation Combo | Total |
|------|-------------|-----------------|-------|
| Onboarding | 30 | 40 | 70 |
| Existing | 225 | 800 | 1,025 |
| **Combined** | **255** | **840** | **1,095** |

---

## Output Chaining Summary

```
                 ┌─────────────┐
                 │  Discovery   │  file_paths, file_type, delimiter, layout,
                 │  (Phase 1)   │  start_line, record_type, columns
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │  Config      │  store_col, upc_col, desc_col, units_col,
                 │  (Phase 2-4) │  price_col, price_type, implied_*
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │  Processing  │  store_agg (STORE_NUMBER, Units, Totalprice)
                 │  (Phase 5)   │  item_agg  (UPC_CODE, PRODUCT_DESCRIPTION,
                 └──────┬──────┘              UNITS_SOLD, TOTAL_DOLLARS)
                        │
                 ┌──────▼──────┐
                 │  Validation  │  store_df, comparison_df, summary_df,
                 │  (Phase 6)   │  compare_result, fr_prod, fr_test
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │  Reports     │  OutputResult (DataFrames + CSV bytes)
                 │  (Phase 7+)  │  summary_kpis, top/bottom stores/UPCs,
                 └─────────────┘   migration_report (Existing)
```

Each phase reads **only** what was produced by the previous phase. No phase re-executes earlier work. The `ExecutionEngine` (Phase 5) checks cached results on the context and skips completed operations.

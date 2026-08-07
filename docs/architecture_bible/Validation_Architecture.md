# Validation Architecture

Store validation, item validation, comparison logic, difference calculation,
"tolerance", summary generation, and outputs.

---

## 1. Layer Position

```
Aggregation (_aggregators) → pre-computed summaries
  ↓
workflow/validation.py  (validation service — wires engine, no parsing)
  ↓
validation/store.py, validation/item.py  (thin orchestrators)
  ↓
calculations/core.py  (pure Polars calculation engine)
```

Validators **hard-refuse to aggregate**: `storelevelvalidation` raises `ValueError` if
`prod_summary`/`test_summary` are `None`; `run_item_validation` likewise. This enforces
the "Validation must not perform aggregation" rule.

---

## 2. Store Validation (`validation/store.py`)

### `compare_files(prod_file, test_file, col1, col2)` (:18)
- Extracts a column from each DataFrame, `drop_nulls → cast(Utf8) → strip → lowercase →
  unique`, converts to sets.
- Returns `{"missing_in_test": "a, b", "missing_in_prod": "c"}` (comma-joined, sorted,
  lowercased). Used for the store-list comparison (onboarding: BAU stores vs store-list
  file; existing: BAU vs TEST aggregated stores).

### `storelevelvalidation(...)` (:49)
- Requires pre-computed summaries; all format-specific params are documented UNUSED and
  retained only for backward compatibility; `aggregation_source` is a dead parameter.
- Calls `_compare_store_summaries` → `calculations.store_diffs`.

### `storelevelvalidation_from_df(...)` (:100)
- Re-aggregates in-memory DataFrames via the **AggregateOperation** (data operations
  framework) then compares. Production-unused (tests only).

---

## 3. Item Validation (`validation/item.py`)

`run_item_validation(bau_summary, test_summary, ...)` (:17) — requires pre-computed
summaries; returns `(comparison, summary)` via `create_comparison` (= `item_comparison`)
and `item_summary`. `create_comparison` is a trivial wrapper used internally/tests.

---

## 4. Comparison Logic (`calculations/core.py`)

### `pct_diff(base_col, comp_col)` (:10)
`(base − comp)/base × 100` with zero-division rules:
- both zero → 0.0
- only base zero → −100.0
- only comp zero → 100.0

**This is not a tolerance threshold** — it is defined output for undefined percentages.

### `full_join_with_coalesce(left, right, on, suffix="_Test", fill_value=0.0)` (:50)
Full outer join; `fill_null(fill_value)` applied only to non-key columns (fixes key
corruption).

### `store_diffs(prod_summary, test_summary)` (:67)
- Inputs: `STORE_NUMBER` (str), `Units` (f64), `Totalprice` (f64).
- Full join on `STORE_NUMBER`; renames to `Units_Prod/Totalprice_Prod` +
  `Units_Test/Totalprice_Test`; backfills missing side columns with 0.0.
- Computes `Units_Diff`, `Sales_Diff`, `Units_Diff_%`, `Sales_Diff_%`.
- **Missing stores are not flagged** — they appear as 0.0 on one side → ±100% diffs.
- Output columns: `STORE_NUMBER, Units_Prod, Totalprice_Prod, Units_Test,
  Totalprice_Test, Units_Diff, Sales_Diff, Units_Diff_%, Sales_Diff_%`.

### `item_comparison(bau_df, test_df)` (:107)
- Renames `UNITS_SOLD/TOTAL_DOLLARS` → `BAU Units/BAU Dollars` (and TEST variants).
- **Full outer join on `[UPC_CODE, PRODUCT_DESCRIPTION]`** — a UPC whose description
  differs between BAU and TEST yields two presence rows (no UPC-only dedup).
- `classify_presence` on the Units columns: "Present only in TEST" / "Present only in
  BAU" / "Present in Both".
- Casts all four value columns to Float64, fill 0.0.
- Computes `Units Difference`, `Dollar Difference`, `Unit % Difference`,
  `Dollar % Difference`.
- Output columns: `UPC_CODE, PRODUCT_DESCRIPTION, BAU Units, TEST Units, BAU Dollars,
  TEST Dollars, Present In, Units Difference, Dollar Difference, Unit % Difference,
  Dollar % Difference`.

### `item_summary(comparison_df)` (:142)
`group_by("Present In")` summing `Units Difference` and `Dollar Difference`, sorted.

---

## 5. Difference / Tolerance Thresholds — NOT PRESENT

There are **no tolerance/difference thresholds anywhere** in the validation or reporting
layers. The only numeric primitives are `pct_diff` (zero-division rules) and the 0.0
fill values. The word "tolerance" appears only in unrelated detection thresholds
(`_BOUNDARY_CONSISTENCY_RATIO`) and data-access resource thresholds.

Similarly, there is **no explicit duplicate-UPC or missing-UPC validation**. Duplicate
UPCs are silently merged by the aggregation group-by; null UPCs group into a null bucket.
No "duplicate count" or "missing UPC" warning is surfaced.

---

## 6. Validation Service (`workflow/validation.py`)

### `ValidationResult` (plain class, :40)
Fields: `store_comparison`, `item_comparison`, `item_summary`, `store_list_result`
(dict), `upc_summary`, `errors`, `warnings` (never populated). File-review fields were
removed when the Validation→Reports boundary was closed (H5).

### `run_onboarding_validation(...)` (:55)
1. If `run_compare_store_list` → `_run_store_list_compare(store_agg, opts, source)` —
   compares aggregated stores vs an external store-list file (I/O: download,
   `pl.read_excel`/`safe_read_csv`).
2. If `run_item_validation` → `result.upc_summary = item_agg` (no BAU-vs-TEST comparison
   in onboarding; the item aggregate *is* the UPC summary).
3. File review is **not** generated here — it moved to the workflow orchestration layer
   (`workflow/orchestration.py::_generate_file_review` → Reporting). Validation only
   produces validation results (H5).

### `run_existing_validation(...)` (:94)
1. `run_store_validation` → `storelevelvalidation` → `store_comparison`.
2. `run_item_validation` → `run_item_validation` → `item_comparison` + `item_summary`.
3. `run_compare_store_list` → `_run_store_list_compare_both(prod_store_agg,
   test_store_agg)` — **compares BAU vs TEST aggregates; the store-list file path is
   ignored** in this flow.
4. File review for both sides is generated by the workflow orchestration layer after
   validation completes.

Each step is individually try/except-guarded; errors are appended to `result.errors`
and recorded on metrics.

### Orchestration wrappers (`workflow/orchestration.py`)
`run_onboarding_validation(ctx, ...)` and `run_existing_validation(ctx, ...)` build
`ParseOptions`/`ColumnMapping`/`ValidationOptions` from UI-provided values, run
validation, and then coordinate Reporting (file review) via `_generate_file_review`,
copying results back onto the context.

---

## 7. Summary Generation

- **Item summary** — always computed inside `run_item_validation` (grouped by
  `Present In`).
- **`ValidationOptions.run_summary` flag is dead** — never read; the summary is always
  computed whenever item validation runs.
- The business-analytics KPIs are separate (Reporting layer, see Reporting doc).

---

## 8. Known Defects

| # | Severity | Finding |
|---|----------|---------|
| 1 | ~~High~~ **RESOLVED** | Validation service invoked Report generation (`_reports.generate_file_review`) — moved to the workflow orchestration layer (H5). |
| 2 | Medium | `_run_store_list_compare_both` ignores the store-list file in the existing flow (compares BAU vs TEST instead). |
| 3 | Medium | Item comparison joins on UPC **+ description**; changed descriptions produce duplicate presence rows. |
| 4 | Medium | `run_summary` flag is inert. |
| 5 | Medium | Store-list file loading duplicated between `ui/helpers.load_storelist` and `workflow/validation._run_store_list_compare`. |
| 6 | Medium | Missing-store diff = ±100% (no explicit missing indicator at store-diff level). |
| 7 | Low | `storelevelvalidation_from_df`, `create_comparison`, `aggregation_source` param, and format-specific params are dead/vestigial. |
| 8 | Low | I/O (download/read) happens inside the validation service. |
| 9 | Low | No tolerance thresholds or duplicate/missing-UPC checks despite declared scope. |

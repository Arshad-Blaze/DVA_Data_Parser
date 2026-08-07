# Reporting Architecture

Excel/CSV generation, summary sheets, business statistics, downloads, and output
contracts.

---

## 1. Key Finding: There is NO Excel Generation

Despite "Excel generation" in the declared architecture, **no Excel writer exists**
anywhere in the codebase. Grep for `openpyxl`/`xlsxwriter`/`to_excel`/`ExcelWriter`
confirms Excel is used only for **reading** (`.xlsx/.xls` inputs: `ui/helpers.load_storelist`,
`workflow/validation._run_store_list_compare`, `parser/excel.py`, `detection.py`).

All report downloads are **CSV strings** produced by Polars `df.write_csv()` and handed
to `st.download_button(..., file_name="*.csv")`. The only non-CSV download is the
migration report JSON.

---

## 2. Output Layer (`workflow/output.py`)

### `OutputResult` dataclass (:32) — the UI-consumed contract
- Onboarding: `compare_result`, `upc_summary_df`, `upc_summary_csv`, `file_review_df`,
  `file_review_csv`.
- Existing: `store_df`/`store_df_csv`, `comparison_df`/`comparison_df_csv`,
  `summary_df`, `fr_prod`/`fr_prod_csv`, `fr_test`/`fr_test_csv`.
- Summary worksheets: `summary_kpis`, `top_stores`, `bottom_stores`, `top_upcs`,
  `bottom_upcs`, `top_upcs_by_qty`, `top_brands`, `category_summary`,
  `store_validation_summary`.
- Migration: `migration_metrics`, `schema_diff`, `operation_compare`,
  `migration_report_json`, `migration_recommendations`.

### `generate_onboarding_output(ctx)` (:80)
Copies `compare_result`, `upc_summary_df` + CSV, `file_review_df` + CSV, then
`generate_summary_sheets(..., prod_label="Retailer", test_label="Storelist")`.

### `generate_existing_output(ctx)` (:129)
Copies store/item comparison + CSVs, summary_df, file reviews, then
`generate_summary_sheets(store_agg=ctx.prod.store_agg, upc_summary=ctx.prod.item_agg,
item_comparison=ctx.comparison_df, store_diff=ctx.store_df, prod_label="BAU",
test_label="TEST")`.

### `generate_summary_sheets(...)` (:189) — worksheet frames
- `summary_kpis` — the `generate_summary_analytics` single row.
- `top_stores` / `bottom_stores` — top/bottom 10 by `Totalprice` and `Units`, tagged
  `rank_by` = Sales/Quantity.
- `top_upcs` / `bottom_upcs` — top/bottom 10 by `TOTAL_DOLLARS`.
- `top_upcs_by_qty` — top 10 by `UNITS_SOLD`.
- `top_brands` — only if a `Brand` column exists; grouped sum + count.
- `category_summary` — grouped by `PRODUCT_DESCRIPTION` (category is modeled as product
  description).
- `store_validation_summary` — from `store_diff`: `STORE_NUMBER`,
  `Units_Diff_% → Units Variance %`, `Sales_Diff_% → Sales Variance %`.

### `generate_migration_report(ctx)` (:284)
`compare_schemas` + `compare_operations` + `migration_report.generate_report` →
`OutputResult` with migration fields.

---

## 3. Business Statistics (`_reports.py::generate_summary_analytics`, :150)

Single-row KPI DataFrame from **pre-computed frames only** (no re-parsing):

- **Counts:** `Store Count (Prod)`, `Store Count (Test)`, `UPC Count (Prod)`,
  `UPC Count (Test)` — labels **hard-coded "Prod"/"Test"**.
- **Totals:** `Total Quantity (Prod)`, `Total Sales (Prod)`, `Total Quantity (Test)`,
  `Total Sales (Test)` — prefers UPC-level sums, falls back to store-level, else 0.0.
- **Top/Bottom Stores:** top/bottom 5 by sales and by quantity (semicolon-joined
  "STORE: value" strings).
- **Top/Bottom UPCs:** top/bottom 5 selling UPCs by `TOTAL_DOLLARS`.
- **Variance:** largest price/quantity variance from the item comparison (uses
  `prod_label`/`test_label` here — inconsistent with hard-coded Prod/Test elsewhere).
- **Growth rates:** highest/lowest `Units_Diff_%` / `Sales_Diff_%` stores.
- **Averages:** average basket (dollars / n_rows) and average price (dollars / qty),
  keyed with `prod_label`/`test_label`.
- **Execution metrics:** from `_metrics_dict` → `Rows Processed`, `Total Execution
  Time`, `Peak Memory`, `Peak Cpu`, `Files Processed`.
- **Missing data:** value counts of `Present In`.

---

## 4. File Review (`_reports.py::generate_file_review`, :30)

Output columns: `filename, store_count, upc_count, total_units, total_dollars`.

Single mode:
1. **Precomputed mode (:79)** — requires `precomputed_store_agg` + `precomputed_upc_summary`
   (produced by the Aggregation layer) → single consolidated row ("N files (aggregated)").
   Raises `ValueError` when summaries are absent. **The Reports layer never parses or
   aggregates.** The workflow orchestration layer (`workflow/orchestration.py::_generate_file_review`)
   supplies the summaries and coordinates Validation → Reporting.

`date_col` parameter is accepted but never used.

---

## 5. Downloads (UI wiring)

| Download | Source | Location |
|----------|--------|----------|
| UPC Summary CSV | `upc_summary_csv` | `ui/onboarding.py:874` |
| File Review CSV | `file_review_csv` | `ui/onboarding.py:868` |
| Store Compare CSV | `store_df_csv` | `ui/existing.py:1329` |
| Item Compare CSV | `comparison_df_csv` | `ui/existing.py:1345` |
| Summary CSV | `summary_df` CSV | `ui/existing.py:1339` |
| File Reviews (prod/test) | `fr_prod_csv`/`fr_test_csv` | `ui/existing.py:1323/1339` |
| Migration Report JSON | `migration_report_json` | `ui/existing.py:1401-1407` |
| Certification reports (md/json/html) | `runner.generate_report` | `ui/certification_suite.py:103-117` |

Summary sheets are rendered via `ui/helpers._display_summary_sheets` (:131) and
`display_execution_summary` (:200).

---

## 6. Known Defects

| # | Severity | Finding |
|---|----------|---------|
| 1 | High | **No Excel generation** despite declared support — all downloads are CSV. |
| 2 | High | KPI label mismatch: `generate_summary_analytics` writes `Store Count (Prod)` / `Total Quantity (Prod)` / `Total Sales (Prod)`, but the UI reads `Store Count ({side_label})` etc. → these render as **0** in the KPI panel. |
| 3 | Medium | `Total Time` lookup mismatch: analytics writes `Total Execution Time`; UI looks up `Total Time` → metric missing in KPI panel. |
| 4 | Medium | TEST-side summary dropped: `generate_summary_sheets` always passes `test_store_agg=None`/`test_upc_summary=None` → worksheets reflect **BAU only** even in the two-sided flow. |
| 5 | ~~Medium~~ **RESOLVED** | `_reports.generate_file_review` fallback re-parses/aggregates — removed; precomputed summaries are now required (H6). |
| 6 | Medium | Ranking logic duplicated: KPI strings (top/bottom 5) vs summary-sheet frames (top/bottom 10). |
| 7 | Medium | Summary math duplicated between `_summarize` and the streaming loop. |
| 8 | Low | `MigrationReport.to_json()` omits `recommendations` even though they are the primary actionable output. |
| 9 | Low | `generate_summary_analytics` unused KPI keys (not rendered by the UI). |

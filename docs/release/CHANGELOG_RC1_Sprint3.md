# Changelog — RC1 Sprint 3 (Workflow Stabilization)

## Added

- **UOM Column:** `FormatConfig.weight_uom_col` field allows selecting a data column that contains UOM values per row. UI shows "UOM Column" selectbox in Quantity Configuration section. (dav_tool/format_config.py:180, dav_tool/ui/helpers.py:616-633)
- **Guard for empty store list path:** `_run_store_list_compare` returns early when `validation_opts.store_list_path` is empty, preventing crash. (dav_tool/workflow/validation.py:144)

## Changed

- **Connection Manager auto-collapse:** File browser collapses on path selection. Summary caption shown in collapsed state. (dav_tool/ui/connection_manager.py)
- **Store List optional in Onboarding:** Wrapped store list inputs in `st.expander("Store List (optional)", expanded=False)`. (dav_tool/ui/onboarding.py:414)
- **No duplicate `get_column_names()` in Onboarding processing:** Before calling `get_column_names()`, checks `ctx.columns` first. (dav_tool/ui/onboarding.py:216)
- **No duplicate `cached_get_column_names()` in Existing processing:** Processing phase reuses `ctx.prod.schema` when available. (dav_tool/ui/existing.py:674)

## Fixed

- Connection manager path selection no longer shows stale directory tree.
- Store list section no longer takes space when unused.
- Processing phase no longer re-parses data columns when schema is already propagated from config.
- Layout CSV prompt only shows for fixed-width files (verified — already correct).

## Tests

- 210 unit tests: PASS
- 12 golden tests: PASS

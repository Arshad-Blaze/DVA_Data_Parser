# DVA Platform — Redundancy Cleanup Audit

**Date:** 2026-08-07
**Auditor:** Senior Python Engineer
**Focus:** Dead-code removal and post-cleanup verification of the DVA Data Parser

---

## Summary

A full redundancy audit was performed across the ~100-module codebase. All
unused modules, functions, classes, and enums were removed with explicit user
approval for **full removal** (including the test-only operations framework).

**Baseline:** 358 tests passing → **After cleanup: 314 tests passing** (47.5s).
The 44-test delta is exactly the Filter/Sort/Sample/Statistics/Export/Preview
operation tests, whose production modules were deleted (verified: old
`tests/test_operations.py` had 61 test functions, new has 17).

No production functionality was removed — every deleted symbol had zero
reference from non-test code paths.

---

## Removed Modules (git rm)

| Module | Contents | Reason |
|--------|----------|--------|
| `dav_tool/flatten.py` | FlattenEngine, FlattenConfig | Zero importers |
| `dav_tool/layout_registry.py` | LayoutRegistry, LayoutEntry, ColumnLayout | Zero importers |
| `dav_tool/operations/filter.py` | FilterOperation | Test-only |
| `dav_tool/operations/sort.py` | SortOperation | Test-only |
| `dav_tool/operations/sample.py` | SampleOperation | Test-only |
| `dav_tool/operations/statistics.py` | StatisticsOperation | Test-only |
| `dav_tool/operations/export.py` | ExportOperation | Test-only |
| `dav_tool/operations/preview.py` | PreviewOperation | Test-only |

## Removed Functions / Classes / Enums

| File | Removed | Reason |
|------|---------|--------|
| `config_builder.py` | `build_file_info_section`, `build_record_info_section`, `build_schema_section`, `build_business_rules_section`, `_resolve_sample`, `_cleanup_sample`, `_load_sample` | Obsolete progressive-config builders, zero refs |
| `config_validator.py` | `STAGE_LABELS`, `get_current_stage`, `stage_fields`, `stage_summary`, `ConfigValidationError`, `assert_config_valid` | Zero refs |
| `_aggregators.py` | `aggregate_with_options`, `aggregate_with_config` | Zero refs; `aggregate()` kept (used by stream helpers) |
| `options.py` | `CanonicalContext` | Zero refs (only docstring mentions) |
| `format_config.py` | `QuantityType` | Zero refs (only string literals) |
| `workflow/flush.py` | `track_temp_dir`, `_TRACKED_TEMP_DIRS`, `_flush_temp_files` | Permanent no-op, never called |
| `workflow/preview.py` | `parse_from_discovery`, `preview_from_discovery` | Only referenced each other |
| `ui/helpers.py` | `invalidate_preview_caches`, `resolve_source_paths`, `display_config_review`, `edit_and_accept_config`, `progressive_config_wizard`, `render_all_config_sections`, `_render_section_fields`, `render_progressive_stage` | Zero external refs (progressive cluster only referenced internally) |
| `ui/platform.py` | `get_services`, `get_rule_registry`, `get_parser_registry`, `get_parser_factory`, `get_service`, `reset_platform`, `_PLATFORM_READY` | Zero refs; flag was written but never read |

## Kept (verified live, not dead)

- **Parser modules** (`delimited/excel/fixed_width/parent_child/sales_product`):
  `@register_parser`-decorated, loaded via `parser/__init__.py` side effects.
- **`dav_tool/__main__.py`**: console entry point (`dav-tool` in `pyproject.toml`).
- **Operations:** `aggregate.py` (used by `validation/store.py`),
  `workflow_ops.py` (used by `workflow/execution.py`), `base.py`, `registry.py`,
  `orchestration.py`.
- **`ui/platform.py`**: `ensure_bootstrap`, `get_workflow_engine`,
  `get_pipeline_registry` (all referenced by pages).

## Verification

- `import dav_tool.ui.helpers`, `dav_tool.ui.platform`, `dav_tool.operations`
  all import cleanly.
- No stale references to deleted modules or symbols anywhere in the repo
  (grep across `.py`, excluding `venv/`).
- Import-lint (AST walk) on `helpers.py` after cleanup: no unused imports.
- Full suite: **314 passed** in 47.55s (`tests/`, excluding `tests/e2e`).

## Edge Cases Considered

- **Operations framework was public API** — removal was explicitly approved by
  the user; the 6 modules were confirmed test-only before deletion.
- **`QuantityType` / `CanonicalContext` string references** — confirmed they
  were only docstring/literal mentions, not runtime imports.
- **E2E "flatten" references** — verified they refer to flattening concepts via
  `_parsers`/UI, not the deleted `dav_tool/flatten.py` module.
- **`aggregate()` kept** — `stream_store_aggregate`/`stream_item_aggregate`/
  `stream_upc_summary` depend on it.

## Suggested Tests

- Re-run the full suite (done — 314 passed).
- Run an HEB end-to-end dataset through the full pipeline to confirm the
  transformation engine still operates after removal of the progressive-config
  UI helpers (covered by `test_full_pipeline_runs_transformation_end_to_end`).

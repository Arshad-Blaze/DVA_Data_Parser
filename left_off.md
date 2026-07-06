# Phase 4 — Configuration Driven Parsing

## Done

- Created `dav_tool/format_config.py` with `FormatConfig` dataclass, `load_format_config()`, `save_format_config()`, `apply_format_config()`, and `config_from_ctx()`.
- Config schema captures all parsing settings: file_type, delimiter, layout files, multiline/HDR/TRL config, and column mapping.
- `apply_format_config()` sets all `ProcessingContext` fields, loads referenced layout CSVs (resolved relative to config file), flattens multiline data, and auto-applies schema.
- Added `_config_applied` / `_config_name` tracking attributes to `ProcessingContext` (set dynamically, not in dataclass).
- **Onboarding UI**: "Optional: Load Config (JSON)" text input in Phase 0 — loads config, bypasses manual detection/flatten flow, shows flattened preview directly, and allows proceeding to column mapping. "Save Config" input + button in Phase 1 column mapping after confirmation.
- **Existing UI**: "Optional: BAU Config (JSON)" and "Optional: Test Config (JSON)" text inputs per side in Phase 0 — loads and applies config per-side, skips manual detection/flatten when config is pre-loaded, shows config-loaded status.
- Bypassed manual multiline inputs in `_multiline_flow()` / `_multiline_section()` / `_multiline_side_inputs()` when config is pre-loaded.
- **11 unit tests** in `tests/test_format_config.py`: roundtrip save/load, partial config, apply delimited, apply multiline delimited, apply HDR with layouts, relative path resolution, missing layout handling, empty paths, config_from_ctx, roundtrip ctx via config.
- **5 E2E Playwright tests** in `tests/e2e/onboarding/test_onboarding_config_load.py`: config load delimited, multiline delimited, HDR fixed, shows preview, proceeds to column mapping.
- All 86 unit tests pass (75 existing + 11 new); all 26 onboarding E2E pass (21 existing + 5 new); all 7 existing HDR trailer E2E pass.

## Key Design Decisions

- Config is a simple JSON file — no new dependencies, easy to hand-edit or generate.
- Layout file paths in config are resolved relative to the config file's directory (or absolute).
- `apply_format_config()` is purely additive — it sets ctx fields but doesn't modify parser/aggregator/validation code.
- Column mapping fields in config pre-populate the column mapping phase, enabling fully automated onboarding from a config file.
- No changes to any parser, aggregator, validation, or report code.

## Files Changed

| File | Change |
|---|---|
| `dav_tool/format_config.py` | **NEW** — FormatConfig dataclass, load/save/apply, config_from_ctx |
| `dav_tool/ui/onboarding.py` | Added config load in Phase 0, save config in Phase 1, import + bypass in multiline flow |
| `dav_tool/ui/existing.py` | Added config load per-side in Phase 0, bypass in multiline section |
| `tests/test_format_config.py` | **NEW** — 11 unit tests |
| `tests/e2e/onboarding/test_onboarding_config_load.py` | **NEW** — 5 E2E tests |
| `tests/e2e/sample_data.py` | Added `create_config_test_data()` |
| `tests/e2e/conftest.py` | Added `config_test_data` fixture |
| `left_off.md` | Updated |

## Next Steps

1. Phase 5 — Golden Dataset Framework (regression dataset against expected canonical output).
2. Phase 6 — Performance Improvements (memory, CPU, batch size, parallel processing).
3. Phase 7 — Enterprise Readiness (installer, logging, configuration repository, documentation).

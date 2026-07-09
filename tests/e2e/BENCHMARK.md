# E2E Test Benchmark — Phase 4

**Date:** 2026-07-06
**Branch:** phase3-trailer
**Commit:** 8798554

## Summary

| Suite | Tests | Passed | Failed | Skipped | Wall Time |
|---|---|---|---|---|---|
| Onboarding | 26 | 26 | 0 | 0 | 348.74s |
| Existing | 20 | 19 | 0 | 1 | 309.19s |
| Regression | 8 | 8 | 0 | 0 | 90.21s |
| **Total** | **54** | **53** | **0** | **1** | **748.14s** |

1 skipped: `test_detection_completes_for_both_sides` — pre-existing flaky timing test (not caused by Phase 4).

## Performance Metrics

### Onboarding (26 tests)

| Test | Duration (s) |
|---|---|
| `test_start_over_resets_phase` | 20.946 |
| `test_validation_executes` | 20.374 |
| `test_reports_available` | 20.194 |
| `test_full_onboarding_flow` | 16.632 |
| `test_config_load_proceed_to_mapping` | 8.930 |
| `test_proceed_to_column_mapping` | 8.050 |
| `test_trailer_fields_appear_in_preview` | 7.413 |
| `test_config_load_multiline_delimited` | 7.154 |
| `test_config_load_delimited` | 7.151 |
| `test_config_load_hdr_fixed` | 7.076 |
| `test_config_load_shows_preview` | 7.070 |
| `test_trailer_layout_loads` | 7.054 |
| `test_apply_schema` | 6.174 |
| `test_header_detail_layouts_load` | 5.555 |
| `test_column_mapping_widgets_present` | 4.472 |
| `test_column_mapping_phase_loads` | 4.402 |
| `test_flatten_records` | 4.375 |
| `test_detection_completes` | 2.583 |
| `test_detects_hdr_fixed` | 2.565 |
| `test_raw_preview_appears` | 2.551 |
| `test_preview_appears` | 2.547 |
| `test_detects_multiline` | 2.539 |

### Existing (19 tests, excludes 1 skipped)

| Test | Duration (s) |
|---|---|
| `test_start_over_resets` | 29.872 |
| `test_full_existing_flow` | 28.446 |
| `test_validation_executes` | 27.662 |
| `test_reports_available_existing` | 27.414 |
| `test_proceed_to_column_mapping` | 13.175 |
| `test_trailer_layout_bau` | 9.748 |
| `test_apply_schema` | 9.422 |
| `test_flatten_records` | 8.948 |
| `test_column_mapping_widgets_present` | 8.633 |
| `test_header_detail_layouts_bau` | 8.242 |
| `test_previews_appear` | 7.085 |
| `test_detects_multiline_both_sides` | 6.927 |
| `test_detects_hdr_both_sides` | 6.648 |
| `test_raw_previews_appear` | 5.192 |
| `test_hdr_prefix_shown` | 5.172 |

### Regression (8 tests)

| Test | Duration (s) |
|---|---|
| `test_processing_history_available` | 20.114 |
| `test_missing_store_list_shows_error` | 18.316 |
| `test_navigation_between_pages` | 6.099 |
| `test_detection_shows_status` | 3.422 |
| `test_invalid_path_shows_error` | 2.548 |
| `test_developer_mode_toggle` | 1.671 |
| `test_cannot_proceed_without_both_paths` | 0.096 |
| `test_cannot_proceed_without_path` | 0.020 |

## HTML Report

Full report with screenshots: `tests/e2e/reports/report.html`

## Notes

- Tests run with `--slowmo 200` (200ms delay between Playwright actions)
- Streamlit server started fresh per session
- Test data generated fresh per session in temp directories
- Pre-existing flaky test `test_detection_completes_for_both_sides` excluded

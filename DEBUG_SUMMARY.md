=== TESTING FRAMEWORK ANALYSIS ===

E2E Tests (8 tests per flow, 24 total):
- ALL tests use the same data format: delimited CSV files
- Tests focus on onboarding and existing flows
- NO multiline-specific tests in the current E2E suite

Full unit tests (full_test.py) includes:
- 10 comprehensive test sections covering all formats:
  1. DELIMITED SINGLE FILE
  2. DELIMITED MULTI-FILE
  3. FIXED-WIDTH SINGLE FILE
  4. FIXED-WIDTH MULTI-FILE
  5. MULTILINE DELIMITED (HDR) SINGLE
  6. MULTILINE DELIMITED (HDR) MULTI-FILE
  7. MULTILINE FIXED-WIDTH (type prefix) single
  8. MULTILINE FIXED-WIDTH (type prefix) multi-file
  9. HDR FIXED-WIDTH (multi-character) with flattening
  10. Various edge cases and report testing

=== UI COMPONENTS FLOW ===
onboarding.py phase0 → phase0_parsing_and_preview:
- Detects file type on first file selection
- Calls is_multiline_record(file_paths[0])
- If multiline: calls _multiline_flow()
- If delimited/fixed: calls detect_file_type

MULTILINE FLOW in onboarding.py (_multiline_flow):
- Shows multi-line structured file warning
- Calls _multiline_preschema(file_paths) - user-input schema renaming
- If schema applied: ctx.schema = dict values -> next phase
- Shows preview_flattened_multiline_preview (collapsed preview)
- Has preview and schema retry/reapply logic

Phase1 (column mapping) is identical for all file types:
- Gets columns from ctx.columns (inboarding) or ctx.columns (existing)
- Same UI widgets, same validation, same aggregation trigger

=== MULTILINE UI STATUS ===
onboarding.py:
✅ _multiline_preschema() exists - user schema renaming for multiline
✅ _multiline_flow() exists - complete multiline UI flow
✅ _multiline_preschema_button() exists - "Apply Schema" button

existing.py:
❌ _multiline_side_inputs() exists - but uses st.text_area without keys
❌ _multiline_preschema() exists - but also uses text_area without keys
❌ Tests fail due to empty column names from UI state reset

=== UI COMPONENT NAVIGATION ===
oneboarding.py:
- Phase 1: File Detection & Preview
- Phase 2: Column Mapping (same for all types)
- Phase 3: Validation (same for all types)

existing.py:
- Phase 1: File Detection & Preview
- Phase 2: Column Mapping (same for all types)
- Phase 3: Validation (same for all types)

=== STATUS CHECKLIST ===

Phase 2 Requirements:
1. Detect multiline record format.
   ✅ Done in detection.py: is_multiline_record()
2. Group physical lines into logical records.
   ✅ Done in _parsers.py: flatten_multiline_chunks()
3. Flatten logical records.
   ✅ Done in _parsers.py: same as above
4. Generate exactly the same canonical dataframe as single-line parsing.
   ❓ Need verification - must test canonical equivalence
5. Do NOT change downstream processing.
   ✅ By design - looks correct

=== IMMEDIATE CONCERNS ===

1. UI State Issue in existing.py:
   - _multiline_side_inputs() uses st.text_area without keys
   - When navigation occurs, widgets lose keys → state reset
   - Tests fail: column mapping gets empty values
   - Fix: Add explicit keys to text_area widgets

2. Missing Multiline E2E Tests:
   - All 24 Playwright tests use delimited test data
   - Need multiline test workflow
   - Need to update existing_test_* and onboarding_test_* files

=== NEXT STEPS ===

1. Fix UI state reset issue in existing.py
   - Add keys to all _multiline_side_inputs text_area widgets
   - Add keys to _multiline_preschema text_area widgets

2. Verify canonical equivalence
   - Run existing tests to confirm equivalence
   - Write tests to prove multiline produces same output as single-line

3. Add multiline E2E tests
   - Update or create new Playwright tests for multiline workflow

4. Test complete implementation

=== RECOMMENDED APPROACH ===

1. Fix UI bugs first (easier, more stable)
2. Add test coverage for multiline functionality
3. Verify canonical equivalence
4. Create integration tests
5. Bugfix any remaining issues

=== URGENCY ===

HIGH - Need to fix UI bugs and add test coverage before proceeding with Phase 3

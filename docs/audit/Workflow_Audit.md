# DVA Platform — Product Workflow Audit

**Role:** Retail Data Operations Analyst (first-time user)
**Method:** Screen-by-screen workflow walkthrough
**Focus:** Can an analyst complete Onboarding and Format Change without developer assistance?

---

## Executive Summary

A first-time analyst **cannot** reliably complete either workflow without developer assistance. The most critical obstacles are:

1. **Duplicate column mapping** — The same 5-column selection appears in two separate phases. The first selection is silently discarded.
2. **Missing Step 1** — Both workflows start at "Step 2". The Connection Manager is separate and its relationship to the workflow is unclear.
3. **No back navigation** — Any mistake requires "Start Over", losing all progress.
4. **`st.stop()` creates soft locks** — The page freezes with no retry mechanism in multiple places.
5. **Progress bar mismatch** — The progress bar shows 7 phases for both workflows, but Format Change has 10 phases.

Without documentation, an analyst will get stuck at duplicate column mapping, soft-locked pages, and the missing Step 1.

---

## Onboarding Workflow

### Issue OB-1: Duplicate column mapping in Phase 2 and Phase 4

**Current Behaviour:** The analyst selects 5 columns (Store, UPC, Description, Units, Price) in Step 3 (Column Mapping). Later, in Step 5 (Processing), the same 5 column selectboxes appear again, and the analyst must select them again. The first selection is silently overwritten.

**Expected Behaviour:** Columns should be mapped once. The processing phase should reuse the mapping from the configuration phase.

**Business Impact:** Analyst confusion, wasted time, risk of selecting different columns the second time producing wrong results. Estimated 2-3 minutes of unnecessary work per session.

**Suggested Improvement:** Remove the duplicate column mapping in the processing phase. Use the mapping established in the configuration phase. Display it as a read-only summary for confirmation before processing.

**Priority:** P1

### Issue OB-2: Workflow starts at "Step 2"

**Current Behaviour:** The phase header says "Step 2: Discovery — File Detection & Preview". Step 1 (Connection) is never shown as a UI step. The Connection Manager is rendered separately above the workflow and the phase progress bar always shows "1. Connection" as completed from first load.

**Expected Behaviour:** The workflow should clearly show all 7 steps starting with Step 1. The Connection Manager should be part of the workflow, not a separate top-level component.

**Business Impact:** Analyst is confused about the workflow structure. They may not realize a connection needs to be established, or may think it was already done.

**Suggested Improvement:** Either integrate the Connection Manager as Step 1 of the workflow, or renumber steps to start at Step 1 (Discovery).

**Priority:** P1

### Issue OB-3: No back navigation between phases

**Current Behaviour:** The only way to go back to a previous phase is clicking "Start Over" which clears all progress. There is no "Back" or "Previous Step" button.

**Expected Behaviour:** Standard multi-step workflow with "Back" and "Next" navigation between phases. State should be preserved when going back.

**Business Impact:** Any mistake in a later phase forces the analyst to restart entirely. Loss of all configuration work. Estimated 5-15 minutes of rework per mistake.

**Suggested Improvement:** Add back navigation buttons between phases. Store workflow state persistently so going back preserves previous selections.

**Priority:** P1

### Issue OB-4: Page freezes on detection failure with no retry

**Current Behaviour:** When file detection fails for non-fixed files, `st.stop()` is called. The page stops rendering entirely with no retry button. The analyst sees a frozen page.

**Expected Behaviour:** A clear error message with a "Retry Detection" button or guidance on what to change.

**Business Impact:** Analyst cannot recover. Must refresh the browser and start over. Dead end in the workflow.

**Suggested Improvement:** Replace `st.stop()` with a visible error state and retry button. The Format Change workflow already has this pattern — apply it to Onboarding.

**Priority:** P1

### Issue OB-5: No pass/fail summary at end of workflow

**Current Behaviour:** After all phases complete, the Reports phase shows data tables but no explicit "All validations passed" or "Validation failed" summary. The "Start Over" button is the only action.

**Expected Behaviour:** A clear pass/fail verdict at the top of the Reports page. If failed, indicate which validation(s) failed and why.

**Business Impact:** Analyst cannot tell if the data is good or bad. Must manually inspect tables to determine pass/fail. Risk of approving bad data.

**Suggested Improvement:** Add a prominent pass/fail indicator at the top of the Reports phase. Show per-validation pass/fail status.

**Priority:** P1

### Issue OB-6: Phase 3 (Validate Configuration) is a dead click

**Current Behaviour:** The Validate Configuration phase requires clicking "Proceed to Processing →" even when the config is valid. The analyst performs no actual validation — just one click to advance.

**Expected Behaviour:** If all configuration is valid, advance automatically. Only show validation UI when there are errors to resolve.

**Business Impact:** Unnecessary click adds friction. Analyst may wonder what they're supposed to do in this step.

**Suggested Improvement:** Skip the Validate Configuration page entirely when config is valid. If invalid, show errors inline in the Configuration phase.

**Priority:** P2

### Issue OB-7: Implied Dollars/Units checkboxes unexplained

**Current Behaviour:** Two checkboxes labeled "Implied Dollars" and "Implied Units". No tooltip, help text, or explanation of what they do or when to use them.

**Expected Behaviour:** Brief help text or tooltip explaining that these divide dollar/unit values by 100 (for systems that store cents as integers).

**Business Impact:** Analyst either ignores them (potential wrong data) or turns them on/off randomly (data corruption).

**Suggested Improvement:** Add tooltip text: "Check if dollar values are stored as cents (e.g., $10.99 stored as 1099). Divides by 100."

**Priority:** P2

### Issue OB-8: Store List section hidden by default

**Current Behaviour:** The Store List input is inside a collapsed expander labeled "Store List (optional)". If the analyst needs store comparison, they must know to look for it and expand it.

**Expected Behaviour:** If store comparison is a common use case, it should not be hidden. If optional, indicate availability with a visible indicator.

**Business Impact:** Analyst may not know store comparison is available as a validation option.

**Suggested Improvement:** Keep the expander but add a caption: "Optional: Upload a store list to validate store coverage."

**Priority:** P2

### Issue OB-9: No loading indicator during file detection

**Current Behaviour:** `detect_file()` may take several seconds for large folders, but there is no spinner or progress indicator.

**Expected Behaviour:** A spinner with "Detecting file type..." message during detection.

**Business Impact:** Analyst may think the app is frozen or unresponsive.

**Suggested Improvement:** Wrap `detect_file()` in a `st.spinner()`.

**Priority:** P2

---

## Format Change Workflow

### Issue FC-1: Triple column mapping

**Current Behaviour:** The analyst selects column mappings three times: in Phase 3 (Step 4), again in Phase 6 (Step 7) for BAU, and again in Phase 6 for Test. Same issue as OB-1 but worse — 3× duplication for 2 data sides.

**Expected Behaviour:** Columns should be mapped once per data side during configuration. Processing should reuse those mappings.

**Business Impact:** 15 column selections per session instead of 5. Significant time waste and error risk.

**Suggested Improvement:** Map columns once per side during the configuration phase. Read-only summary in processing phase.

**Priority:** P1

### Issue FC-2: Progress bar shows 7 phases but workflow has 10

**Current Behaviour:** The progress bar (from helpers.py) hardcodes 7 phase labels. Format Change has 10 phases including Discovery Compare, Schema Compare, and Migration Report. These extra phases are invisible on the progress bar.

**Expected Behaviour:** The progress bar should reflect the actual number of phases in the current workflow.

**Business Impact:** Analyst cannot tell where they are in the workflow. Progress bar is misleading.

**Suggested Improvement:** Make the progress bar accept the actual phase count and labels from the workflow.

**Priority:** P1

### Issue FC-3: BAU/Test/Prod naming confusion

**Current Behaviour:** The UI uses "BAU" (Business As Usual) for one data side, "Test" for the other. But the code and context attributes also use "Prod" and "Retailer" interchangeably. The analyst sees "BAU" in one place and "Prod" in another.

**Expected Behaviour:** Consistent terminology throughout. If the user-facing term is "BAU", use it everywhere. If "Existing" is preferred, use that.

**Business Impact:** Analyst may not know what "BAU" means, or may think "Prod" and "BAU" are different concepts.

**Suggested Improvement:** Pick one term set (e.g., "Existing" / "New") and use it consistently in all labels, headers, and code visible to the UI.

**Priority:** P1

### Issue FC-4: No guidance on handling mismatched discovery results

**Current Behaviour:** The Discovery Comparison page shows BAU vs. Test differences (file type, delimiter, columns). The only action is "Proceed to Configuration →" regardless of match or mismatch. No guidance on what mismatches mean or whether to proceed.

**Expected Behaviour:** If file types match, proceed normally. If they don't match, show guidance: "BAU is comma-delimited but Test is pipe-delimited. This is unusual — verify the Test file format. You can proceed but results may be affected."

**Business Impact:** Analyst may proceed with mismatched data without realizing the comparison is invalid.

**Suggested Improvement:** Add contextual guidance based on comparison results. Warning-highlight mismatches with explanatory text.

**Priority:** P2

### Issue FC-5: "Compare Discovery Results →" button behavior is unclear

**Current Behaviour:** After both BAU and Test sides complete detection, a button says "Compare Discovery Results →". Clicking it advances to the next phase but there is no visible "comparison" — the comparison happens internally and is shown in the next phase.

**Expected Behaviour:** The button label should match the next phase. Or show the comparison inline and then advance.

**Business Impact:** Analyst clicks the button and the page changes. They may not realize the comparison already happened.

**Suggested Improvement:** Rename to "Review Discovery Comparison →" to set expectation of what's next.

**Priority:** P2

### Issue FC-6: Sequential BAU/Test configuration without side-by-side view

**Current Behaviour:** In the configuration phase, the analyst configures BAU first, accepts, then configures Test. They cannot see both configurations simultaneously.

**Expected Behaviour:** Show BAU and Test configuration side by side, or allow toggling between them.

**Business Impact:** Analyst must remember BAU settings when configuring Test. Cannot verify both are correct simultaneously.

**Suggested Improvement:** Two-column layout for concurrent configuration, or a summary comparison after both are accepted.

**Priority:** P3

---

## Connection Manager

### Issue CM-1: Info banner is misleading

**Current Behaviour:** After selecting a path in the Connection Manager, an info banner says "Selected path: **{path}** — enter it in the folder path field below to use it." But the folder path is auto-populated — the analyst does not need to enter it again.

**Expected Behaviour:** A confirmation message: "Path selected: **{path}**. Ready for discovery." No instruction to re-enter.

**Business Impact:** Analyst may try to re-enter the path unnecessarily, or wonder why the auto-populated path doesn't match.

**Suggested Improvement:** Update the message to confirm the path is ready for use.

**Priority:** P1

### Issue CM-2: "Local" connection shows spinner then disappears

**Current Behaviour:** Clicking "Use Local File System" triggers a brief spinner ("Connecting...") and then the file browser appears. The "connected" state is not explicitly confirmed.

**Expected Behaviour:** A success message or visual indicator confirming local filesystem is connected.

**Business Impact:** Minor confusion — analyst may wonder if the connection succeeded.

**Suggested Improvement:** Show a brief success toast or status badge: "Local Filesystem — Connected"

**Priority:** P3

### Issue CM-3: File list preview calls detect_file on every expand

**Current Behaviour:** The data preview expander in the Connection Manager calls `detect_file()` every time it expands. For large folders or remote connections, this is expensive and slow.

**Expected Behaviour:** Cache detection results. Only re-detect when the file list changes.

**Business Impact:** Slow response when toggling the preview expander. Analyst waits repeatedly for the same detection.

**Suggested Improvement:** Cache the `_cm_discovery` result and only invalidate on path or file list change.

**Priority:** P2

### Issue CM-4: Directory without files shows no feedback

**Current Behaviour:** If a directory has no files, the file list shows "No files found at ...". But the analyst may still be able to proceed — the workflow will later fail.

**Expected Behaviour:** Clearly indicate that the directory contains no processable files and the workflow cannot proceed.

**Business Impact:** Analyst selects an empty directory and proceeds to the workflow, only to get an error later.

**Suggested Improvement:** Show a warning banner: "This directory contains no files. Select a different directory."

**Priority:** P2

---

## Cross-Cutting Issues

### Issue XC-1: No explicit "Workflow Complete" notification

**Current Behaviour:** After all phases complete in either workflow, the Reports page shows data but no "Workflow complete" message. The analyst is left to scroll and interpret results.

**Expected Behaviour:** A prominent "✓ Workflow Complete" indicator at the top of the Reports phase.

**Business Impact:** Analyst may not realize the workflow is finished and may wait for something else to happen.

**Suggested Improvement:** Add a completion banner with checkmark icon at the top of the Reports page.

**Priority:** P1

### Issue XC-2: "Step 1" never visible

**Current Behaviour:** Phase progress starts at WORKFLOW_PHASE.CONNECTION (0) but neither workflow renders a Connection UI step. The progress bar shows Step 1 as always completed.

**Expected Behaviour:** Either show Step 1 as part of the workflow, or start the progress bar at Step 2.

**Business Impact:** Analyst sees a completed step they never performed. Confusing.

**Suggested Improvement:** If Connection Manager is always shown as a separate top-level component, the workflow progress bar should start at Step 2 (Discovery) for clarity.

**Priority:** P1

### Issue XC-3: Default page is "Format Change", not "Onboarding"

**Current Behaviour:** `st.session_state.page = "existing"` is the default. A first-time analyst lands on the more complex Format Change workflow.

**Expected Behaviour:** Default to Onboarding (simpler, single-dataset workflow) for first-time users.

**Business Impact:** Analyst sees the more complex workflow first and may be overwhelmed.

**Suggested Improvement:** Default to "onboarding". Add a user preference or onboarding flow to choose.

**Priority:** P2

### Issue XC-4: Phase progress bar is not clickable

**Current Behaviour:** The progress bar shows steps visually but clicking a step does not navigate to it.

**Expected Behaviour:** Clickable steps for quick navigation.

**Business Impact:** Analyst cannot jump to a specific phase. Must click through sequentially.

**Suggested Improvement:** Make completed steps clickable to navigate back. Disable future steps.

**Priority:** P3

---

## Summary

| Priority | Count | Key Issues |
|----------|-------|-----------|
| P1 | 9 | Duplicate column mapping, missing Step 1, no back nav, st.stop() freezes, no pass/fail summary, misleading CM banner, triple mapping in FC, progress bar mismatch, naming confusion, no completion notification |
| P2 | 9 | Dead Validate Config click, unexplained checkboxes, hidden store list, no detection spinner, mismatched discovery guidance, unclear button labels, preview re-detection, empty directory feedback, default page |
| P3 | 3 | Side-by-side config (FC), local connection confirmation, clickable progress bar |

**Conclusion:** A first-time analyst **cannot** complete either workflow without developer assistance. The duplicate column mapping and `st.stop()` soft locks are critical blockers. An estimate of **9 P1 fixes** and **9 P2 improvements** are needed before the workflow is usable by an unsupervised analyst.

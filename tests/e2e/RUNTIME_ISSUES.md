# Runtime Issues Discovered During E2E Testing

## Critical

### 1. Column Mapping Defaults to First Column for All Selectboxes

**Location:** `dav_tool/ui/onboarding.py:150-154`, `dav_tool/ui/existing.py:251-270`

**Description:** All column mapping selectboxes default to the first column in the dropdown (e.g., "Store") rather than intelligently matching column names. When a user clicks "Confirm Mapping" without changing defaults, `stream_store_aggregate` receives the same column name for store, units, and price, causing a `polars.exceptions.DuplicateError`:

```
polars.exceptions.DuplicateError: projections contained duplicate output name 'Store'
```

**Impact:** Users MUST manually select all 5 columns correctly. Any mistake causes a hard crash with a Polars error displayed to the user.

**Recommended Fix:** Either:
- Select the most likely column by matching column names (e.g., match "Store", "UPC", "Description", "Units", "Price" by case-insensitive substring)
- Or add validation before confirming mapping that checks for duplicate column selections and shows a user-friendly error message
- Or add a try/except around the aggregation call with a helpful error message

## Medium

### 2. Validation Error Message Not User-Friendly for Missing Store List

**Location:** `dav_tool/ui/onboarding.py:411-414`

**Description:** When "Compare Store List" is checked but no store list path is provided, the error message only says "Store list file required". This appears as a Streamlit error box without guiding the user to the store list input field in the previous phase.

**Impact:** Users who proceed quickly through column mapping may not remember to provide a store list path and get a brief, unhelpful error.

**Recommended Fix:** Enhance the error message to indicate which phase/field needs attention: "Store list file required. Please go back to Phase 2 (Column Mapping) and provide a Store List File Path."

### 3. No Visual Feedback During Aggregation Phase

**Location:** `dav_tool/ui/onboarding.py:186-209`, `dav_tool/ui/existing.py:312-368`

**Description:** When the user clicks "Proceed to Processing & Validation", the application runs aggregations synchronously with no progress bar or loading indicator. For large files, the UI appears frozen.

**Impact:** Users may think the application has crashed or become unresponsive during long-running aggregations.

**Recommended Fix:** Use Streamlit's `st.spinner()` or `st.progress()` during the aggregation phase to provide visual feedback.

### 4. Developer Mode Checkbox Visible in Sidebar With No Visual Distinction

**Location:** `dav_tool/ui/onboarding.py:31`, `dav_tool/ui/existing.py:37`

**Description:** The "Developer Mode" checkbox is always visible in the sidebar. There's no visual cue that it's a development/debug feature.

**Impact:** Non-technical users may enable it, seeing raw diagnostics they don't understand.

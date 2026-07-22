Sprint: Core Stabilization & Canonical Schema Implementation

This sprint is NOT about adding new features. It is about making the DVA Platform stable, predictable, retailer-agnostic and production ready.

=========================
PRIMARY GOAL
=========================

The platform must have ONE internal schema.

Retailers may provide completely different column names, but after the Mapping phase every downstream layer must work ONLY on the canonical schema.

Example:

store
store_num
location
site
store_id

must all become

STORE_NUMBER

Similarly,

upc
barcode
sku
item_code

must become

UPC_CODE

sales
net_sales
sales_amt
total_sales

must become

TOTAL_DOLLARS

etc.

No downstream code should ever know retailer-specific column names.

After mapping there should only be canonical column names.

Validation SHOULD continue using canonical names.

DO NOT change validation to dynamically use retailer column names.

Instead, fix the mapping layer so that every dataset entering Aggregation and Validation has already been renamed to the canonical schema.

This architecture must be enforced everywhere.

====================================================
WORK ITEMS
====================================================

1. Review every pipeline layer.

Detection
↓

Preview

↓

Parser

↓

Column Mapping

↓

Canonical Dataset

↓

Aggregation

↓

Validation

↓

Reports

Verify each layer has a single responsibility.

Remove duplicated logic.

Remove unnecessary coupling.

Ensure each layer only communicates through defined contracts.

====================================================

2. Detection Stability

Detection must execute ONLY once per dataset.

No repeated detection during Streamlit reruns.

Cache DiscoveryResult correctly.

Invalidate cache ONLY when:

• files change
• user clicks Re-detect
• configuration changes

Never rerun because a widget changed.

====================================================

3. Preview Pipeline

Make preview stages explicit.

Raw Preview

↓

Detected Preview

↓

Flattened Preview (multiline only)

↓

Parsed Preview

↓

Canonical Preview

Each stage should clearly represent the output of the previous layer.

No mixed previews.

====================================================

4. Fixed Width Workflow

Redesign the workflow as:

Raw Preview

↓

Detection Summary

↓

Layout Upload OR Layout Builder

↓

Parsed Preview

↓

Column Mapping

↓

Canonical Preview

Simplify Layout Builder.

Keep only:

• Column Name
• Start
• Length
• Type

End should be calculated automatically.

Remove all unnecessary columns.

Ensure uploaded layouts and manually created layouts produce identical LayoutDefinition objects.

====================================================

5. Session State

Audit every session state key.

Ensure:

• no duplicate initialization
• no missing widget keys
• no unnecessary reruns
• no stale previews
• proper cleanup
• deterministic behavior

====================================================

6. Detection Audit

Review every detection algorithm.

Delimiter detection

Header detection

Record type detection

Fixed width detection

Multiline detection

Date detection

Quantity detection

Weight detection

UOM detection

Ensure every retailer sample works.

====================================================

7. Retailer Compatibility

Validate against every retailer sample collected.

Delimited

Quoted CSV

Pipe-delimited

Fixed Width

HDR

Multiline

Header/Trailer

Sales + Product Master

Mixed Units + Weight

No retailer should require code changes.

Only configuration should differ.

====================================================

8. Quantity Resolution

Implement and verify the rule:

IF Weight Quantity exists

AND Weight Quantity > 0

Use Weight Quantity.

Else

If Weight Quantity is blank or zero

Use Units.

Weight takes priority.

Units are fallback only.

Carry Weight UOM through aggregation.

Support mixed retailers correctly.

====================================================

9. Logging

Replace print() with structured logging.

Every major phase should log:

START

COMPLETE

WARN

ERROR

Include timing.

Include row counts.

Include detection confidence.

====================================================

10. Exception Handling

Every workflow should fail gracefully.

Never expose Python tracebacks in the UI.

Display meaningful user messages.

Write detailed diagnostics to logs.

====================================================

11. Imports

Audit the entire repository.

Imports only at module level.

No local imports unless absolutely required to break circular dependencies.

Remove unused imports.

Verify package compatibility.

Remove unnecessary dependencies.

Investigate pyiceberg dependency and ensure optional packages degrade gracefully if unavailable (no admin-only installation requirements).

====================================================

12. UI Audit

Perform complete UI testing.

Execute:

Onboarding

Existing Validation

Format Change

Detection

Layout Builder

Mapping

Processing

Validation

Reports

No broken navigation.

No dead buttons.

No repeated execution.

No hidden crashes.

====================================================

13. Detection Confidence

Show WHY a file was detected.

Example:

Detected Fixed Width

Confidence: 97%

Reason:

✓ Constant record length

✓ Character boundaries detected

✓ No delimiter pattern

✓ Fixed-width score exceeded threshold

Do similar reasoning for all file types.

====================================================

14. Documentation Cleanup

Move ALL developer markdowns, review reports and architecture notes into a dedicated docs/developer/ folder.

Delete obsolete documentation.

Remove duplicate markdowns.

Keep only user-facing documentation in the root.

====================================================

SUCCESS CRITERIA

• One canonical schema after mapping.
• Validation uses ONLY canonical column names.
• Detection runs once.
• No unnecessary reruns.
• Stable UI.
• All retailer samples supported.
• Fixed-width workflow simplified.
• Preview pipeline clearly staged.
• Proper logging.
• Graceful exception handling.
• Global imports only.
• Clean documentation.
• Platform ready for the next feature sprint.

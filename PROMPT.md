RC2 IMPLEMENTATION

The repository has completed RC1 and now moves into RC2.

The Architecture Bible is the ONLY source of truth.

Every implementation decision must strengthen the architecture rather than add shortcuts.

Mission
-------
Complete RC2 by making the platform production-ready while remaining fully architecture compliant.

Primary objectives

1. Complete the Detection Layer.
   - Detection becomes the single source of truth.
   - It must fully describe every supported file.
   - Support delimited, fixed-width, multiline, HDR, mixed record types, trailer detection, record prefixes, layout metadata, candidate schema, candidate quantity columns, candidate UOM columns, confidence score, warnings and recommendations.
   - No downstream layer may perform re-detection.

2. Replace external Layout CSV dependency.
   - Build a fully interactive Fixed Width Layout Builder.
   - Workflow:
       Raw Preview
       → Record Type Selection
       → Start Line
       → Detail Prefix
       → Flatten Preview (if multiline)
       → Character Ruler
       → Interactive Column Builder
       → Canonical Preview
       → Save Layout
   - Layout CSV becomes optional import/export only.

3. Upgrade the Canonical Layer.
   - Introduce Business Schema between Physical Schema and Canonical Schema.
   - Detection proposes mappings.
   - User confirms mappings.
   - Downstream layers consume only canonical business names.

4. Complete enterprise Quantity Resolution.
   - Support mixed Units + Weight datasets.
   - Rule:
         if weight > 0 use weight
         else if units > 0 use units
         else 0
   - Support row-level UOM, default UOM, conversions, missing values and zero-weight fallback.
   - Entire implementation must remain vectorized.

5. Expand Reporting.
   - Add summary worksheets derived only from validated outputs.
   - Include:
       Top/Bottom Stores
       Top/Bottom UPCs
       Category summaries
       Brand summaries
       Data quality metrics
       Performance metrics
       Validation metrics
   - Never re-read data for reporting.

6. Enforce a single execution pipeline:
       Connection
       → Detection
       → Canonical
       → Requirement
       → Operation
       → Processing
       → Validation
       → Output
       → Flush

   All workflows (Onboarding, Format Change, Existing Comparison, future workflows) must use this exact pipeline.

7. Perform repository cleanup.
   - Remove duplicate logic.
   - Remove dead code.
   - Remove unused imports.
   - Remove architecture bypasses.
   - Ensure every layer consumes only the contract produced by the previous layer.

8. Execute full regression testing using sample datasets.
   - Validate delimited, fixed-width, multiline, HDR, weighted quantity, and format change scenarios.
   - Generate:
       Architecture_Compliance_Report_RC2.md
       Detection_Completeness_Report_RC2.md
       Business_Logic_Report_RC2.md
       Production_Readiness_RC2.md

Constraints
-----------
- Preserve existing working functionality.
- Do not introduce breaking changes.
- Prefer refactoring over rewriting.
- Maintain streaming-first processing.
- Keep UI synchronized with architecture.
- Every major implementation must include tests and documentation updates.

Deliverable
-----------
RC2 should be a production-ready, architecture-compliant, enterprise retailer POS processing platform with a single execution pipeline and comprehensive validation, reporting, and documentation.

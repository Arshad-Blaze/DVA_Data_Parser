Goal

Avoid repeated aggregation during validation.

Current flow

1. Parse file.
2. Map columns.
3. Store-level validation performs aggregation.
4. Item-level validation performs another aggregation.

This causes duplicate computation.

Desired flow

1. Parse file.
2. Map columns.
3. Generate one reusable aggregation layer.
4. Cache:
   - Store aggregation - Group By "Store" Sum "UnitsSold" and "TotalDollars"
   - UPC + Description aggregation - Group By "UPC | DESCRIPTION GROUP KEY" Sum "UnitsSold" and "TotalDollars"
5. Store these in session state or a shared processing context.
6. Validation modules should consume the cached aggregations instead of recomputing them.

Requirements

- Do not change validation results.
- Do not duplicate aggregation logic.
- Keep UI unchanged.
- Make minimal code changes.
- Preserve existing architecture.

Deliverables

1. Explain affected files.
2. Implement.
3. Run tests.
4. Summarize changes.

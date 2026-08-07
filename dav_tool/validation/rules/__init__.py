"""Validation rules — rule-driven validation.

Every rule is a pure function over an AggregatedDataset.  Rules never call
reporting, never parse, and never aggregate.
"""

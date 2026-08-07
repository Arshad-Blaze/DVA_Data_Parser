"""Concrete pipeline stages.

Each stage maps 1:1 to the target architecture:

    Connection Stage → Discovery Stage → Dataset Graph Stage →
    Transformation Planning Stage → Parser Pipeline Stage →
    Canonical Dataset Stage → Aggregation Stage → Validation Stage →
    Reporting Stage

Stages live in separate modules so the registry can compose them
independently.
"""

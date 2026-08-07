"""Pipeline Layer — the target architecture for DVA Platform.

The pipeline layer replaces the workflow-driven application with a
pipeline-driven data processing platform.  Every retailer runs through
the identical stage sequence; only the *pipeline* selected for a given
DiscoveryResult differs.

Architecture:

    Bootstrap
      ↓
    Workflow Engine
      ↓
    Pipeline Registry
      ↓
    Pipeline Context
      ↓
    Connection Stage → Discovery Stage → Dataset Graph Stage →
    Transformation Planning Stage → Parser Pipeline Stage →
    Canonical Dataset Stage → Aggregation Stage → Validation Stage →
    Reporting Stage → Downloads

Rules:
- Each stage owns exactly one responsibility.
- Each stage receives one contract and returns one contract.
- No stage accesses Streamlit.
- No downstream stage performs upstream work.
- Contracts are immutable dataclasses.
"""

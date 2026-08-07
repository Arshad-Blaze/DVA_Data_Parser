"""Register the built-in validation rules into the default registry.

Called once by Bootstrap.  Rules are the standard set plus configurable
tolerance.
"""
from __future__ import annotations

from .difference import ItemDifferenceRule, StoreDifferenceRule, UPCDifferenceRule
from .integrity import (
    DuplicateUPCRule,
    MissingStoreRule,
    MissingUPCRule,
    NegativeSalesRule,
    WeightValidationRule,
)
from .registry import RuleRegistry
from .tolerance import ToleranceRule


def register_standard_rules(registry: RuleRegistry, tolerance_pct: float = 5.0) -> None:
    """Register the standard rule set on *registry*."""
    registry.register(StoreDifferenceRule())
    registry.register(ItemDifferenceRule())
    registry.register(UPCDifferenceRule())
    registry.register(DuplicateUPCRule())
    registry.register(MissingStoreRule())
    registry.register(MissingUPCRule())
    registry.register(NegativeSalesRule())
    registry.register(WeightValidationRule())
    registry.register(ToleranceRule(tolerance_pct=tolerance_pct))

"""Schema Comparison Service — compares BAU vs Test column schemas.

Pure logic, no Streamlit, no UI. Returns a ``SchemaDiff`` dataclass.
"""
from dataclasses import dataclass, field
from typing import List, Set, Optional


@dataclass
class SchemaDiff:
    common: Set[str] = field(default_factory=set)
    only_prod: Set[str] = field(default_factory=set)
    only_test: Set[str] = field(default_factory=set)
    prod_count: int = 0
    test_count: int = 0

    @property
    def identical(self) -> bool:
        return not self.only_prod and not self.only_test

    @property
    def summary(self) -> str:
        if self.identical:
            return "Schemas match exactly."
        parts = []
        if self.only_prod:
            parts.append(f"{len(self.only_prod)} column(s) only in BAU")
        if self.only_test:
            parts.append(f"{len(self.only_test)} column(s) only in Test")
        return "; ".join(parts)


def compare_schemas(
    prod_cols: Optional[List[str]],
    test_cols: Optional[List[str]],
) -> SchemaDiff:
    """Compare BAU and Test column schemas.

    Args:
        prod_cols: BAU column names (canonical or physical).
        test_cols: Test column names (canonical or physical).

    Returns:
        SchemaDiff with common / only-prod / only-test sets.
    """
    prod_set = set(prod_cols or [])
    test_set = set(test_cols or [])
    return SchemaDiff(
        common=prod_set & test_set,
        only_prod=prod_set - test_set,
        only_test=test_set - prod_set,
        prod_count=len(prod_set),
        test_count=len(test_set),
    )

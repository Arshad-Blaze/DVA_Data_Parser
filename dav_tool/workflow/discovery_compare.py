"""Discovery Comparison Service — compares BAU vs Test discovery results.

Pure logic, no Streamlit, no UI.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class DiscoveryComparison:
    prod_file_type: Optional[str] = None
    test_file_type: Optional[str] = None
    prod_delimiter: Optional[str] = None
    test_delimiter: Optional[str] = None
    prod_columns: List[str] = field(default_factory=list)
    test_columns: List[str] = field(default_factory=list)

    @property
    def same_type(self) -> bool:
        return self.prod_file_type == self.test_file_type

    @property
    def same_delimiter(self) -> bool:
        return self.prod_delimiter == self.test_delimiter

    @property
    def same_col_count(self) -> bool:
        return len(self.prod_columns) == len(self.test_columns)

    @property
    def identical_columns(self) -> bool:
        return self.same_col_count and self.prod_columns == self.test_columns

    @property
    def only_prod(self) -> Set[str]:
        return set(self.prod_columns) - set(self.test_columns)

    @property
    def only_test(self) -> Set[str]:
        return set(self.test_columns) - set(self.prod_columns)


def compare_discovery(prod_ctx, test_ctx) -> DiscoveryComparison:
    """Compare discovery results between BAU and Test contexts.

    Args:
        prod_ctx: ProcessingContext for BAU side.
        test_ctx: ProcessingContext for Test side.

    Returns:
        DiscoveryComparison with metadata comparisons.
    """
    return DiscoveryComparison(
        prod_file_type=getattr(prod_ctx, 'file_type', None),
        test_file_type=getattr(test_ctx, 'file_type', None),
        prod_delimiter=getattr(prod_ctx, 'delimiter', None),
        test_delimiter=getattr(test_ctx, 'delimiter', None),
        prod_columns=getattr(prod_ctx, 'columns', None) or [],
        test_columns=getattr(test_ctx, 'columns', None) or [],
    )

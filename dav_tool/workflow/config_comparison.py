"""Configuration Comparison Service — compares BAU vs Test configuration settings.

Pure logic, no Streamlit, no UI.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ConfigComparison:
    prod_file_type: Optional[str] = None
    test_file_type: Optional[str] = None
    prod_delimiter: Optional[str] = None
    test_delimiter: Optional[str] = None
    prod_store_col: Optional[str] = None
    test_store_col: Optional[str] = None
    prod_upc_col: Optional[str] = None
    test_upc_col: Optional[str] = None
    prod_desc_col: Optional[str] = None
    test_desc_col: Optional[str] = None
    prod_units_col: Optional[str] = None
    test_units_col: Optional[str] = None
    prod_price_col: Optional[str] = None
    test_price_col: Optional[str] = None
    prod_quantity_type: str = "units"
    test_quantity_type: str = "units"
    prod_col_count: int = 0
    test_col_count: int = 0
    diffs: List[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return len(self.diffs) == 0


def compare_configs(prod_cfg, test_cfg) -> ConfigComparison:
    """Compare configuration settings between BAU and Test.

    Args:
        prod_cfg: FormatConfig or object with config attributes for BAU.
        test_cfg: FormatConfig or object with config attributes for Test.

    Returns:
        ConfigComparison with differences listed in ``diffs``.
    """
    result = ConfigComparison(
        prod_file_type=getattr(prod_cfg, 'file_type', None),
        test_file_type=getattr(test_cfg, 'file_type', None),
        prod_delimiter=getattr(prod_cfg, 'delimiter', None),
        test_delimiter=getattr(test_cfg, 'delimiter', None),
        prod_store_col=getattr(prod_cfg, 'store_col', None),
        test_store_col=getattr(test_cfg, 'store_col', None),
        prod_upc_col=getattr(prod_cfg, 'upc_col', None),
        test_upc_col=getattr(test_cfg, 'upc_col', None),
        prod_desc_col=getattr(prod_cfg, 'desc_col', None),
        test_desc_col=getattr(test_cfg, 'desc_col', None),
        prod_units_col=getattr(prod_cfg, 'units_col', None),
        test_units_col=getattr(test_cfg, 'units_col', None),
        prod_price_col=getattr(prod_cfg, 'price_col', None),
        test_price_col=getattr(test_cfg, 'price_col', None),
        prod_quantity_type=getattr(prod_cfg, 'quantity_type', 'units'),
        test_quantity_type=getattr(test_cfg, 'quantity_type', 'units'),
        prod_col_count=len(getattr(prod_cfg, 'columns', None) or []),
        test_col_count=len(getattr(test_cfg, 'columns', None) or []),
    )

    if result.prod_file_type != result.test_file_type:
        result.diffs.append(
            f"File type: BAU={result.prod_file_type} vs Test={result.test_file_type}"
        )
    if result.prod_delimiter != result.test_delimiter:
        result.diffs.append(
            f"Delimiter: BAU={result.prod_delimiter} vs Test={result.test_delimiter}"
        )
    if result.prod_store_col != result.test_store_col:
        result.diffs.append(
            f"Store column: BAU={result.prod_store_col} vs Test={result.test_store_col}"
        )
    if result.prod_upc_col != result.test_upc_col:
        result.diffs.append(
            f"UPC column: BAU={result.prod_upc_col} vs Test={result.test_upc_col}"
        )
    if result.prod_quantity_type != result.test_quantity_type:
        result.diffs.append(
            f"Quantity type: BAU={result.prod_quantity_type} vs Test={result.test_quantity_type}"
        )
    return result

"""Canonical Schema — the platform's target column names and alias matching.

Every retailer's physical columns are mapped into the canonical fields below.
No downstream layer (aggregation, validation, insights, reporting) ever
references retailer column names.

The platform defines 14 canonical fields.  A retailer's dataset may provide
only a subset; unmapped fields are simply absent from the canonical output.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

#: The platform canonical schema (target column names).
CANONICAL_FIELDS: List[str] = [
    "STORE_NUMBER",
    "UPC_CODE",
    "PRODUCT_DESCRIPTION",
    "TRANSACTION_DATE",
    "UNITS_SOLD",
    "WEIGHT_QTY",
    "WEIGHT_UOM",
    "TOTAL_DOLLARS",
    "CATEGORY",
    "BRAND",
    "DEPARTMENT",
    "STORE_NAME",
    "ITEM_SIZE",
    "ITEM_UOM",
]

#: Known retailer spellings for each canonical field (uppercase, normalized).
CANONICAL_ALIASES: Dict[str, List[str]] = {
    "STORE_NUMBER": [
        "STORE", "STORE#", "STORE NO", "STORE NUMBER", "STORENUMBER",
        "STORE_ID", "STOREID", "STORE_CODE", "STR#", "LOC", "LOCATION",
        "LOCATION_ID", "SITE", "SITE_ID",
    ],
    "UPC_CODE": [
        "UPC", "UPCCODE", "UPC CODE", "ITEM", "ITEM_CODE", "ITEMCODE",
        "ITEM_ID", "ITEMID", "SKU", "PLU", "BARCODE", "EAN", "PRODUCT_CODE",
        "PRODUCT_ID", "PRODUCTCODE",
    ],
    "PRODUCT_DESCRIPTION": [
        "DESCRIPTION", "DESC", "ITEM_DESC", "ITEM_DESCRIPTION", "PRODUCT",
        "PRODUCT_NAME", "PRODUCT_DESCR", "NAME", "ITEMNAME", "ITEM_NAME",
    ],
    "TRANSACTION_DATE": [
        "DATE", "TXN_DATE", "TRANSACTIONDATE", "SALE_DATE", "SALEDATE",
        "DATE_SOLD", "BUSINESS_DATE", "INVOICE_DATE", "SALES_DATE", "TXDATE",
    ],
    "UNITS_SOLD": [
        "UNITS", "UNIT", "UNITS_SOLD", "QTY", "QUANTITY", "QTY_SOLD",
        "SALES_QTY", "UNITSSOLD", "COUNT", "PCS", "EACH", "UNITSOLD",
        "SOLD_QTY", "UNIT_QTY",
    ],
    "WEIGHT_QTY": [
        "WEIGHT", "WEIGHT_QTY", "WEIGHTQTY", "LBS", "GROSS_WEIGHT",
        "SCALE_WEIGHT", "WEIGHT_UNITS", "WQTY", "WEIGHTED_QTY", "WT_QTY",
    ],
    "WEIGHT_UOM": [
        "UOM", "WEIGHT_UOM", "WEIGHTUOM", "UNIT_OF_MEASURE", "WEIGHT_UNIT",
        "UNITS_UOM", "MU", "UOM_CODE", "WEIGHT_UNITS_UOM",
    ],
    "TOTAL_DOLLARS": [
        "PRICE", "TOTALPRICE", "TOTAL_PRICE", "AMOUNT", "SALES", "DOLLARS",
        "TOTAL_DOLLARS", "REVENUE", "SALE_AMOUNT", "EXTENDED_PRICE",
        "EXT_AMOUNT", "SALES_AMOUNT", "AMT", "NET_SALES", "GROSS_SALES",
    ],
    "CATEGORY": [
        "CATEGORY", "CAT", "CATEGORY_DESC", "CATEGORY_NAME", "CLASS",
        "PRODUCT_CATEGORY", "CATEGORY_CODE",
    ],
    "BRAND": [
        "BRAND", "BRAND_NAME", "BRAND_DESC", "MANUFACTURER", "VENDOR",
        "PRODUCT_BRAND", "BRAND_CODE",
    ],
    "DEPARTMENT": [
        "DEPARTMENT", "DEPT", "DEPT#", "DEPARTMENT_DESC", "DIVISION",
        "DEPARTMENT_NAME", "DEPT_NAME", "DEPARTMENT_CODE",
    ],
    "STORE_NAME": [
        "STORE_NAME", "STORENAME", "STORE_DESC", "STORE_DESCRIPTION",
        "LOCATION_NAME", "STORE_DESCR",
    ],
    "ITEM_SIZE": [
        "SIZE", "ITEM_SIZE", "PACK_SIZE", "SIZE_VALUE", "SIZE_QTY",
        "ITEM_PACK_SIZE",
    ],
    "ITEM_UOM": [
        "SIZE_UOM", "ITEM_UOM", "PACK_UOM", "UNIT_UOM", "SIZE_UNIT",
    ],
}

#: Canonical field ↔ operational role used by the canonical stream.
#: ``role`` is the argument name passed to ``canonical_chunk_stream``.
ROLE_BY_CANONICAL: Dict[str, str] = {
    "STORE_NUMBER": "store_col",
    "UPC_CODE": "upc_col",
    "PRODUCT_DESCRIPTION": "desc_col",
    "TRANSACTION_DATE": "date_col",
    "UNITS_SOLD": "units_col",
    "WEIGHT_QTY": "weight_qty_col",
    "WEIGHT_UOM": "weight_uom_col",
    "TOTAL_DOLLARS": "price_col",
}

#: Canonical fields that are directly selectable from a physical column
#: (no special numeric/date handling in the canonical stream).
PLAIN_FIELDS: List[str] = [
    "CATEGORY", "BRAND", "DEPARTMENT", "STORE_NAME", "ITEM_SIZE", "ITEM_UOM",
]

_NORMALIZE_RE = re.compile(r"[^a-z0-9]")


def _norm(name: str) -> str:
    return _NORMALIZE_RE.sub("", (name or "").lower())


def alias_set(canonical: str) -> set:
    """Normalized set of aliases (including the canonical name) for a field."""
    out = {_norm(canonical)}
    for alias in CANONICAL_ALIASES.get(canonical, ()):
        out.add(_norm(alias))
    return out


def match_canonical(
    physical: str,
    canonical: str,
    suggestions: Optional[Dict[str, str]] = None,
) -> float:
    """Confidence (0.0–1.0) that *physical* maps to *canonical*.

    Exact normalized match → 1.0; equal ignoring punctuation → 0.95;
    canonical-vs-alias → 0.85; substring containment → 0.7; else 0.0.
    """
    p = _norm(physical)
    if not p:
        return 0.0
    c = _norm(canonical)
    if p == c:
        return 1.0
    if c in p or p in c:
        return 0.7
    aliases = CANONICAL_ALIASES.get(canonical, ())
    for alias in aliases:
        a = _norm(alias)
        if a == p:
            return 0.85
        if a in p or p in a:
            return 0.7
    return 0.0


def best_match(
    physical_columns: Sequence[str],
    canonical: str,
    suggestions: Optional[Dict[str, str]] = None,
) -> tuple:
    """Return ``(physical, confidence)`` for the best *canonical* match."""
    if suggestions:
        sug = (suggestions or {}).get(canonical)
        if sug and sug in list(physical_columns):
            return sug, 1.0
    best_phys, best_conf = None, 0.0
    for col in physical_columns:
        conf = match_canonical(col, canonical)
        if conf > best_conf:
            best_phys, best_conf = col, conf
    return best_phys, best_conf

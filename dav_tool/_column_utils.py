"""Column detection utilities — pure functions with no UI dependency.

Extracted from ``dav_tool.ui.helpers`` to allow workflow and config
layers to use column detection without importing Streamlit.
"""

COLUMN_SYNONYMS = {
    "Store": [
        "store", "store number", "store_id", "store id",
        "store code", "store_code", "store_number", "store num",
        "location", "location code",
    ],
    "UPC": [
        "upc", "upc_code", "upc code", "item upc", "item_upc",
        "upc number", "upc_number", "barcode", "upc12", "gtin",
        "ean", "product code",
    ],
    "Description": [
        "description", "desc", "item description", "item_description",
        "product description", "product_description", "product name",
        "item name", "name", "description of goods",
    ],
    "Units": [
        "units", "qty", "quantity", "sold", "units sold",
        "units_sold", "quantity sold", "sales quantity", "qty sold",
        "unit sold", "sale quantity",
    ],
    "Price": [
        "price", "total price", "total_price", "sales", "amount",
        "dollars", "total dollars", "total_dollars", "revenue",
        "total revenue", "selling price", "sales amount",
        "sale price", "price sold",
    ],
}


def find_best_column_index(cols, target, synonyms):
    if not cols:
        return -1
    col_lower = [c.lower().strip() for c in cols]
    target_lower = target.lower()

    if target_lower in col_lower:
        return col_lower.index(target_lower)

    for syn in synonyms:
        syn_lower = syn.lower()
        if syn_lower in col_lower:
            return col_lower.index(syn_lower)

    for i, col in enumerate(col_lower):
        for syn in synonyms:
            syn_lower = syn.lower()
            if syn_lower in col or col in syn_lower:
                return i

    for i, col in enumerate(col_lower):
        if target_lower in col or col in target_lower:
            return i

    return -1


def smart_column_indices(cols):
    indices = {}
    for target, synonyms in COLUMN_SYNONYMS.items():
        idx = find_best_column_index(cols, target, synonyms)
        key = target.lower()
        if 0 <= idx < len(cols):
            indices[key] = (idx, cols[idx])
        else:
            indices[key] = (None, None)
    return indices

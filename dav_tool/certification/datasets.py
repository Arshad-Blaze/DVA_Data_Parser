"""Generate representative retailer datasets for certification.

Creates BAU/TEST pairs with expected outputs in retailer_certification/.
Each dataset includes: BAU/, TEST/, Config/, expected/, Layout/ (if needed).
"""
import csv
import json
import os
from typing import Optional

ROWS = [
    ("S001", "100001", "Widget A", "10", "99.90"),
    ("S001", "100002", "Gadget B", "5", "49.95"),
    ("S002", "100001", "Widget A", "8", "79.92"),
    ("S003", "100003", "Doohickey", "20", "199.80"),
]

ROWS_TEST = [
    ("S001", "100001", "Widget A", "12", "119.88"),
    ("S001", "100002", "Gadget B", "5", "49.95"),
    ("S002", "100001", "Widget A", "8", "79.92"),
    ("S003", "100003", "Doohickey", "20", "199.80"),
    ("S004", "100004", "NewItem", "7", "69.93"),
]


def write_csv(path: str, rows, delimiter: str = ","):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(["Store", "UPC", "Description", "Units", "Price"])
        for row in rows:
            w.writerow(row)
    return path


def write_config(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def write_docs(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


def generate_retailer_grocery(root: str):
    """Standard comma-delimited CSV — baseline retailer."""
    base = os.path.join(root, "delimited", "retailer_grocery")
    write_csv(os.path.join(base, "BAU", "sales.csv"), ROWS)
    write_csv(os.path.join(base, "TEST", "sales.csv"), ROWS_TEST)
    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Grocery",
        "file_type": "delimited",
        "delimiter": ",",
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Grocery\n\nStandard comma-delimited POS data.\n"
               "4 stores BAU, 5 stores TEST (S004 added).\n"
               "Testing: basic column mapping, store comparison.\n")


def generate_retailer_pharmacy(root: str):
    """Tab-delimited — different delimiter."""
    base = os.path.join(root, "delimited", "retailer_pharmacy")
    write_csv(os.path.join(base, "BAU", "rx_data.csv"), ROWS, delimiter="\t")
    write_csv(os.path.join(base, "TEST", "rx_data.csv"), ROWS_TEST, delimiter="\t")
    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Pharmacy",
        "file_type": "delimited",
        "delimiter": "\t",
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Pharmacy\n\nTab-delimited POS data.\n"
               "Testing: non-comma delimiter detection.\n")


def generate_retailer_wholesale(root: str):
    """Pipe-delimited multiline with H/D record types."""
    base = os.path.join(root, "multiline", "retailer_wholesale")
    bau_path = os.path.join(base, "BAU", "wholesale.txt")
    test_path = os.path.join(base, "TEST", "wholesale.txt")
    os.makedirs(os.path.dirname(bau_path), exist_ok=True)
    os.makedirs(os.path.dirname(test_path), exist_ok=True)

    with open(bau_path, "w") as f:
        for store, upc, desc, units, price in ROWS:
            f.write(f"H|{store}|2024-01-15\n")
            f.write(f"D|{store}|{upc}|{desc}|{units}|{price}\n")

    with open(test_path, "w") as f:
        for store, upc, desc, units, price in ROWS_TEST:
            f.write(f"H|{store}|2024-01-15\n")
            f.write(f"D|{store}|{upc}|{desc}|{units}|{price}\n")

    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Wholesale",
        "file_type": "multiline",
        "ml_record_types": ["H", "D"],
        "ml_delimiter": "|",
        "canonical_schema": ["Store", "UPC", "Description", "Units", "Price"],
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Wholesale\n\nPipe-delimited multiline (H/D record types).\n"
               "Testing: multiline record detection and flattening.\n")


def generate_retailer_apparel(root: str):
    """HDR fixed-width with header/detail/trailer."""
    base = os.path.join(root, "header_detail", "retailer_apparel")
    layout_dir = os.path.join(base, "Layout")
    os.makedirs(layout_dir, exist_ok=True)

    header_layout_path = os.path.join(layout_dir, "header_layout.csv")
    with open(header_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["4", "5", "Store", "text"])
        w.writerow(["12", "8", "Date", "text"])

    detail_layout_path = os.path.join(layout_dir, "detail_layout.csv")
    with open(detail_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["1", "12", "UPC", "text"])
        w.writerow(["13", "21", "Description", "text"])
        w.writerow(["34", "2", "Units", "numeric"])
        w.writerow(["36", "8", "Price", "numeric"])

    trailer_layout_path = os.path.join(layout_dir, "trailer_layout.csv")
    with open(trailer_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["4", "5", "TotalUnits", "numeric"])
        w.writerow(["10", "9", "TotalPrice", "numeric"])

    def hdr_header(store, seq, date):
        return f"HDR{seq:02d}{store:<4}   {date}\n"

    def hdr_detail(upc, desc, units, price):
        return f"{upc:<12}{desc:<21}{units:>2}{price:>8}     \n"

    def hdr_trailer(total_units, total_price):
        return f"TRL{total_units:>5}{total_price:>9}\n"

    bau_path = os.path.join(base, "BAU", "apparel.txt")
    os.makedirs(os.path.dirname(bau_path), exist_ok=True)
    with open(bau_path, "w") as f:
        stores = {}
        for store, upc, desc, units, price in ROWS:
            if store not in stores:
                stores[store] = []
            stores[store].append((upc, desc, units, price))
        for seq, (store, items) in enumerate(stores.items(), 1):
            f.write(hdr_header(store, seq, "2024-01-15"))
            for upc, desc, units, price in items:
                f.write(hdr_detail(upc, desc, units, price))
            total_units = sum(int(u) for _, _, u, _ in items)
            total_price = sum(float(p) for _, _, _, p in items)
            f.write(hdr_trailer(total_units, f"{total_price:.2f}"))

    test_path = os.path.join(base, "TEST", "apparel.txt")
    os.makedirs(os.path.dirname(test_path), exist_ok=True)
    stores_test = {}
    for store, upc, desc, units, price in ROWS_TEST:
        if store not in stores_test:
            stores_test[store] = []
        stores_test[store].append((upc, desc, units, price))
    with open(test_path, "w") as f:
        for seq, (store, items) in enumerate(stores_test.items(), 1):
            f.write(hdr_header(store, seq, "2024-01-15"))
            for upc, desc, units, price in items:
                f.write(hdr_detail(upc, desc, units, price))
            total_units = sum(int(u) for _, _, u, _ in items)
            total_price = sum(float(p) for _, _, _, p in items)
            f.write(hdr_trailer(total_units, f"{total_price:.2f}"))

    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Apparel",
        "file_type": "multiline",
        "header_prefix": "HDR",
        "header_layout_file": header_layout_path,
        "detail_layout_file": detail_layout_path,
        "trailer_prefix": "TRL",
        "trailer_layout_file": trailer_layout_path,
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Apparel\n\nHDR fixed-width with header/detail/trailer.\n"
               "Testing: HDR detection, layout loading, trailer parsing.\n")


def generate_retailer_global(root: str):
    """Unicode-encoded CSV (UTF-8)."""
    base = os.path.join(root, "unicode", "retailer_global")
    os.makedirs(os.path.join(base, "BAU"), exist_ok=True)
    os.makedirs(os.path.join(base, "TEST"), exist_ok=True)

    bau_path = os.path.join(base, "BAU", "global.csv")
    with open(bau_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "UPC", "Description", "Units", "Price"])
        w.writerow(["S001", "100001", "Café", "10", "99.90"])
        w.writerow(["S002", "100002", "São Paulo", "5", "49.95"])

    test_path = os.path.join(base, "TEST", "global.csv")
    with open(test_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "UPC", "Description", "Units", "Price"])
        w.writerow(["S001", "100001", "Café", "12", "119.88"])
        w.writerow(["S002", "100002", "São Paulo", "5", "49.95"])
        w.writerow(["S003", "100003", "München", "8", "79.92"])

    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Global",
        "file_type": "delimited",
        "delimiter": ",",
        "encoding": "utf-8",
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Global\n\nUTF-8 encoded CSV with international characters.\n"
               "Testing: unicode encoding detection and handling.\n")


def generate_retailer_legacy(root: str):
    """Malformed/edge-case data (CP-1252 encoding)."""
    base = os.path.join(root, "malformed", "retailer_legacy")
    os.makedirs(os.path.join(base, "BAU"), exist_ok=True)
    os.makedirs(os.path.join(base, "TEST"), exist_ok=True)

    bau_path = os.path.join(base, "BAU", "legacy.csv")
    with open(bau_path, "w", encoding="cp1252", newline="") as f:
        f.write("Store,UPC,Description,Units,Price\n")
        f.write("S001,100001,Widget A,10,99.90\n")
        f.write("S001,100002,Gadget B,5,49.95\n")

    test_path = os.path.join(base, "TEST", "legacy.csv")
    with open(test_path, "w", encoding="cp1252", newline="") as f:
        f.write("Store,UPC,Description,Units,Price\n")
        f.write("S001,100001,Widget A,12,119.88\n")
        f.write("S001,100002,Gadget B,5,49.95\n")
        f.write("S002,100001,Widget A,8,79.92\n")

    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Legacy",
        "file_type": "delimited",
        "delimiter": ",",
        "encoding": "cp1252",
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Legacy\n\nCP-1252 encoded CSV (legacy system).\n"
               "Testing: alternative encoding detection and fallback.\n")


def generate_retailer_fixedwidth(root: str):
    """Fixed-width numeric layout."""
    base = os.path.join(root, "fixed_width", "retailer_pharmacy_fw")
    layout_dir = os.path.join(base, "Layout")
    os.makedirs(layout_dir, exist_ok=True)

    layout_path = os.path.join(layout_dir, "layout.csv")
    with open(layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["1", "6", "Store", "text"])
        w.writerow(["7", "10", "UPC", "numeric"])
        w.writerow(["17", "20", "Description", "text"])
        w.writerow(["37", "5", "Units", "numeric"])
        w.writerow(["42", "8", "Price", "numeric"])

    def fwf_row(store, upc, desc, units, price):
        return f"{store:<6}{upc:>10}{desc:<20}{units:>5}{price:>8}\n"

    bau_path = os.path.join(base, "BAU", "fixed.txt")
    os.makedirs(os.path.dirname(bau_path), exist_ok=True)
    with open(bau_path, "w") as f:
        for row in ROWS:
            f.write(fwf_row(*row))

    test_path = os.path.join(base, "TEST", "fixed.txt")
    os.makedirs(os.path.dirname(test_path), exist_ok=True)
    with open(test_path, "w") as f:
        for row in ROWS_TEST:
            f.write(fwf_row(*row))

    write_config(os.path.join(base, "Config", "config.json"), {
        "version": 1,
        "name": "Retailer Pharmacy FW",
        "file_type": "fixed",
        "layout_file": layout_path,
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "quantity_col": "Units",
        "price_col": "Price",
        "price_type": "Total Price",
    })
    write_docs(os.path.join(base, "Documentation", "README.md"),
               "# Retailer Pharmacy (Fixed-Width)\n\nFixed-width numeric layout.\n"
               "Testing: fixed-width parsing, layout loading, column detection.\n")


def generate_all(root: Optional[str] = None):
    if root is None:
        root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "retailer_certification",
        )
    generate_retailer_grocery(root)
    generate_retailer_pharmacy(root)
    generate_retailer_wholesale(root)
    generate_retailer_apparel(root)
    generate_retailer_global(root)
    generate_retailer_legacy(root)
    generate_retailer_fixedwidth(root)
    print(f"Datasets generated under {root}")


if __name__ == "__main__":
    generate_all()

import csv
import os
from typing import List, Tuple


def create_delimited_csv(
    directory: str,
    filename: str = "store.csv",
    rows: List[Tuple[str, str, str, str, str]] = None,
) -> str:
    if rows is None:
        rows = [
            ("S001", "100001", "Widget A", "10", "99.90"),
            ("S001", "100002", "Gadget B", "5", "49.95"),
            ("S002", "100001", "Widget A", "8", "79.92"),
            ("S003", "100003", "Doohickey", "20", "199.80"),
        ]
    path = os.path.join(directory, filename)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "UPC", "Description", "Units", "Price"])
        for row in rows:
            w.writerow(row)
    return path


def create_fixed_width_data(
    directory: str,
    filename: str = "fixed.txt",
    rows: List[Tuple[str, str, str, str, str]] = None,
) -> Tuple[str, str]:
    if rows is None:
        rows = [
            ("S001", "100001", "Widget A", "10", "99.90"),
            ("S001", "100002", "Gadget B", "5", "49.95"),
            ("S002", "100001", "Widget A", "8", "79.92"),
        ]

    layout_path = os.path.join(directory, "layout.csv")
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

    data_path = os.path.join(directory, filename)
    with open(data_path, "w") as f:
        for row in rows:
            f.write(fwf_row(*row))

    return data_path, layout_path


def create_multiline_delimited(directory: str, filename: str = "multiline.txt") -> str:
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        f.write("H|S001|2024-01-15\n")
        f.write("D|S001|100001|Widget A|10|99.90\n")
        f.write("D|S001|100002|Gadget B|5|49.95\n")
        f.write("H|S002|2024-01-15\n")
        f.write("D|S002|100001|Widget A|8|79.92\n")
    return path


def create_hdr_fixed_width(directory: str, filename: str = "hdr_fixed.txt") -> Tuple[str, str, str]:
    header_layout_path = os.path.join(directory, "hdr_header_layout.csv")
    with open(header_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["4", "5", "Store", "text"])
        w.writerow(["12", "8", "Date", "text"])

    detail_layout_path = os.path.join(directory, "hdr_detail_layout.csv")
    with open(detail_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["1", "12", "UPC", "text"])
        w.writerow(["13", "21", "Description", "text"])
        w.writerow(["34", "2", "Units", "numeric"])
        w.writerow(["36", "8", "Price", "numeric"])

    def hdr_header(store, date):
        return f"HDR{store:<5}   {date}\n"

    def hdr_detail(upc, desc, units, price):
        return f"{upc:<12}{desc:<21}{units:>2}{price:>8}     \n"

    data_path = os.path.join(directory, filename)
    with open(data_path, "w") as f:
        f.write(hdr_header("S001", "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "10", "99.90"))
        f.write(hdr_detail("100002", "Gadget B", "5", "49.95"))
        f.write(hdr_header("S002", "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "8", "79.92"))

    return data_path, header_layout_path, detail_layout_path


def create_config_test_data(directory: str) -> dict:
    """Creates test data files plus matching FormatConfig JSON files.

    Returns dict with paths to data dirs, data files, and config JSON files
    for delimited, multiline delimited, and HDR fixed-width formats.
    """
    import json

    # === Delimited ===
    delim_dir = os.path.join(directory, "delim")
    os.makedirs(delim_dir, exist_ok=True)
    delim_file = os.path.join(delim_dir, "data.csv")
    with open(delim_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store", "UPC", "Description", "Units", "Price"])
        w.writerow(["S001", "100001", "Widget A", "10", "99.90"])
        w.writerow(["S002", "100002", "Gadget B", "5", "49.95"])

    delim_config = {
        "version": 1,
        "name": "Delimited Test",
        "file_type": "delimited",
        "delimiter": ",",
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "units_col": "Units",
        "price_col": "Price",
    }
    delim_config_path = os.path.join(delim_dir, "config.json")
    with open(delim_config_path, "w") as f:
        json.dump(delim_config, f, indent=2)

    # === Multiline Delimited ===
    ml_dir = os.path.join(directory, "ml_delim")
    os.makedirs(ml_dir, exist_ok=True)
    ml_file = os.path.join(ml_dir, "ml_data.txt")
    with open(ml_file, "w") as f:
        f.write("H|S001|2024-01-15\n")
        f.write("D|S001|100001|Widget A|10|99.90\n")
        f.write("D|S001|100002|Gadget B|5|49.95\n")
        f.write("H|S002|2024-01-15\n")
        f.write("D|S002|100001|Widget A|8|79.92\n")

    ml_config = {
        "version": 1,
        "name": "ML Delimited Test",
        "file_type": "multiline",
        "ml_record_types": ["H", "D"],
        "ml_delimiter": "|",
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "units_col": "Units",
        "price_col": "Price",
    }
    ml_config_path = os.path.join(ml_dir, "config.json")
    with open(ml_config_path, "w") as f:
        json.dump(ml_config, f, indent=2)

    # === HDR Fixed-Width with Trailer ===
    hdr_dir = os.path.join(directory, "hdr_fixed")
    os.makedirs(hdr_dir, exist_ok=True)

    hdr_header_layout_path = os.path.join(hdr_dir, "hdr_header_layout.csv")
    with open(hdr_header_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["6", "4", "Store", "text"])
        w.writerow(["13", "8", "Date", "text"])

    hdr_detail_layout_path = os.path.join(hdr_dir, "hdr_detail_layout.csv")
    with open(hdr_detail_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["1", "12", "UPC", "text"])
        w.writerow(["13", "21", "Description", "text"])
        w.writerow(["34", "2", "Units", "numeric"])
        w.writerow(["36", "8", "Price", "numeric"])

    hdr_trailer_layout_path = os.path.join(hdr_dir, "hdr_trailer_layout.csv")
    with open(hdr_trailer_layout_path, "w", newline="") as f:
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

    hdr_file = os.path.join(hdr_dir, "hdr_data.txt")
    with open(hdr_file, "w") as f:
        f.write(hdr_header("S001", 1, "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "10", "99.90"))
        f.write(hdr_detail("100002", "Gadget B", "5", "49.95"))
        f.write(hdr_trailer("15", "149.85"))

    hdr_config = {
        "version": 1,
        "name": "HDR Fixed-Width Test",
        "file_type": "multiline",
        "header_prefix": "HDR",
        "header_layout_file": hdr_header_layout_path,
        "detail_layout_file": hdr_detail_layout_path,
        "trailer_prefix": "TRL",
        "trailer_layout_file": hdr_trailer_layout_path,
        "store_col": "Store",
        "upc_col": "UPC",
        "desc_col": "Description",
        "units_col": "Units",
        "price_col": "Price",
    }
    hdr_config_path = os.path.join(hdr_dir, "config.json")
    with open(hdr_config_path, "w") as f:
        json.dump(hdr_config, f, indent=2)

    return {
        "delim_dir": delim_dir,
        "delim_file": delim_file,
        "delim_config": delim_config_path,
        "ml_dir": ml_dir,
        "ml_file": ml_file,
        "ml_config": ml_config_path,
        "hdr_dir": hdr_dir,
        "hdr_file": hdr_file,
        "hdr_header_layout": hdr_header_layout_path,
        "hdr_detail_layout": hdr_detail_layout_path,
        "hdr_trailer_layout": hdr_trailer_layout_path,
        "hdr_config": hdr_config_path,
    }


def create_hdr_trailer_test_data(directory: str) -> dict:
    header_layout_path = os.path.join(directory, "trl_header_layout.csv")
    with open(header_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["6", "4", "Store", "text"])
        w.writerow(["13", "8", "Date", "text"])

    detail_layout_path = os.path.join(directory, "trl_detail_layout.csv")
    with open(detail_layout_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["From", "Length", "Field", "Type"])
        w.writerow(["1", "12", "UPC", "text"])
        w.writerow(["13", "21", "Description", "text"])
        w.writerow(["34", "2", "Units", "numeric"])
        w.writerow(["36", "8", "Price", "numeric"])

    trailer_layout_path = os.path.join(directory, "trl_trailer_layout.csv")
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

    # Onboarding: single dir with HDR + DTL + TRL
    onb_dir = os.path.join(directory, "onb_trl")
    os.makedirs(onb_dir, exist_ok=True)
    onb_file = os.path.join(onb_dir, "onb_trl_data.txt")
    with open(onb_file, "w") as f:
        f.write(hdr_header("S001", 1, "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "10", "99.90"))
        f.write(hdr_detail("100002", "Gadget B", "5", "49.95"))
        f.write(hdr_trailer("15", "149.85"))
        f.write(hdr_header("S002", 2, "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "8", "79.92"))
        f.write(hdr_trailer("8", "79.92"))

    # Existing: BAU and Test dirs
    bau_dir = os.path.join(directory, "bau_trl")
    os.makedirs(bau_dir, exist_ok=True)
    bau_file = os.path.join(bau_dir, "bau_trl_data.txt")
    with open(bau_file, "w") as f:
        f.write(hdr_header("S001", 1, "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "10", "99.90"))
        f.write(hdr_detail("100002", "Gadget B", "5", "49.95"))
        f.write(hdr_trailer("15", "149.85"))

    test_dir = os.path.join(directory, "test_trl")
    os.makedirs(test_dir, exist_ok=True)
    test_file = os.path.join(test_dir, "test_trl_data.txt")
    with open(test_file, "w") as f:
        f.write(hdr_header("S001", 1, "2024-01-15"))
        f.write(hdr_detail("100001", "Widget A", "12", "119.88"))
        f.write(hdr_detail("100002", "Gadget B", "5", "49.95"))
        f.write(hdr_trailer("17", "169.83"))

    return {
        "trl_data_dir": onb_dir,
        "trl_data_file": onb_file,
        "trl_header_layout": header_layout_path,
        "trl_detail_layout": detail_layout_path,
        "trl_trailer_layout": trailer_layout_path,
        "bau_trl_dir": bau_dir,
        "bau_trl_file": bau_file,
        "test_trl_dir": test_dir,
        "test_trl_file": test_file,
    }


def create_multiline_flow_test_data(directory: str) -> dict:
    bau_dir = os.path.join(directory, "bau_ml")
    os.makedirs(bau_dir, exist_ok=True)
    bau_file = create_multiline_delimited(bau_dir, "bau_multiline.txt")

    test_dir = os.path.join(directory, "test_ml")
    os.makedirs(test_dir, exist_ok=True)
    test_path = os.path.join(test_dir, "test_multiline.txt")
    with open(test_path, "w") as f:
        f.write("H|S001|2024-01-15\n")
        f.write("D|S001|100001|Widget A|12|119.88\n")
        f.write("D|S001|100002|Gadget B|5|49.95\n")
        f.write("H|S002|2024-01-15\n")
        f.write("D|S002|100001|Widget A|8|79.92\n")
        f.write("H|S003|2024-01-16\n")
        f.write("D|S003|100003|Doohickey|20|199.80\n")
        f.write("H|S004|2024-01-16\n")
        f.write("D|S004|100004|NewItem|7|69.93\n")

    storelist_path = os.path.join(directory, "storelist_ml.csv")
    with open(storelist_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store"])
        w.writerow(["S001"])
        w.writerow(["S002"])
        w.writerow(["S003"])
        w.writerow(["S004"])

    onb_dir = os.path.join(directory, "onboarding_ml")
    os.makedirs(onb_dir, exist_ok=True)
    onb_file = create_multiline_delimited(onb_dir, "onb_multiline.txt")

    return {
        "bau_ml_dir": bau_dir,
        "bau_ml_file": bau_file,
        "test_ml_dir": test_dir,
        "test_ml_file": test_path,
        "onboarding_ml_dir": onb_dir,
        "onboarding_ml_file": onb_file,
        "storelist_ml_path": storelist_path,
    }


def create_flow_test_data(directory: str) -> dict:
    bau_dir = os.path.join(directory, "bau")
    os.makedirs(bau_dir, exist_ok=True)
    bau_file = create_delimited_csv(bau_dir, "bau_data.csv")

    test_dir = os.path.join(directory, "test")
    os.makedirs(test_dir, exist_ok=True)
    test_file = create_delimited_csv(
        test_dir, "test_data.csv",
        rows=[
            ("S001", "100001", "Widget A", "12", "119.88"),
            ("S001", "100002", "Gadget B", "5", "49.95"),
            ("S002", "100001", "Widget A", "8", "79.92"),
            ("S003", "100003", "Doohickey", "20", "199.80"),
            ("S004", "100004", "NewItem", "7", "69.93"),
        ],
    )

    storelist_path = os.path.join(directory, "storelist.csv")
    with open(storelist_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Store"])
        w.writerow(["S001"])
        w.writerow(["S002"])
        w.writerow(["S003"])
        w.writerow(["S004"])

    onb_dir = os.path.join(directory, "onboarding")
    os.makedirs(onb_dir, exist_ok=True)
    onb_file = create_delimited_csv(onb_dir, "onb_data.csv")

    fw_dir = os.path.join(directory, "fixedwidth")
    os.makedirs(fw_dir, exist_ok=True)
    fw_file, fw_layout = create_fixed_width_data(fw_dir, "fixed_data.txt")

    return {
        "bau_dir": bau_dir,
        "bau_file": bau_file,
        "test_dir": test_dir,
        "test_file": test_file,
        "onboarding_dir": onb_dir,
        "onboarding_file": onb_file,
        "storelist_path": storelist_path,
        "fixedwidth_dir": fw_dir,
        "fixedwidth_file": fw_file,
        "fixedwidth_layout": fw_layout,
    }

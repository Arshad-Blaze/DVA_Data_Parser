"""
Comprehensive test: delimited, fixed-width, multiline (delimited + fixed-width).
Single file + multiple files for each type, plus file review report.
"""
import os, csv, tempfile
import polars as pl
from dav_tool._aggregators import (
    stream_store_aggregate,
    stream_item_aggregate,
    stream_upc_summary,
    generate_file_review,
)
from dav_tool._parsers import load_layout

OUT = "/tmp/dav_test_results"
os.makedirs(OUT, exist_ok=True)
results = []

def report(name, df):
    results.append(f"\n{'='*60}")
    results.append(f"  {name}")
    results.append(f"{'='*60}")
    if df is not None and not df.is_empty():
        results.append(str(df))
    else:
        results.append("  (empty)")

# ============================================================
# 1. DELIMITED — single file
# ============================================================
TMP = tempfile.mkdtemp()
csv1 = os.path.join(TMP, "store1.csv")
with open(csv1, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Store","UPC","Description","Units","Price"])
    w.writerow(["S001","100001","Widget A","10","99.90"])
    w.writerow(["S001","100002","Gadget B","5","49.95"])
    w.writerow(["S002","100001","Widget A","8","79.92"])
    w.writerow(["S003","100003","Doohickey","20","199.80"])

report("DELIMITED SINGLE FILE — Store Validation",
    stream_store_aggregate([csv1],"delimited","Store","Units","Price",delimiter=","))
report("DELIMITED SINGLE FILE — Item Validation",
    stream_item_aggregate([csv1],"delimited","UPC","Description","Units","Price",delimiter=","))

# ============================================================
# 2. DELIMITED — multiple files
# ============================================================
csv2 = os.path.join(TMP, "store2.csv")
with open(csv2, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Store","UPC","Description","Units","Price"])
    w.writerow(["S002","100004","New Item","3","29.97"])
    w.writerow(["S003","100001","Widget A","12","119.88"])
    w.writerow(["S004","100005","Extra","7","69.93"])

report("DELIMITED MULTI-FILE — Store Validation",
    stream_store_aggregate([csv1,csv2],"delimited","Store","Units","Price",delimiter=","))
report("DELIMITED MULTI-FILE — Item Validation",
    stream_item_aggregate([csv1,csv2],"delimited","UPC","Description","Units","Price",delimiter=","))
report("DELIMITED MULTI-FILE — UPC Summary",
    stream_upc_summary([csv1,csv2],"delimited","UPC","Units","Price",delimiter=","))

# ============================================================
# 3. FIXED-WIDTH — single file
# ============================================================
layout_csv = os.path.join(TMP, "layout.csv")
with open(layout_csv, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["From","Length","Field","Type"])
    w.writerow(["1","6","Store","text"])
    w.writerow(["7","10","UPC","numeric"])
    w.writerow(["17","20","Description","text"])
    w.writerow(["37","5","Units","numeric"])
    w.writerow(["42","8","Price","numeric"])

layout = load_layout(layout_csv)

def fwf_row(store, upc, desc, units, price):
    # Pad each field exactly to its layout width: Store(6), UPC(10), Description(20), Units(5), Price(8)
    return f"{store:<6}{upc:>10}{desc:<20}{units:>5}{price:>8}\n"

fwf1 = os.path.join(TMP, "fixed1.txt")
with open(fwf1, "w") as f:
    f.write(fwf_row("S001", "100001", "Widget A", "10", "99.90"))
    f.write(fwf_row("S001", "100002", "Gadget B", "5", "49.95"))
    f.write(fwf_row("S002", "100001", "Widget A", "8", "79.92"))

report("FIXED-WIDTH SINGLE FILE — Store Validation",
    stream_store_aggregate([fwf1],"fixed","Store","Units","Price",layout=layout))
report("FIXED-WIDTH SINGLE FILE — Item Validation",
    stream_item_aggregate([fwf1],"fixed","UPC","Description","Units","Price",layout=layout))

# ============================================================
# 4. FIXED-WIDTH — multiple files
# ============================================================
fwf2 = os.path.join(TMP, "fixed2.txt")
with open(fwf2, "w") as f:
    f.write(fwf_row("S003", "100003", "Doohickey", "20", "199.80"))
    f.write(fwf_row("S002", "100004", "New Item", "3", "29.97"))

report("FIXED-WIDTH MULTI-FILE — Store Validation",
    stream_store_aggregate([fwf1,fwf2],"fixed","Store","Units","Price",layout=layout))
report("FIXED-WIDTH MULTI-FILE — UPC Summary",
    stream_upc_summary([fwf1,fwf2],"fixed","UPC","Units","Price",layout=layout))

# ============================================================
# 5. MULTILINE DELIMITED (HDR) — single file
# ============================================================
mld1 = os.path.join(TMP, "multiline_delimited1.txt")
with open(mld1, "w") as f:
    f.write("H|S001|2024-01-15\n")
    f.write("D|S001|100001|Widget A|10|99.90\n")
    f.write("D|S001|100002|Gadget B|5|49.95\n")
    f.write("H|S002|2024-01-15\n")
    f.write("D|S002|100001|Widget A|8|79.92\n")

# D-record schema: [Store,UPC,Description,Units,Price]
ml_d_cols = ["Store","UPC","Description","Units","Price"]
report("MULTILINE DELIMITED SINGLE — Store Validation (D records)",
    stream_store_aggregate(
        [mld1],"multiline","Store","Units","Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_d_cols))
report("MULTILINE DELIMITED SINGLE — Item Validation (D records)",
    stream_item_aggregate(
        [mld1],"multiline","UPC","Description","Units","Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_d_cols))
report("MULTILINE DELIMITED SINGLE — UPC Summary (D records)",
    stream_upc_summary(
        [mld1],"multiline","UPC","Units","Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_d_cols))

# ============================================================
# 6. MULTILINE DELIMITED — multiple files
# ============================================================
mld2 = os.path.join(TMP, "multiline_delimited2.txt")
with open(mld2, "w") as f:
    f.write("H|S003|2024-01-16\n")
    f.write("D|S003|100003|Doohickey|20|199.80\n")
    f.write("D|S004|100004|New Item|3|29.97\n")

report("MULTILINE DELIMITED MULTI-FILE — Item Validation",
    stream_item_aggregate(
        [mld1,mld2],"multiline","UPC","Description","Units","Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_d_cols))
report("MULTILINE DELIMITED MULTI-FILE — Store Validation",
    stream_store_aggregate(
        [mld1,mld2],"multiline","Store","Units","Price",
        multiline_record_types=["D"], multiline_delimiter="|",
        column_names=ml_d_cols))

# ============================================================
# 7. MULTILINE FIXED-WIDTH (with record type prefix)
# ============================================================
ml_fw_layout = os.path.join(TMP, "ml_fw_layout.csv")
with open(ml_fw_layout, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["From","Length","Field","Type"])
    w.writerow(["2","6","UPC","numeric"])
    w.writerow(["8","20","Description","text"])
    w.writerow(["28","5","Units","numeric"])
    w.writerow(["33","8","Price","numeric"])
ml_layout = load_layout(ml_fw_layout)

def ml_fwf_row(upc, desc, units, price):
    # "U" at pos 0; UPC(2,6), Description(8,20), Units(28,5), Price(33,8)
    return f"U{upc:<6}{desc:<20}{units:>5}{price:>8}\n"

mlfw1 = os.path.join(TMP, "multiline_fixed1.txt")
with open(mlfw1, "w") as f:
    f.write(ml_fwf_row("100001", "Widget A", "10", "99.90"))
    f.write(ml_fwf_row("100002", "Gadget B", "5", "49.95"))
    f.write(ml_fwf_row("100001", "Widget A", "8", "79.92"))

report("MULTILINE FIXED-WIDTH SINGLE — Item Validation",
    stream_item_aggregate(
        [mlfw1],"fixed","UPC","Description","Units","Price",
        layout=ml_layout, record_type="U"))

mlfw2 = os.path.join(TMP, "multiline_fixed2.txt")
with open(mlfw2, "w") as f:
    f.write(ml_fwf_row("100003", "Doohickey", "20", "199.80"))
    f.write(ml_fwf_row("100004", "New Item", "3", "29.97"))

report("MULTILINE FIXED-WIDTH MULTI-FILE — Item Validation",
    stream_item_aggregate(
        [mlfw1,mlfw2],"fixed","UPC","Description","Units","Price",
        layout=ml_layout, record_type="U"))

report("MULTILINE FIXED-WIDTH SINGLE — UPC Summary",
    stream_upc_summary(
        [mlfw1],"fixed","UPC","Units","Price",
        layout=ml_layout, record_type="U"))

report("MULTILINE FIXED-WIDTH MULTI-FILE — Store (UPC as store proxy)",
    stream_store_aggregate(
        [mlfw1,mlfw2],"fixed","UPC","Units","Price",
        layout=ml_layout, record_type="U"))

# ============================================================
# 8. FILE REVIEW REPORT (all types in one pass)
# ============================================================
review_delim = generate_file_review(
    [csv1,csv2],"delimited","Store","UPC","Units","Price",delimiter=",")
report("FILE REVIEW — Delimited", review_delim)

review_fwf = generate_file_review(
    [fwf1,fwf2],"fixed","Store","UPC","Units","Price",layout=layout)
report("FILE REVIEW — Fixed-Width", review_fwf)

review_ml = generate_file_review(
    [mld1,mld2],"multiline","Store","UPC","Units","Price",
    multiline_record_types=["D"], multiline_delimiter="|",
    column_names=ml_d_cols)
report("FILE REVIEW — Multiline Delimited", review_ml)

review_mlfw = generate_file_review(
    [mlfw1,mlfw2],"fixed","UPC","UPC","Units","Price",
    layout=ml_layout, record_type="U")
report("FILE REVIEW — Multiline Fixed-Width", review_mlfw)

# ============================================================
# 9. IMPLIED DECIMAL TEST
# ============================================================
csv_implied = os.path.join(TMP, "implied.csv")
with open(csv_implied, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Store","UPC","Desc","Units","Price"])
    w.writerow(["S1","U1","Item X","1000","9999"])  # 10.00 units, 99.99 dollars

report("IMPLIED DECIMAL Store (units/100, dollars/100)",
    stream_store_aggregate(
        [csv_implied],"delimited","Store","Units","Price",delimiter=",",
        implied_units=True, implied_dollars=True))

# ============================================================
# 10. UNIT PRICE MODE
# ============================================================
csv_up = os.path.join(TMP, "unitprice.csv")
with open(csv_up, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Store","UPC","Desc","Units","UnitPrice"])
    w.writerow(["S1","U1","Item X","10","9.99"])

report("UNIT PRICE MODE (units × unit_price = total)",
    stream_store_aggregate(
        [csv_up],"delimited","Store","Units","UnitPrice",delimiter=",",
        price_type="Unit Price"))

# ============================================================
# WRITE REPORT
# ============================================================
report_path = os.path.join(OUT, "full_test_report.txt")
with open(report_path, "w") as f:
    f.write("\n".join(results))
print(f"\nTest report written to: {report_path}")
print("\n".join(results))

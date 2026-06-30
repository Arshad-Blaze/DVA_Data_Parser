# DAV Tool — User Guide

## What is DAV Tool?

DAV Tool compares two sets of retail sales data to find differences. It answers questions like:

- *"Do both files have the same stores?"*
- *"Are the unit sales and dollar amounts matching?"*
- *"Which UPCs are new or missing?"*
- *"How big are the differences?"*

It works with common data formats used in retail/POS systems and can handle large files without slowing down.

---

## Getting Started

### Launching the app

Open a terminal and run:

```bash
streamlit run dav_tool/ui/app.py
```

Your web browser will open automatically showing the DAV Tool interface.

### The two pages

At the top of the screen you'll see two buttons:

- **Onboarding** — Use when you have **one** data file and want to validate it against a store list or generate a UPC summary.
- **Existing** — Use when you have **two** data files (BAU = current/approved, Test = new/changed) and want to compare them.

---

## Onboarding Page

For when you have a single data file.

### Step 1: Point to your file

Enter the folder path or file path. DAV Tool will automatically detect whether it's:
- **Delimited** (CSV, pipe, tab) — shown in green
- **Fixed-width** — shown with a warning, you'll need a layout CSV
- **Multi-line** — shown with a warning, you'll see record-type prefixes

### Step 2 (Multi-line only): Flatten the data

If your file uses record-type prefixes (like `H|` for headers, `D|` for details):

1. Look at the **Raw Preview** to see the prefixes
2. DAV Tool auto-detects the prefixes — adjust if needed
3. Click **Flatten Records**
4. Review the **Flattened Preview**
5. Rename the generic column names (Column_0, Column_1, etc.) to meaningful names
6. Click **Apply Schema**

### Step 3: Preview and set options

For fixed-width files, enter:
- **Layout CSV** — a file describing column positions (see Layout CSV Format below)
- **Start Line** — skip header rows if needed
- **Record Type** — filter to lines starting with a specific letter (e.g. `U` for UPC records)

### Step 4: Map columns

Select which column in your data corresponds to:
- **Retailer Store Column** — store identifier
- **UPC Column** — product code
- **Description Column** — product name
- **Units Column** — quantity sold
- **Price Column** — dollar amount

### Step 5: Choose validations

- **Compare Store List** — upload a store list file; DAV Tool shows which stores are missing from either side
- **Generate Unique UPC Summary** — lists every UPC with total units and dollars
- **File Review Report** — per-file metadata summary

### Step 6: Review results

Results appear in an expandable section:
- Missing stores are listed as text
- UPC summary is shown as a table (downloadable as CSV)
- File review report shows per-file counts

---

## Existing Page

For comparing two data files (BAU vs Test).

### Step 1: Point to both files

Enter the folder/file path for:
- **BAU** (left column) — your current/approved data
- **Test** (right column) — the new data to compare

### Step 2: Configure each file

Follow the same steps as Onboarding for each file:
- Multi-line files need flattening and schema naming
- Fixed-width files need a layout CSV
- Delimited files are auto-detected

### Step 3: Map columns for both files

You'll see two columns of dropdown menus. Map the same concepts (Store, UPC, Description, Units, Price) for both BAU and Test. Additional options:

- **Price Type** — choose **Total Price** (already a total) or **Unit Price** (multiplied by units)
- **Implied Decimal** — check this if your file stores `9999` to mean `99.99`

### Step 4: Choose validations

| Validation | What it shows |
|---|---|
| **Store Level Validation** | Per-store comparison of units and dollars with difference and percentage columns |
| **Item Level Validation** | Per-UPC comparison showing which items match, are new, or are missing |
| **Compare Store List** | Stores in BAU but not Test, and vice versa |
| **Summary** | Aggregate totals of how many items match vs differ |
| **File Review Report** | Per-file metadata (store count, UPC count, totals) |

### Step 5: Review results

All results appear in a single expandable section:

**Store Compare** — text list of missing stores
**Summary** — table of item-level match categories
**Store Validation** — table with one row per store:
- Units_Prod / Units_Test — units sold in each file
- Totalprice_Prod / Totalprice_Test — dollar totals
- Units_Diff / Sales_Diff — absolute difference (BAU minus Test)
- Units_Diff_% / Sales_Diff_% — percentage difference
  - **-100%** = BAU had 0, Test has something (all Test units are "extra")
  - **+100%** = Test had 0, BAU has something (all BAU units are "missing")
  - **0%** = both zero or both match

**Item Validation** — table with one row per UPC:
- Difference columns show Test minus BAU
- Present In column shows: "Present in Both", "Present only in BAU", or "Present only in TEST"
- Percentage columns handle zero-BAU cases the same way as store validation

Each table can be downloaded as CSV.

---

## Understanding the File Formats

### Delimited files (CSV, pipe, tab)

A simple file where values are separated by a character:

```
Store,UPC,Description,Units,Price
S001,100001,Widget A,10,99.90
S002,100001,Widget A,8,79.92
```

### Fixed-width files

Columns start and end at specific character positions. You need a **layout CSV** that describes each column:

```csv
From,Length,Field,Type
1,6,Store,text
7,10,UPC,numeric
17,20,Description,text
37,5,Units,numeric
42,8,Price,numeric
```

- **From** — starting position (1 = first character)
- **Length** — how many characters this field occupies
- **Field** — name you give the column
- **Type** — `text`, `numeric`, or `date`

### Multi-line HDR files

POS export files where each line starts with a letter indicating its record type:

```
H|S001|2024-01-15
D|100001|Widget A|10|99.90
D|100002|Gadget B|5|49.95
```

- **H** records = header (store, date)
- **D** records = detail (UPC, description, units, price)

DAV Tool flattens these by filtering to one record type at a time. You name the columns after flattening.

---

## File Review Report

When enabled, this generates a compact table with one row per file:

| Column | Meaning |
|---|---|
| filename | Name of the data file |
| store_count | Number of unique stores found |
| upc_count | Number of unique UPCs found |
| total_units | Sum of all units sold |
| total_dollars | Sum of all dollar amounts |

Useful for quickly checking that your files contain the expected data volume.

---

## Tips

- **Large files** — DAV Tool streams data in chunks; it can handle files larger than your computer's RAM
- **Encoding** — UTF-8 and Windows cp1252 are both supported automatically
- **Multi-line with different record types** — you can process H and D records separately by entering `H` or `D` as the record type filter
- **Layout CSV errors** — make sure column headers are exactly `From,Length,Field,Type` (case-insensitive)

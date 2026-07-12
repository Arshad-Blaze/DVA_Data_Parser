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

### Before you run: get input specs from your data team

DAV Tool needs to know the structure of your files before it can process them. Ask your data team for:

| What you need | Why |
|---|---|
| **Layout CSV** | For fixed-width files — describes each column's position |
| **Header + Detail layout CSVs** | For HDR fixed-width files — separate layouts for header and detail records |
| **Delimiter** | For delimited files — comma, pipe, tab, or semicolon |
| **Record-type prefixes** | For multiline files — which letters prefix each record type (e.g. H, D) |
| **Column mapping** | Which column is Store, UPC, Description, Units, Price |
| **Implied decimals** | Whether `9999` means `99.99` (divide by 100) |
| **Price type** | Total Price (already aggregated) or Unit Price (multiply by units) |

Get these details first so you can set up the tool quickly when you launch it.

> **Tip:** If you have a saved config JSON, you can skip most manual setup — the wizard will pre-fill settings from it.

### Launching the app

Open a terminal and run:

```bash
dav-tool
```

Or if you're running from source:

```bash
python -m dav_tool
```

Or via Streamlit directly:

```bash
streamlit run dav_tool/ui/app.py
```

Your web browser will open automatically showing the DAV Tool interface.

### The two pages

At the top of the screen you'll see the **Connection Manager** (for connecting to local or SSH data sources) and two page buttons:

- **Onboarding** — Use when you have **one** data file and want to validate it against a store list or generate a UPC summary.
- **Existing** — Use when you have **two** data files (BAU = current/approved, Test = new/changed) and want to compare them.

Both pages follow the same 7-step workflow:

```
1. Connection (CM) → 2. Discovery → 3. Configuration → 4. Validate Config → 5. Processing → 6. Validation → 7. Reports
```

---

## Onboarding Page

For when you have a single data file.

### Step 1: Connection Manager

Before entering the Onboarding page, the **Connection Manager** appears at the top of the screen. You can:

- **Use Local File System** — browse and select files from your local machine
- **Connect to SSH Server** — enter credentials to browse remote files via SFTP

Once connected, select a file or folder. The Connection Manager automatically detects the file type and stores a **DiscoveryResult** for downstream use.

### Step 2: Discovery — File Detection & Preview

When you navigate to the Onboarding page, DAV Tool **consumes the Connection Manager's DiscoveryResult** — no re-detection occurs. The file type, delimiter, columns, and layout are all reused.

If no Connection Manager result is available, you can:
1. Enter a folder path or file path manually
2. DAV Tool runs detection and shows the result

Once detection completes, you'll see:
- **Column count detected** (e.g. "Parsing complete — 5 column(s) detected")
- Click **"Progressive Configuration →"** to proceed

### Step 3: Configuration — Progressive Config Wizard

The configuration wizard walks you through **6 sections** in order:

| Section | What you configure |
|---|---|
| **General** | Configuration name (label), file type, encoding, has header |
| **File Format** | Delimiter, layout CSV, start line, record type, multiline settings |
| **Schema & Columns** | Review detected columns, edit schema if needed |
| **Business Rules** | Column mapping (Store, UPC, Description, Units, Price), price type, implied decimals |
| **Validation** | Enable/disable validations (store, item, compare store list, file review) |
| **Output** | Output format and report options |

Each section must be confirmed before moving to the next. Completed sections are marked with a checkmark.

**Config Name** is a cosmetic label for the configuration being built. It is used as:
- The default download filename (`{name}.json`)
- A label shown in success toasts
- A field serialized into the saved JSON

It is **not** the name of an existing file to load. Leave it blank if you don't need a name.

After completing all sections, the configuration is **locked** and you see:
> "Configuration complete. Proceed to validation."

Click **"Validate Configuration →"** to proceed.

### Step 4: Validate Configuration

Review the full configuration summary. You can:

- **Edit Configuration** — go back to modify settings
- **Download Config as JSON** — save the config for future use
- **Accept Configuration** — lock the config and proceed to processing

Click **"Accept Configuration →"** to proceed.

### Step 5: Processing

Select which column corresponds to:
- **Retailer Store Column** — store identifier
- **UPC Column** — product code
- **Description Column** — product name
- **Units Column** — quantity sold
- **Price Column** — dollar amount

Click **"Confirm Mapping"** then **"Proceed to Processing & Validation →"**.

DAV Tool aggregates the data (Store + Item summaries in parallel) and moves to the Validation phase.

### Step 6: Validation

Choose which validations to run:

- **Compare Store List** — upload a store list file; DAV Tool shows which stores are missing
- **Generate Unique UPC Summary** — lists every UPC with total units and dollars
- **File Review Report** — per-file metadata summary

Click **"Run Validation"** to execute.

### Step 7: Review Results

Results appear in expandable sections:
- Missing stores are listed as text
- UPC summary is shown as a table (downloadable as CSV)
- File review report shows per-file counts

---

## Existing Page

For comparing two data files (BAU vs Test).

### Step 1: Connection Manager

The Connection Manager allows you to connect via local filesystem or SSH. For the Existing page, you can select **two paths** (BAU and Test) using the same Connection Manager interface.

### Step 2: Discovery — File Detection & Preview

DAV Tool **consumes the Connection Manager's DiscoveryResult for each side** — no re-detection occurs. The file type, delimiter, columns, and layout are all reused from the BAU and Test selections.

If no Connection Manager result is available, you can:
1. Enter BAU and Test folder/file paths manually
2. DAV Tool runs detection for each side independently

Each side has its own **DiscoveryResult** stored under `_cm_bau_discovery` and `_cm_test_discovery`.

Once detection completes, click **"Progressive Configuration →"** to proceed.

### Step 3: Configuration — Progressive Config Wizard (per side)

Each side (BAU and Test) has its own configuration wizard with the same 6 sections:

| Section | What you configure |
|---|---|
| **General** | Configuration name (label), file type, encoding, has header |
| **File Format** | Delimiter, layout CSV, start line, record type, multiline settings |
| **Schema & Columns** | Review detected columns, edit schema if needed |
| **Business Rules** | Column mapping (Store, UPC, Description, Units, Price), price type, implied decimals |
| **Validation** | Enable/disable validations (store, item, compare store list, file_review) |
| **Output** | Output format and report options |

Complete the wizard for BAU first, then for Test.

### Step 4: Validate Configuration

Review the configuration summary for both sides. You can:

- **Edit Configuration** — go back to modify settings
- **Download Config as JSON** — save the config for future use
- **Accept Configuration** — lock the config and proceed to processing

Click **"Accept Configuration →"** to proceed.

### Step 5: Processing

Map columns for both files:

| Column | Description |
|---|---|
| **Retailer Store Column** | Store identifier |
| **UPC Column** | Product code |
| **Description Column** | Product name |
| **Units Column** | Quantity sold |
| **Price Column** | Dollar amount |

Additional options:
- **Price Type** — choose **Total Price** (already a total) or **Unit Price** (multiplied by units)
- **Implied Decimal** — check this if your file stores `9999` to mean `99.99`

Click **"Confirm Mapping"** then **"Proceed to Processing & Validation →"**.

DAV Tool aggregates the data (Store + Item summaries in parallel) and moves to the Validation phase.

### Step 6: Validation

Choose which validations to run:

| Validation | What it shows |
|---|---|
| **Store Level Validation** | Per-store comparison of units and dollars with difference and percentage columns |
| **Item Level Validation** | Per-UPC comparison showing which items match, are new, or are missing |
| **Compare Store List** | Stores in BAU but not Test, and vice versa |
| **Summary** | Aggregate totals of how many items match vs differ |
| **File Review Report** | Per-file metadata (store count, UPC count, totals) |

Click **"Run Validation"** to execute.

### Step 7: Review Results

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

### Multi-line HDR files (delimited)

POS export files where each line starts with a letter indicating its record type:

```
H|S001|2024-01-15
D|100001|Widget A|10|99.90
D|100002|Gadget B|5|49.95
```

- **H** records = header (store, date)
- **D** records = detail (UPC, description, units, price)

DAV Tool flattens these by filtering to one record type at a time. You name the columns after flattening.

### Multi-line HDR files (fixed-width)

POS export files with a multi-character header prefix (e.g. `HDR`) followed by fixed-width records:

```
HDRS001   2024-01-15
100001     Widget A            1099.90
100002     Gadget B             549.95
```

- Lines starting with `HDR` are **header** records — they carry store and date fields
- Remaining lines are **detail** records with UPC, description, units, and price
- Each record type has its own fixed-width **layout CSV**
- Header fields (store, date) are automatically carried into every detail row during flattening
- You need **two** layout CSVs: one for the header record, one for the detail record

#### HDR with trailer lines (TRL)

Some POS formats add a **trailer line** at the end of each transaction:

```
HDR01S001   2024-01-15
100001     Widget A            1099.90
100002     Gadget B             549.95
TRL   15   149.85
```

- Lines starting with `TRL` are **trailer** records — they carry summary fields like total units and total dollars
- Trailer fields are automatically attached to every detail row in that transaction
- You need a **third layout CSV** for the trailer record (optional)
- Configurable via **Trailer Prefix** (default `TRL`) and **Trailer Layout CSV** inputs

## Config Files

Instead of going through the manual setup each time, you can save your parsing settings as a **JSON config file** and load it on subsequent runs.

### Sample configurations by file type

#### Delimited (CSV / pipe / tab)

```json
{
  "version": 2,
  "name": "Retailer X — Delimited",
  "file_type": "delimited",
  "encoding": "cp1252",
  "has_header": true,
  "delimiter": ",",
  "start_line": 0,
  "record_type": null,
  "detected_columns": ["Store", "UPC", "Description", "Units", "Price"],
  "detected_data_types": {
    "Store": "String",
    "UPC": "Int64",
    "Description": "String",
    "Units": "Int64",
    "Price": "Float64"
  },
  "suggested_mapping": {
    "store": "Store",
    "upc": "UPC",
    "description": "Description",
    "units": "Units",
    "price": "Price"
  },
  "store_col": "Store",
  "upc_col": "UPC",
  "desc_col": "Description",
  "units_col": "Units",
  "price_col": "Price",
  "price_type": "Total Price",
  "implied_dollars": false,
  "implied_units": false,
  "locked": false
}
```

#### Fixed-width

```json
{
  "version": 2,
  "name": "Retailer Y — Fixed-Width",
  "file_type": "fixed",
  "encoding": "cp1252",
  "has_header": false,
  "delimiter": null,
  "start_line": 1,
  "record_type": "U",
  "layout_file": "/path/to/layout.csv",
  "detected_columns": ["Store", "UPC", "Description", "Units", "Price"],
  "detected_data_types": {
    "Store": "String",
    "UPC": "Int64",
    "Description": "String",
    "Units": "Int64",
    "Price": "Float64"
  },
  "suggested_mapping": {
    "store": "Store",
    "upc": "UPC",
    "description": "Description",
    "units": "Units",
    "price": "Price"
  },
  "store_col": "Store",
  "upc_col": "UPC",
  "desc_col": "Description",
  "units_col": "Units",
  "price_col": "Price",
  "price_type": "Total Price",
  "implied_dollars": false,
  "implied_units": false,
  "locked": false
}
```

Layout file paths can be absolute or relative to the config file's directory.

#### Multi-line HDR (delimited)

```json
{
  "version": 2,
  "name": "Retailer Z — Multiline Delimited",
  "file_type": "multiline",
  "encoding": "cp1252",
  "has_header": false,
  "delimiter": "|",
  "start_line": 0,
  "ml_record_types": ["H", "D"],
  "ml_delimiter": "|",
  "schema": ["Store", "Date", "UPC", "Description", "Units", "Price"],
  "detected_columns": ["Store", "Date", "UPC", "Description", "Units", "Price"],
  "detected_data_types": {
    "Store": "String",
    "Date": "String",
    "UPC": "Int64",
    "Description": "String",
    "Units": "Int64",
    "Price": "Float64"
  },
  "suggested_mapping": {
    "store": "Store",
    "upc": "UPC",
    "description": "Description",
    "units": "Units",
    "price": "Price"
  },
  "store_col": "Store",
  "upc_col": "UPC",
  "desc_col": "Description",
  "units_col": "Units",
  "price_col": "Price",
  "price_type": "Total Price",
  "implied_dollars": false,
  "implied_units": false,
  "locked": false
}
```

#### HDR Fixed-Width (with Trailer)

```json
{
  "version": 2,
  "name": "Retailer W — HDR Fixed-Width",
  "file_type": "multiline",
  "encoding": "cp1252",
  "has_header": false,
  "delimiter": null,
  "start_line": 0,
  "header_prefix": "HDR",
  "header_layout_file": "/path/to/header_layout.csv",
  "detail_layout_file": "/path/to/detail_layout.csv",
  "trailer_prefix": "TRL",
  "trailer_layout_file": "/path/to/trailer_layout.csv",
  "schema": ["Store", "Date", "UPC", "Description", "Units", "Price", "TotalUnits", "TotalPrice"],
  "detected_columns": ["Store", "Date", "UPC", "Description", "Units", "Price", "TotalUnits", "TotalPrice"],
  "detected_data_types": {
    "Store": "String",
    "Date": "String",
    "UPC": "Int64",
    "Description": "String",
    "Units": "Int64",
    "Price": "Float64",
    "TotalUnits": "Int64",
    "TotalPrice": "Float64"
  },
  "suggested_mapping": {
    "store": "Store",
    "upc": "UPC",
    "description": "Description",
    "units": "Units",
    "price": "Price"
  },
  "store_col": "Store",
  "upc_col": "UPC",
  "desc_col": "Description",
  "units_col": "Units",
  "price_col": "Price",
  "price_type": "Total Price",
  "implied_dollars": false,
  "implied_units": false,
  "locked": false
}
```

### Config file fields explained

| Field | Description |
|---|---|
| `version` | Config format version (currently 2) |
| `name` | **Cosmetic label** for the configuration (used as default download filename, shown in toasts). Not a file path. |
| `file_type` | `delimited`, `fixed`, or `multiline` |
| `encoding` | File encoding detected (`cp1252`, `utf-8`, etc.) |
| `has_header` | Whether the file has a header row |
| `delimiter` | Delimiter character for delimited files |
| `start_line` | Number of lines to skip at the top |
| `record_type` | Line prefix filter (e.g. `U` for UPC records only) |
| `layout_file` | Path to layout CSV (for fixed-width) |
| `header_prefix` | Multi-character header prefix (e.g. `HDR`) for HDR files |
| `header_layout_file` | Layout CSV for HDR header records |
| `detail_layout_file` | Layout CSV for HDR detail records |
| `trailer_prefix` | Trailer line prefix (e.g. `TRL`) |
| `trailer_layout_file` | Layout CSV for trailer records |
| `ml_record_types` | List of record-type prefixes (e.g. `["H", "D"]`) |
| `ml_delimiter` | Delimiter used inside multiline records |
| `schema` | Full list of column names after flattening |
| `detected_columns` | Column names detected from the sample |
| `detected_data_types` | Map of column name to inferred data type |
| `suggested_mapping` | Auto-detected column role mapping |
| `store_col` / `upc_col` / `desc_col` / `units_col` / `price_col` | Mapped column names |
| `price_type` | `Total Price` or `Unit Price` |
| `implied_dollars` / `implied_units` | Divide by 100 for implied decimals |
| `validation_config` | Per-validation enable/disable and column requirements |
| `locked` | Whether the config has been accepted by the user |

### How to save a config

1. Complete the progressive configuration wizard (all 6 sections)
2. The configuration is automatically locked
3. In the **Validate Configuration** phase, click **"Download Config as JSON"**
4. Enter a filename (default: `{config_name}.json` or `config.json`)

### How to load a config

1. Launch DAV Tool and navigate to **Onboarding** or **Existing**
2. Connect to your data source (local or SSH) via the Connection Manager
3. Select your files — DAV Tool detects the file type automatically
4. In the Configuration phase, the wizard starts with detected settings
5. To load a previously saved config, click **"Load Config"** and enter the path to your saved JSON
6. The wizard pre-fills all settings from the config
7. Click **"Accept Configuration"** to lock and proceed

Config files let you onboard the same retailer repeatedly without re-entering settings.

### Layout CSV format

```csv
From,Length,Field,Type
1,6,Store,text
7,10,UPC,numeric
```

- **From** — starting position (1 = first character)
- **Length** — how many characters this field occupies
- **Field** — name you give the column
- **Type** — `text`, `numeric`, or `date`

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

## Developer Mode

Both pages have a **Developer Mode** checkbox in the sidebar. When enabled, it shows live diagnostics:

- Current pipeline phase (Connection → Discovery → Configuration → Validate Config → Processing → Validation → Reports)
- File type detection status
- Memory and CPU usage
- Aggregation row counts
- Validation completion status

This is useful for debugging and understanding what the pipeline is doing at each step.

---

## Tips

- **Large files** — DAV Tool streams data in chunks; it can handle files larger than your computer's RAM
- **Encoding** — UTF-8 and Windows cp1252 are both supported automatically
- **Multi-line with different record types** — you can process H and D records separately by entering `H` or `D` as the record type filter
- **Layout CSV errors** — make sure column headers are exactly `From,Length,Field,Type` (case-insensitive)
- **Config Name** — The name field in the config wizard is a cosmetic label, not a file path. Use it to identify the config in toasts and download filenames.
- **Progressive Wizard** — Each section must be confirmed before moving to the next. You can go back and edit completed sections.
- **Connection Manager** — Use the CM to connect to local or SSH sources before entering a page. Discovery reuses CM's result without re-detection.

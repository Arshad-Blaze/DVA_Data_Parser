# DAV Tool — Data Analysis & Validation Tool

DAV Tool compares retail/POS data files (BAU vs Test) to find differences in sales, units, and store coverage. It handles **plain CSV**, **fixed-width text**, and **multi-line HDR-format** files with streaming — no database or intermediate files needed.

---

## For Non-Technical Users

### What it does
- Upload two sets of sales data (your current file and a new/test file)
- Pick which columns hold store numbers, UPCs, descriptions, units, and prices
- Run validations to see:
  - **Store-level comparison** — which stores differ in units/dollars, and by how much
  - **Item-level comparison** — which UPCs differ between the two files
  - **Store list compare** — stores present in one file but missing from the other
  - **File review report** — per-file summary of store count, UPC count, units, and dollars

### Supported file formats
| Format | Description |
|---|---|
| **Delimited** | CSV, pipe-delimited, tab-delimited, semicolon (auto-detected) |
| **Fixed-width** | Columns at fixed character positions (requires a layout CSV) |
| **Multi-line HDR (delimited)** | POS data with record-type prefixes (e.g. `H\|store\|date`, `D\|upc\|desc\|units\|price`) |
| **Multi-line HDR (fixed-width)** | POS data with multi-character header prefix (e.g. `HDR`) followed by fixed-width records; requires **two** layout CSVs (header + detail) |

### How to run
```
streamlit run dav_tool/ui/app.py
```

### Before you run: get input specs from your data team
DAV Tool needs to know the structure of your files before it can process them. Before running, confirm with your data team:
- **Layout CSV** for any fixed-width file (column positions)
- **Header + Detail layout CSVs** for HDR fixed-width files (separate layouts for header and detail records)
- **Delimiter** for delimited files (comma, pipe, tab, semicolon)
- **Record-type prefixes** for multiline files (e.g. `H`, `D`, `U`)
- **Column mapping** — which columns hold Store, UPC, Description, Units, Price
- **Implied decimals** — whether `9999` means `99.99` (divide by 100)
- **Price type** — Total Price or Unit Price (multiplied by units sold)

---

## For Technical Users

### Installation

```bash
pip install polars streamlit
```

No additional setup required — just run the app.

### Project structure

```
dav_tool/
├── _parsers.py          Raw file I/O: fixed-width, delimited, multiline flattening
├── _aggregators.py      Streaming aggregations: store, item, UPC, file review
├── detection.py         File-type and multiline detection
├── io.py                Safe CSV reader with encoding fallback
├── config.py            Shared constants
├── types.py             Dataclass definitions
├── validation/
│   ├── store.py         Store-level validation logic
│   └── item.py          Item-level validation logic
└── ui/
    ├── app.py           Streamlit entry point (page dispatch)
    ├── helpers.py       Shared UI helpers
    ├── onboarding.py    Onboarding page logic
    └── existing.py      Existing/BAU page logic
```

### Key design decisions

- **Polars streaming** (`streaming=True`, chunked generators) — handles files larger than RAM
- **No intermediate files** — data flows directly from source files through aggregators
- **Multiline handling** — record-type prefixes (H, D, U, T) are detected, filtered, and flattened at preview time; user defines column names before schema is applied
- **Schema fix at preview** — users rename generic `Column_N` names before column mapping, avoiding downstream failures

### Running tests

```bash
pytest tests/ -v                     # 18 unit tests
python full_test.py                  # Integration test (all formats + file review)
```

---

## Workflow Overview

```
1. Get input specs from data team (layout CSVs, column mapping, delimiter, etc.)
2. Select page: Onboarding (single file) or Existing (BAU vs Test)
3. Point to file(s) — format is auto-detected
4. For multiline files: flatten, preview, name columns
   - Delimited: set record-type flags and delimiter → flatten → rename schema
   - HDR fixed-width: provide header + detail layout CSVs → flatten → rename schema
5. For fixed-width: provide layout CSV, set start line / record type
6. Map columns (Store, UPC, Description, Units, Price)
7. Choose validations and run
8. Review results and download CSVs
```

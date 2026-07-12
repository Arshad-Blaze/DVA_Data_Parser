# DVA Data Parser

## Purpose

This application parses retailer POS files and prepares them for downstream validation.

The tool supports

- Delimited files
- Fixed Width files
- HDR / Multiline records

---

# Processing Pipeline

User

↓

UI

↓

Workflow Layer

↓

Auto Detection

↓

Parser

↓

Structured Data

↓

Aggregator

↓

Validation

↓

Reports

---

## Workflow Phases

The pipeline follows 7 phases:

```
1. Connection (CM) → 2. Discovery → 3. Configuration → 4. Validate Config → 5. Processing → 6. Validation → 7. Reports
```

- **Connection:** User connects via local filesystem or SSH (Connection Manager)
- **Discovery:** File detection, preview, column extraction (reuses CM's DetectionResult)
- **Configuration:** Progressive config wizard (6 sections: General, File, Schema, Business Rules, Validation, Output)
- **Validate Config:** Review and accept configuration
- **Processing:** Full dataset read, aggregation (Store + Item in parallel)
- **Validation:** Run selected validations
- **Reports:** Review results and download CSVs

---

## Module Responsibilities

### UI

Handles

- User workflow
- Upload
- Configuration (progressive config wizard)
- Progress
- Display

No business logic.

---

### Workflow Layer

Orchestrates the pipeline using service functions.

Modules

- `dav_tool/workflow/discovery.py` — File detection, preview, column extraction, DetectionResult
- `dav_tool/workflow/processing.py` — Aggregation orchestration, file review
- `dav_tool/workflow/validation.py` — Validation orchestration
- `dav_tool/options.py` — Option dataclasses (ParseOptions, ColumnMapping, AggregationOptions, ValidationOptions)

No Streamlit imports. No rendering. Pure processing logic.

**Discovery consumption:** The Discovery phase reuses the Connection Manager's DetectionResult without re-detection. For the Existing page, BAU and Test discoveries are stored separately.

---

### Detection

Determines

- File type
- Encoding
- Delimiter
- Record format

Produces parser configuration.

---

### Parser

Converts raw files into structured tables.

Supports

- CSV
- TXT
- Fixed Width
- Multi-record

---

### Aggregator

Creates

- Store summaries
- Item summaries
- Statistics

---

### Validation

Runs business rules.

Examples

- Missing Stores
- Duplicate UPC
- Missing UPC
- Record Counts
- Store Comparison
- Item Comparison

---

### Reports

Exports

- Excel
- CSV
- Validation Reports

---

## Option Dataclasses

Option dataclasses replace parameter explosion with structured configuration.

| Dataclass | Purpose |
|-----------|---------|
| `ParseOptions` | File type, delimiter, layout, multiline config |
| `ColumnMapping` | Store, UPC, description, units, price columns |
| `AggregationOptions` | Flags for what to compute |
| `ValidationOptions` | Flags for what to validate |
| `WorkflowState` | Current phase, progress, errors |
| `ProcessingContext` | Carries `discovery: DetectionResult` as bridge between Discovery and downstream phases |

---

## Design Principles

Single Responsibility

Small Functions

Modular Components

No Circular Dependencies

Minimal Coupling

High Cohesion

---

## Performance Goals

Support

200MB–500MB retailer files.

Future target

1GB+ files.

Memory usage should remain predictable.

---

## Future Improvements

- Better logging
- Configurable detection pipeline
- Plugin parsers
- Configurable validations (partially implemented via ValidationConfig)
- Background processing

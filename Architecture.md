# DVA Platform Architecture

## Overview

The DVA (Data Validation & Analysis) Platform is a modular Streamlit-based application for processing Retail/POS data. It supports three file formats (delimited, fixed-width, multiline/HDR) and provides a complete pipeline from file detection through aggregation, validation, and reporting.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│  (Streamlit) app.py, onboarding.py, existing.py, helpers.py  │
├─────────────────────────────────────────────────────────────┤
│                     Workflow Layer                            │
│  discovery.py, canonical.py, processing.py, validation.py    │
├─────────────────────────────────────────────────────────────┤
│                     Service Layer                             │
│  config_builder.py, _aggregators.py, _reports.py             │
├─────────────────────────────────────────────────────────────┤
│                     Parser Layer                              │
│  _parsers.py, _normalizer.py, detection.py, format_config.py │
├─────────────────────────────────────────────────────────────┤
│                   Data Source Layer                           │
│  datasource/{base,local,ssh,manager}.py                      │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**UI Layer** — User interaction, rendering, session state, progress display.
- `app.py`: Main entry point, page routing
- `onboarding.py`: Single-dataset workflow (discovery → processing → validation → reports)
- `existing.py`: Two-dataset comparison workflow (BAU vs Test)
- `helpers.py`: Shared UI components, config renderers, column selection
- `layout_builder.py`: Interactive fixed-width layout builder (RC2 new)
- `connection_manager.py`: Connection management (local/SSH)

**Workflow Layer** — Orchestrates the pipeline phases.
- `discovery.py`: File detection service producing DiscoveryResult
- `processing.py`: Store and item aggregation orchestration
- `validation.py`: Onboarding and existing validation execution
- `canonical.py`: Canonical schema management
- `preview.py`: Data preview wrappers for UI

**Service Layer** — Business logic without UI dependency.
- `config_builder.py`: Build FormatConfig from data samples
- `_aggregators.py`: Aggregation engine (store/item/UPC level)
- `_reports.py`: File review report generation

**Parser Layer** — File format parsing and data normalization.
- `_parsers.py`: Raw parsing, chunk streaming, canonical stream
- `_normalizer.py`: Column normalization to canonical names
- `detection.py`: File type, delimiter, multiline detection
- `format_config.py`: Config data model (FormatConfig, ValidationConfig)
- `_column_utils.py`: Column name matching and smart indices

**Data Source Layer** — Abstract data access layer.
- `base.py`: IDataSource protocol
- `local.py`: Local filesystem access
- `ssh.py`: SSH/SFTP remote access
- `manager.py`: Connection state management

## Data Flow

```
Connection → Discovery → Configuration → Config Validation
→ Processing → Validation → Reports
```

## Key Design Decisions

1. **Single Discovery Result**: Detection runs once and stores a `DiscoveryResult` consumed by all downstream phases. No re-detection.

2. **Three-Layer Schema**: Physical (raw columns), Canonical (business names), Business Mapping (column → concept).

3. **Canonical Chunk Stream**: All file formats produce a unified canonical stream with pre-renamed columns — aggregation never sees raw column names.

4. **Polars LazyFrame**: Large file processing uses streaming LazyFrames with chunked processing for memory efficiency.

5. **Option Objects**: Immutable dataclasses (ParseOptions, ColumnMapping) replace long parameter lists.

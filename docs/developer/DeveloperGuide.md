# Developer Guide

## Setup

### Prerequisites
- Python >= 3.10
- pip

### Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install optional SSH support
pip install paramiko>=3.0
```

### Running the Application

```bash
# Start Streamlit app
streamlit run dav_tool/ui/app.py
```

### Running Tests

```bash
# Run all tests
python3 -m pytest

# Run with verbose output
python3 -m pytest -v

# Run specific test file
python3 -m pytest tests/test_detection_service.py -v

# Run E2E tests
python3 -m pytest tests/e2e/ -v
```

## Project Structure

```
dav_tool/
├── __main__.py              # CLI entry point
├── _aggregators.py          # Aggregation engine
├── _column_utils.py         # Column name matching
├── _normalizer.py           # Canonical normalization
├── _observability.py        # Metrics, logging, memory tracking
├── _parsers.py              # File parsing engines
├── _reports.py              # Report generation
├── calculations/            # Calculation functions
├── certification/           # Certification suite
├── config.py                # Configuration constants
├── config_builder.py        # Build config from data samples
├── config_validator.py      # Config validation
├── datasource/              # Data access layer
├── detection.py             # File type detection
├── format_config.py         # Config data model
├── io.py                    # File I/O utilities
├── operations/              # Data operations (sort, filter, etc.)
├── options.py               # Option objects
├── processing_context.py    # Pipeline state
├── ui/                      # Streamlit UI
│   ├── app.py               # Main app entry
│   ├── onboarding.py        # Single-dataset flow
│   ├── existing.py          # Two-dataset comparison flow
│   ├── helpers.py           # Shared UI components
│   ├── layout_builder.py    # Fixed-width layout builder (RC2)
│   ├── connection_manager.py
│   └── certification_suite.py
├── validation/              # Business rule validation
└── workflow/                # Workflow orchestration
    ├── canonical.py         # Canonical schema
    ├── data_access.py       # Source wrapping
    ├── discovery.py         # File detection service
    ├── discovery_compare.py # Discovery comparison
    ├── flush.py             # Data flush
    ├── migration_report.py  # Migration report
    ├── operation_comparison.py
    ├── preview.py           # Preview wrappers
    ├── processing.py        # Aggregation orchestration
    ├── schema_comparison.py # Schema comparison
    └── validation.py        # Validation orchestration
```

## Coding Conventions

- Follow PEP 8
- Imports: stdlib → third-party → local
- Prefer Polars over Pandas
- Use LazyFrame for large datasets
- Keep functions under ~50 lines
- No exceptions swallowed silently
- No `except Exception: pass`

## Testing Strategy

- Unit tests in `tests/`
- E2E tests in `tests/e2e/`
- Golden data tests in `tests/golden/`
- Test data in `tests/e2e/sample_data.py`

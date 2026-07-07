# E2E Test Execution Instructions

## Prerequisites

- Python 3.10+
- Virtual environment with dependencies installed

## Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Install Playwright (if not already installed)
pip install playwright pytest-playwright pytest-html pytest-timeout
python -m playwright install chromium
```

## Running Tests

### Run All E2E Tests

```bash
# Using convenience script
./run_e2e_tests.sh

# Or directly via pytest
python -m pytest tests/e2e/ \
    --html=tests/e2e/reports/report.html \
    --self-contained-html \
    --junit-xml=tests/e2e/reports/junit.xml \
    -v
```

### Run Specific Test Categories

```bash
# Connection Manager tests only
python -m pytest tests/e2e/connection_manager/ -v

# Onboarding workflow tests only
python -m pytest tests/e2e/onboarding/ -v

# Existing/BAU workflow tests only
python -m pytest tests/e2e/existing/ -v

# Regression tests only
python -m pytest tests/e2e/test_regression.py -v

# Single test method
python -m pytest tests/e2e/connection_manager/test_connection_manager_ui.py::TestConnectionManagerLocal::test_connect_local_shows_connection_info -v
```

### Run With Performance Monitoring

The test suite automatically captures test duration metrics and prints them at session end. An HTML report is always generated.

## Test Reports

All reports are written to `tests/e2e/reports/`:

| File | Format | Contents |
|---|---|---|
| `report.html` | HTML (self-contained) | Full test results with screenshots on failure |
| `junit.xml` | JUnit XML | Machine-readable results for CI integration |

### Additional Artifacts (on failure)

- **Screenshots:** Captured automatically on test failure
- **Traces:** Playwright trace files for debugging (`.zip` files in report directory)
- **Videos:** Retained on failure for visual debugging

## CI Integration

### GitHub Actions Example

```yaml
- name: Run E2E Tests
  run: |
    source venv/bin/activate
    python -m playwright install chromium
    ./run_e2e_tests.sh

- name: Upload Test Reports
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: e2e-test-reports
    path: tests/e2e/reports/
```

## Test Architecture

### Test Files

```
tests/e2e/
├── ARCHITECTURE_REVIEW.md       # Architecture summary
├── EXECUTION.md                 # This file
├── RUNTIME_ISSUES.md            # Discovered runtime issues
├── conftest.py                  # Shared fixtures & hooks
├── sample_data.py               # Sample data generators
├── fixtures/                    # Fixture modules
├── common/                      # Shared test utilities
├── connection_manager/
│   └── test_connection_manager_ui.py
├── onboarding/
│   ├── test_onboarding_config_builder.py
│   ├── test_onboarding_config_load.py
│   ├── test_onboarding_delimited.py
│   ├── test_onboarding_hdr_trailer.py
│   └── test_onboarding_multiline.py
├── existing/
│   ├── test_existing_delimited.py
│   └── test_existing_fixed_width.py
├── reports/
│   └── test_reports.py
└── test_regression.py
```

### Fixtures

| Fixture | Scope | Description |
|---|---|---|
| `streamlit_server` | session | Starts Streamlit app on random port |
| `test_data` | session | Creates temp dir with sample CSV files |
| `onb_page` | function | New page pre-navigated to Onboarding |
| `ex_page` | function | New page on Existing (default) page |

## Test Count

Currently **35 tests** across 5 test files:
- 9 connection manager tests
- 8 onboarding workflow tests
- 8 existing/BAU workflow tests
- 8 regression tests
- 2 reports tests

## Troubleshooting

### Streamlit Server Fails to Start

Check that port is not in use. The fixture uses a random port automatically.

### Tests Time Out

Increase `--timeout` parameter. Large file processing in the app may take time.

### No Module Named 'dav_tool'

Ensure PYTHONPATH includes the repo root. The conftest sets this automatically.

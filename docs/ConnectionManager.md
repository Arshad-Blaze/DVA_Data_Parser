# Connection Manager — Architecture & Workflow

## Overview

The Connection Manager adds remote data source support to DAV Tool. Users can connect to remote Linux servers via SSH/SFTP and browse, select, and process files without manually copying them to the local machine.

The architecture follows a strict layered design:

```
Application (UI)
       ↓
Connection Manager
       ↓
Data Source Provider  ←  IDataSource interface
       ↓
Parser (unchanged)
       ↓
Canonical Layer
       ↓
Validation
       ↓
Reports
```

The **Parser never knows** whether data comes from the local file system, an SSH/SFTP server, or a future cloud provider. It receives local file paths only.

---

## Architecture

### Layers

| Layer | Responsibility |
|---|---|
| **Connection Manager UI** | Top-level Streamlit component for selecting connection type, entering credentials, and browsing remote files |
| **Connection Manager** (`datasource/manager.py`) | Singleton that manages the active data source and connection configuration |
| **Data Source Provider** (`datasource/base.py`) | Abstract `IDataSource` interface defining all operations |
| **LocalDataSource** (`datasource/local.py`) | Wraps `os` and `glob` operations — no external dependencies |
| **SSHDataSource** (`datasource/ssh.py`) | Uses `paramiko` for native SSH/SFTP — no PuTTY dependency |
| **Parser** (unchanged) | Receives **resolved local paths** only — never modified |

### Data Flow

#### Local workflow (unchanged)

```
User clicks "Use Local File System"
       ↓
LocalDataSource.connect()  →  no-op, returns True
       ↓
get_file_list(path)  →  LocalDataSource.list_files()
       ↓
resolve_source_paths()  →  returns paths as-is (already local)
       ↓
Parser receives local paths  →  unchanged processing
```

#### Remote SSH workflow

```
User fills host/port/username/password(or key)
       ↓
SSHDataSource.connect()  →  opens SSH + SFTP session
       ↓
User browses remote file tree
       ↓
get_file_list(remote_path)  →  SSHDataSource.list_files()
       ↓
User selects files, clicks "Proceed to Processing"
       ↓
resolve_source_paths()  →  downloads each file to local temp directory
       ↓
Parser receives temp local paths  →  unchanged processing
       ↓
Temporary files exist only for the duration of processing
```

---

## Data Source Interface

All data sources implement `IDataSource`:

```python
class IDataSource(ABC):
    def connect(self) -> bool
    def disconnect(self) -> None
    def is_connected(self) -> bool
    def list_directory(self, path: str) -> List[DataSourceEntry]
    def list_files(self, path: str) -> List[str]
    def read_sample(self, path: str, n: int = 100) -> str
    def open_stream(self, path: str) -> BinaryIO
    def download_if_required(self, path: str) -> str
    def exists(self, path: str) -> bool
    def stat(self, path: str) -> dict
    def get_server_info(self) -> dict
    def get_connection_string(self) -> str
```

Key design points:

- **`read_sample()`** reads only the first `n` lines — used by the Configuration Builder to avoid downloading entire files for inference
- **`download_if_required()`** returns a **local path**. For `LocalDataSource` this is the path itself. For `SSHDataSource` it downloads to a `tempfile.NamedTemporaryFile` and returns that path
- **`open_stream()`** returns a file-like object for direct streaming (future use)
- **`list_directory()`** returns `DataSourceEntry` objects with name, path, is_dir, size, and modified time for the file browser

---

## SSH Workflow Detail

### Authentication

| Method | Fields |
|---|---|
| Username + Password | Host, Port, Username, Password |
| Username + Private Key | Host, Port, Username, Private Key Path, Key Passphrase (optional) |

- Passwords are kept in **session memory only** — never written to disk
- SSH keys are loaded from the specified file path
- Host key verification uses `AutoAddPolicy` (first-connect trust)

### Connection Status

After a successful connection, the UI displays:

- **Host** — connected server
- **User** — authenticated username
- **Platform** — server OS (from `uname -a`)
- **Disk** — available space (from `df -h`)
- Connection string is logged via `log_phase()`

### Remote File Browser

The file browser provides:

- **Breadcrumb-style navigation** — type a path or navigate via buttons
- **← Back** button — returns to the previously visited directory
- **↻ Refresh** button — reloads the current directory
- **Search** field — filter files/directories by name
- Folder buttons navigate into directories
- Files are displayed with size (formatted as KB/MB/GB)

### File Selection

- Single files and folders are supported
- Selected remote paths are stored in the UI's folder input field
- `get_file_list()` returns remote file paths
- `resolve_source_paths()` downloads files to local temp before parser consumption

### Performance

- Configuration Builder reads only **100 sample rows** remotely — no full download
- Full files are downloaded only **after** configuration is accepted
- Temporary files are created with `NamedTemporaryFile(delete=False)` and reused during processing
- Download happens at aggregation time, not at listing time

### Error Handling

| Scenario | User-facing message |
|---|---|
| Host unreachable | "SSH connection failed: \[detail]" |
| Authentication failure | "SSH connection failed: Authentication failed" |
| Permission denied | "Cannot list directory /path: Permission denied" |
| Missing file | "Cannot download /path: No such file" |
| Invalid path | "Path does not exist: /path" |
| Timeout | "SSH connection failed: timed out" |
| Connection lost | Detected via `is_connected` check |

No raw stack traces are exposed to the user. All errors are logged via `logger.error(exc_info=True)`.

---

## Local Workflow Detail

The `LocalDataSource` is a thin wrapper around standard Python file operations:

- `list_files()` → `os.listdir` + `glob.glob`
- `read_sample()` → `open(path).readlines()[:n]`
- `download_if_required()` → returns the path as-is
- `connect()` → no-op, returns `True`

It is always available and requires no dependencies.

---

## Adding a New Provider

To add a new data source (e.g., SMB, NFS, Azure Blob, AWS S3):

1. Create a new class in `dav_tool/datasource/` that implements `IDataSource`
2. Add a new connection type in `dav_tool/datasource/manager.py` (e.g., `connect_smb()`)
3. Add a new UI handler in `dav_tool/ui/connection_manager.py`
4. If the provider requires a new dependency, add it to `[project.optional-dependencies]` in `pyproject.toml`

No changes to the Parser, Canonical Layer, Validation, or Reports are needed.

### Example skeleton

```python
from dav_tool.datasource.base import IDataSource, DataSourceEntry

class SMBDataSource(IDataSource):
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    # ... implement all abstract methods
```

---

## Testing

### Unit Tests

All tests are in `tests/` and run with:

```bash
pytest tests/ --ignore=tests/e2e
```

| Test File | Coverage | Tests |
|---|---|---|
| `tests/test_datasource.py` | `LocalDataSource` (all methods), `ConnectionManager` (connect/disconnect/is_connected, SSH auth failure) | 29 |
| `tests/test_config_builder.py` | `build_config()` with and without `source` param, multiline config, data type inference | 5 |

Key test scenarios:

- **`LocalDataSource`**: connect, disconnect, exists, list_files (single file + directory + missing path), list_directory (with sorting: dirs first), read_sample (partial + full file), download_if_required (returns same path), stat (file, dir, missing), open_stream, get_server_info, get_connection_string
- **`ConnectionManager`**: connect_local, get_active_source, disconnect, double-disconnect safety, `connect_ssh` with missing paramiko (DataSourceError), `connect_ssh` with connection failure (DataSourceError via mocked paramiko)
- **`config_builder`**: delimited file detection, source parameter passthrough, empty file list, multiline delimited config, `_infer_data_types`

### Integration Test

The end-to-end test (`full_test.py`) runs the full pipeline (parse → aggregate → validate → report) against all file types (delimited, fixed-width, multiline, HDR) in single-file and multi-file modes. It verifies 29 DataFrame shape checks.

### Running Tests

```bash
# All unit tests (130+ tests)
pytest tests/ --ignore=tests/e2e -q

# Specific test files
pytest tests/test_datasource.py -v
pytest tests/test_config_builder.py -v

# Integration test
python3 full_test.py
```

### CI Notes

- `dav_tool/datasource/ssh.py` has a runtime check for `paramiko` — if not installed, all SSH operations raise `DataSourceError` with install instructions
- The `conftest.py` at `tests/conftest.py` mocks `streamlit` to allow unit tests to import UI-touching modules without a Streamlit runtime
- E2E Playwright tests require a Streamlit runtime environment and are in `tests/e2e/`

---

## Files Modified

| File | Change |
|---|---|
| `dav_tool/datasource/__init__.py` | New — exports all data source classes |
| `dav_tool/datasource/base.py` | New — `IDataSource` ABC + `DataSourceEntry` + `DataSourceError` |
| `dav_tool/datasource/local.py` | New — `LocalDataSource` implementation |
| `dav_tool/datasource/ssh.py` | New — `SSHDataSource` implementation (paramiko) |
| `dav_tool/datasource/manager.py` | New — `ConnectionManager` singleton |
| `dav_tool/ui/connection_manager.py` | New — Connection Manager Streamlit UI |
| `dav_tool/ui/app.py` | Modified — added `render_connection_manager()` at top |
| `dav_tool/ui/helpers.py` | Modified — `get_file_list()` and `load_storelist()` accept optional `source` param |
| `dav_tool/ui/onboarding.py` | Modified — passes `source` to `get_file_list`, `build_config`, resolves paths before aggregation |
| `dav_tool/ui/existing.py` | Modified — passes `source` to `get_file_list`, `build_config`, resolves paths before aggregation and validation |
| `dav_tool/config_builder.py` | Modified — accepts `source` param, reads sample remotely without full download |
| `tests/conftest.py` | New — mock `streamlit` for unit test compatibility |
| `tests/test_datasource.py` | New — 29 unit tests for data source layer |
| `tests/test_config_builder.py` | New — 5 unit tests for configuration builder |
| `pyproject.toml` | Modified — added `paramiko>=3.0` dependency |

## Files NOT Modified

- `dav_tool/_parsers.py` — untouched
- `dav_tool/_aggregators.py` — untouched
- `dav_tool/_normalizer.py` — untouched
- `dav_tool/_reports.py` — untouched
- `dav_tool/validation/*` — untouched
- `dav_tool/_observability.py` — untouched
- `dav_tool/format_config.py` — untouched
- `dav_tool/processing_context.py` — untouched
- `dav_tool/detection.py` — untouched

"""Data Access Strategy — automatic strategy selection beneath Connection Layer.

Sits between IDataSource (Connection Layer) and the Processing Layer.
Automatically selects among:

- DIRECT_STREAM   — local files, direct I/O (fastest, enables Polars LazyFrame)
- BATCH_COPY      — remote small files, download all then process locally
- SEQUENTIAL_COPY — remote medium files, copy one-at-a-time via temp
- CHUNK_STREAM    — remote large files, stream without local copy

Not exposed to users. All decisions are automatic and logged.
"""

import logging
import os
import shutil
import tempfile
import time
import concurrent.futures
from enum import Enum
from typing import List, Optional, BinaryIO, Dict, Callable, TypeVar

from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AccessStrategy(Enum):
    DIRECT_STREAM = "direct_stream"
    BATCH_COPY = "batch_copy"
    SEQUENTIAL_COPY = "sequential_copy"
    CHUNK_STREAM = "chunk_stream"


class DataAccessError(Exception):
    """Raised when data access fails after all retries."""


_MAX_RETRIES = 3
_RETRY_DELAY_S = 2
_BATCH_COPY_MAX_MB = 50
_SEQUENTIAL_COPY_MAX_MB = 500
_MIN_DISK_FREE_MB = 500
_LOW_RAM_MB = 256

_ACTIVE_ACCESSORS: List["DataAccessor"] = []


def _with_retry(fn: Callable[[], T], label: str = "") -> T:
    """Execute *fn* with up to *_MAX_RETRIES* retries on failure."""
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            log_msg = f"[DAS] Retry {attempt}/{_MAX_RETRIES}"
            if label:
                log_msg += f" for {label}"
            log_msg += f" failed: {e}"
            logger.warning(log_msg)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_S * attempt)
    raise DataAccessError(
        f"Operation failed after {_MAX_RETRIES} retries"
        + (f" ({label})" if label else "")
    ) from last_exc


class DataAccessor:
    """Transparent wrapper around IDataSource with automatic strategy selection.

    Usage::

        accessor = DataAccessor(source)
        local_paths = accessor.resolve(file_paths)
        # Now use accessor as a drop-in for IDataSource
        stream = accessor.open_stream(local_paths[0])
        local = accessor.download_if_required(remote_path)
        accessor.cleanup()  # remove temp files
    """

    def __init__(self, source: IDataSource):
        self._source = source
        self._strategy: Optional[AccessStrategy] = None
        self._decision: str = ""
        self._resolved_paths: List[str] = []
        self._local_paths: Dict[str, str] = {}
        self._temp_files: List[str] = []
        self._temp_dir: Optional[str] = None
        self._closed: bool = False

    # ── Public API ──────────────────────────────────────────────

    def resolve(self, file_paths: List[str]) -> List[str]:
        """Analyze files and source, select strategy, return usable paths.

        For DIRECT_STREAM / CHUNK_STREAM: returns original paths.
        For BATCH_COPY: downloads all files, returns local temp paths.
        For SEQUENTIAL_COPY: returns original paths (download on open).
        """
        if self._closed:
            raise DataAccessError("DataAccessor has been closed")
        if not file_paths:
            return file_paths
        if self._source.supports_direct_path:
            self._strategy = AccessStrategy.DIRECT_STREAM
            self._decision = f"strategy=direct_stream, source=local"
            logger.info("[DAS] %s — %d file(s)", self._decision, len(file_paths))
            self._resolved_paths = list(file_paths)
            return self._resolved_paths

        info = self._gather_info(file_paths)
        self._strategy = self._select_strategy(info)
        self._decision = (
            f"strategy={self._strategy.value}, "
            f"files={info['count']}, "
            f"total_mb={info['total_size_mb']:.1f}, "
            f"ram_mb={info['ram_mb']:.0f}, "
            f"disk_mb={info['disk_mb']:.0f}"
        )
        logger.info("[DAS] Selected %s", self._decision)

        if self._strategy == AccessStrategy.BATCH_COPY:
            resolved = self._batch_download(file_paths)
            self._resolved_paths = resolved
            return resolved

        self._resolved_paths = list(file_paths)
        return self._resolved_paths

    def open_stream(self, path: str) -> BinaryIO:
        """Open a binary stream with retry logic.

        Behaviour depends on active strategy:
        - DIRECT_STREAM / BATCH_COPY → opens local file
        - SEQUENTIAL_COPY → downloads to temp first, opens local
        - CHUNK_STREAM → delegates to source.open_stream() with retry
        """
        if self._strategy in (AccessStrategy.DIRECT_STREAM, AccessStrategy.BATCH_COPY):
            return open(path, "rb")

        if self._strategy == AccessStrategy.SEQUENTIAL_COPY:
            local = self._download_one(path)
            return open(local, "rb")

        if self._strategy == AccessStrategy.CHUNK_STREAM:
            return _with_retry(
                lambda: self._source.open_stream(path),
                label=f"open_stream({path})",
            )

        if self._strategy is None:
            return _with_retry(
                lambda: self._source.open_stream(path),
                label=f"open_stream({path})",
            )

        return open(path, "rb")

    def download_if_required(self, path: str) -> str:
        """Return a local path for *path*, using local cache if available.

        With retry logic for remote downloads.
        """
        if path in self._local_paths:
            return self._local_paths[path]
        if self._source.supports_direct_path:
            return path

        local = _with_retry(
            lambda: self._source.download_if_required(path),
            label=f"download({path})",
        )
        self._local_paths[path] = local
        self._temp_files.append(local)
        return local

    @property
    def supports_direct_path(self) -> bool:
        """After BATCH_COPY, all paths are local → direct path supported."""
        return self._strategy in (
            AccessStrategy.DIRECT_STREAM,
            AccessStrategy.BATCH_COPY,
        )

    @property
    def strategy(self) -> Optional[AccessStrategy]:
        return self._strategy

    @property
    def decision(self) -> str:
        return self._decision

    @property
    def wrapped_source(self) -> IDataSource:
        """The underlying IDataSource (for operations DataAccessor does not override)."""
        return self._source

    def cleanup(self):
        """Remove all temp files created by this accessor.

        Safe to call multiple times. Afterwards the accessor is closed.
        """
        if self._closed:
            return
        self._closed = True
        for local in self._temp_files:
            try:
                if os.path.exists(local):
                    os.unlink(local)
                    logger.debug("[DAS] Removed temp: %s", local)
            except Exception as e:
                logger.warning("[DAS] Cleanup failed for %s: %s", local, e)
        self._temp_files.clear()
        self._local_paths.clear()
        if self._temp_dir is not None and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.debug("[DAS] Removed temp dir: %s", self._temp_dir)
            except Exception as e:
                logger.warning("[DAS] Temp dir cleanup failed: %s", e)
            self._temp_dir = None

    # ── Internal helpers ────────────────────────────────────────

    def _gather_info(self, file_paths: List[str]) -> dict:
        """Collect resource and file info for strategy selection."""
        total_size = 0
        file_count = len(file_paths)

        for p in file_paths:
            try:
                stat = _with_retry(
                    lambda p=p: self._source.stat(p),
                    label=f"stat({p})",
                )
                total_size += stat.get("size", 0)
            except Exception as e:
                logger.warning("Could not stat %s, assuming 10MB: %s", p, e)
                total_size += 10 * 1024 * 1024

        return {
            "count": file_count,
            "total_size_mb": total_size / (1024 * 1024),
            "ram_mb": _available_ram_mb(),
            "disk_mb": _available_disk_mb(),
        }

    def _select_strategy(self, info: dict) -> AccessStrategy:
        """Choose the best strategy based on resource profile."""
        total_mb = info["total_size_mb"]
        ram_mb = info["ram_mb"]
        disk_mb = info["disk_mb"]

        if ram_mb < _LOW_RAM_MB:
            logger.info("[DAS] Low RAM (%d MB) — forcing CHUNK_STREAM", ram_mb)
            return AccessStrategy.CHUNK_STREAM

        if disk_mb < (total_mb * 2) and disk_mb < _MIN_DISK_FREE_MB:
            logger.info(
                "[DAS] Low disk (%.0f MB) relative to data (%.1f MB) — forcing CHUNK_STREAM",
                disk_mb, total_mb,
            )
            return AccessStrategy.CHUNK_STREAM

        if total_mb < _BATCH_COPY_MAX_MB:
            return AccessStrategy.BATCH_COPY

        if total_mb < _SEQUENTIAL_COPY_MAX_MB and ram_mb > 1024:
            return AccessStrategy.SEQUENTIAL_COPY

        return AccessStrategy.CHUNK_STREAM

    def _batch_download(self, paths: List[str]) -> List[str]:
        """Download all files in parallel to a managed temp directory."""
        self._ensure_temp_dir()
        local_paths: List[str] = []
        n_workers = min(len(paths), 4)

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as ex:
            fut_to_path = {
                ex.submit(self._source.download_if_required, p): p
                for p in paths
            }
            for future in concurrent.futures.as_completed(fut_to_path):
                remote = fut_to_path[future]
                try:
                    tmp = future.result()
                    dest = os.path.join(
                        self._temp_dir,
                        os.path.basename(remote.rstrip("/")),
                    )
                    shutil.move(tmp, dest)
                    self._local_paths[remote] = dest
                    self._temp_files.append(dest)
                    local_paths.append(dest)
                    logger.info(
                        "[DAS] Batch downloaded: %s → %s (%.1f MB)",
                        remote, dest,
                        os.path.getsize(dest) / (1024 * 1024),
                    )
                except Exception as e:
                    logger.error("[DAS] Batch download failed for %s: %s", remote, e)
                    raise DataAccessError(
                        f"Batch download failed for {remote}: {e}"
                    ) from e
        return local_paths

    def _download_one(self, path: str) -> str:
        """Download a single file, cache, and return local path."""
        if path in self._local_paths:
            return self._local_paths[path]

        local = _with_retry(
            lambda: self._source.download_if_required(path),
            label=f"seq_download({path})",
        )
        self._local_paths[path] = local
        self._temp_files.append(local)
        logger.info("[DAS] Sequential downloaded: %s → %s", path, local)
        return local

    def _ensure_temp_dir(self):
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="dva_da_")


# ── Module-level helpers ──────────────────────────────────────

def _available_ram_mb() -> float:
    """Return available RAM in MB."""
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 * 1024)
    except ImportError:
        return 2 * 1024


def _available_disk_mb() -> float:
    """Return free disk space on temp partition in MB."""
    try:
        usage = shutil.disk_usage(tempfile.gettempdir())
        return usage.free / (1024 * 1024)
    except Exception as e:
        logger.debug("Could not determine free disk space, assuming 10GB: %s", e)
        return 10 * 1024


def wrap_source(
    source: Optional[IDataSource],
    file_paths: List[str],
) -> "tuple":
    """Convenience: wrap *source* in a DataAccessor and resolve *file_paths*.

    Returns ``(accessor_or_source, resolved_paths)``.
    If *source* is ``None``, returns ``(None, file_paths)`` unchanged.
    """
    if source is None:
        return None, file_paths
    accessor = DataAccessor(source)
    resolved = accessor.resolve(file_paths)
    register_accessor(accessor)
    return accessor, resolved


def register_accessor(accessor: "DataAccessor"):
    """Register a DataAccessor for lifecycle-managed cleanup."""
    if accessor not in _ACTIVE_ACCESSORS:
        _ACTIVE_ACCESSORS.append(accessor)


def cleanup_all():
    """Clean up all registered DataAccessors.

    Called by :func:`dav_tool.workflow.flush.flush` at end of lifecycle.
    """
    for acc in _ACTIVE_ACCESSORS:
        try:
            acc.cleanup()
        except Exception as e:
            logger.warning("[DAS] Cleanup error: %s", e)
    _ACTIVE_ACCESSORS.clear()

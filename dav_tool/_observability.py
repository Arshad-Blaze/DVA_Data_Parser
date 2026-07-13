"""Centralized observability: metrics, timing, terminal logging."""
import datetime
import gc
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil
import polars as pl
from dav_tool.config import DEFAULT_LOG_LEVEL

_LOG = logging.getLogger("dva")

MAX_HISTORY = 10


# ── DataFrame Registry ──────────────────────────────────────────────
# Tracks every DataFrame created via the register helper so we can
# report live counts, sizes, and owners during development.
_df_registry: List[dict] = []
_registry_lock = threading.Lock()


def register_df(
    df: pl.DataFrame,
    name: str,
    owner: str = "unknown",
    phase: str = "",
) -> pl.DataFrame:
    """Register a DataFrame for memory tracking and return it unchanged."""
    with _registry_lock:
        _df_registry.append({
            "name": name,
            "rows": df.height,
            "cols": len(df.columns),
            "estimated_mb": _estimate_df_mb(df),
            "phase": phase,
            "owner": owner,
            "timestamp": time.time(),
        })
    return df


def unregister_df(name: str, owner: str = ""):
    """Remove DataFrame entries matching *name* (and optionally *owner*)."""
    global _df_registry
    with _registry_lock:
        _df_registry = [
            e for e in _df_registry
            if not (e["name"] == name and (not owner or e["owner"] == owner))
        ]


def release_df(df: Optional[pl.DataFrame], name: str = "", owner: str = ""):
    """Explicitly delete a DataFrame, unregister it, and run GC."""
    if df is not None:
        del df
    if name:
        unregister_df(name, owner)
    gc.collect()


def _estimate_df_mb(df: pl.DataFrame) -> float:
    """Rough estimate of DataFrame memory in MB."""
    try:
        return df.estimated_size("mb")
    except Exception:
        return 0.0


def log_dataframe_summary():
    """Print a snapshot of all registered DataFrames to stdout."""
    with _registry_lock:
        if not _df_registry:
            print("[MEM] No DataFrames tracked.")
            return
        total_mb = 0.0
        print(f"{'[MEM] DataFrame':<30} {'Rows':>10} {'Cols':>5} {'MB':>10} {'Owner':<15} {'Phase':<10}")
        print("-" * 90)
        for e in _df_registry:
            mb = e["estimated_mb"]
            total_mb += mb
            print(f"{'[MEM] ' + e['name']:<30} {e['rows']:>10} {e['cols']:>5} {mb:>10.2f} {e['owner']:<15} {e['phase']:<10}")
        print("-" * 90)
        print(f"{'[MEM] TOTAL':<30} {'':>10} {'':>5} {total_mb:>10.2f} {'':<15} {'':<10}")


def _mem_mb() -> float:
    """Current RSS in MB."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def print_memory_snapshot(label: str = ""):
    """Print memory snapshot with current/peak."""
    current = _mem_mb()
    print(f"[MEM] {label} — RSS: {current:.1f} MB")


# ── End DataFrame Registry ──────────────────────────────────────────


@dataclass
class ProcessingRecord:
    timestamp: str = ""
    files_processed: int = 0
    rows_processed: int = 0
    execution_time: float = 0.0
    peak_memory: float = 0.0
    peak_cpu: float = 0.0
    warnings: int = 0
    errors: int = 0


@dataclass
class ProcessingMetrics:
    files_processed: int = 0
    rows_processed: int = 0
    stores_processed: int = 0
    upcs_processed: int = 0
    chunks_processed: int = 0
    parse_time: float = 0.0
    aggregation_time: float = 0.0
    validation_time: float = 0.0
    report_time: float = 0.0
    total_execution_time: float = 0.0
    peak_memory: float = 0.0
    current_memory: float = 0.0
    peak_cpu: float = 0.0
    current_cpu: float = 0.0
    memory_released_mb: float = 0.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    files_failed: int = 0
    rows_failed: int = 0
    peak_memory_phase: str = ""

    def record(self, phase: str, label: str, elapsed: float):
        """Record elapsed time for a phase group.

        *phase* is one of "aggregation", "validation", "report", "parse".
        Maps to the corresponding time field via _PHASE_MAP.
        """
        attr = _PHASE_MAP.get(phase)
        if attr:
            setattr(self, attr, getattr(self, attr, 0.0) + elapsed)


_PHASE_MAP = {
    "aggregation": "aggregation_time",
    "validation": "validation_time",
    "report": "report_time",
    "parse": "parse_time",
}


def _monitor_mem(pid: int, stop: threading.Event, peak: List[float], interval: float = 0.01):
    proc = psutil.Process(pid)
    while not stop.is_set():
        try:
            mem = proc.memory_info().rss
            if mem > peak[0]:
                peak[0] = mem
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
            break
        stop.wait(interval)


def setup_logging(level=None):
    if _LOG.hasHandlers():
        return
    if level is None:
        level = getattr(logging, DEFAULT_LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(
        "[DVA] [%(asctime)s] %(message)s", datefmt="%H:%M:%S"
    ))
    _LOG.addHandler(handler)
    _LOG.setLevel(level)
    _LOG.propagate = False


def log_phase(message: str):
    _LOG.info("[Phase] %s", message)


class ProcessingTimer:
    def __init__(self, metrics: ProcessingMetrics, phase_group: str, label: str = ""):
        self.metrics = metrics
        self.phase_group = phase_group
        self.label = label
        self._start = None
        self._stop_event = threading.Event()
        self._peak: List[float] = [0.0]
        self._monitor = None
        self._start_mem = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        self._start_mem = _mem_mb()
        self._stop_event.clear()
        self._monitor = threading.Thread(
            target=_monitor_mem,
            args=(os.getpid(), self._stop_event, self._peak),
            daemon=True,
        )
        self._monitor.start()
        log_phase(f"{self.label} STARTED")
        print_memory_snapshot(f"{self.label} START")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_event.set()
        if self._monitor:
            self._monitor.join(timeout=1)
        elapsed = time.perf_counter() - self._start
        peak_mb = self._peak[0] / (1024 * 1024)
        end_mem = _mem_mb()
        attr = _PHASE_MAP.get(self.phase_group)
        if attr:
            setattr(self.metrics, attr, getattr(self.metrics, attr, 0.0) + elapsed)
        self.metrics.total_execution_time += elapsed
        if peak_mb > self.metrics.peak_memory:
            self.metrics.peak_memory = peak_mb
            self.metrics.peak_memory_phase = self.label
        self.metrics.current_memory = end_mem
        released = self._start_mem - end_mem
        if released > 0:
            self.metrics.memory_released_mb += released
        proc = psutil.Process(os.getpid())
        cpu = proc.cpu_percent()
        self.metrics.current_cpu = cpu
        self.metrics.peak_cpu = max(self.metrics.peak_cpu, cpu)
        print_memory_snapshot(f"{self.label} END (peak={peak_mb:.1f}MB)")
        log_phase(f"{self.label} COMPLETED ({elapsed:.2f}s, peak={peak_mb:.1f}MB)")

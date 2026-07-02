"""Centralized observability: metrics, timing, terminal logging."""
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil
from dav_tool.config import DEFAULT_LOG_LEVEL

_LOG = logging.getLogger("dva")


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
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    files_failed: int = 0
    rows_failed: int = 0


_PHASE_MAP = {
    "aggregation": "aggregation_time",
    "validation": "validation_time",
    "report": "report_time",
    "parse": "parse_time",
}


def _monitor_mem(pid: int, stop: threading.Event, peak: List[float]):
    proc = psutil.Process(pid)
    while not stop.is_set():
        try:
            mem = proc.memory_info().rss
            if mem > peak[0]:
                peak[0] = mem
        except (psutil.NoSuchProcess, ProcessLookupError):
            break
        stop.wait(0.01)


def setup_logging(level=None):
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

    def __enter__(self):
        self._start = time.perf_counter()
        self._stop_event.clear()
        self._monitor = threading.Thread(
            target=_monitor_mem,
            args=(os.getpid(), self._stop_event, self._peak),
            daemon=True,
        )
        self._monitor.start()
        log_phase(f"{self.label} STARTED")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_event.set()
        if self._monitor:
            self._monitor.join(timeout=1)
        elapsed = time.perf_counter() - self._start
        peak_mb = self._peak[0] / (1024 * 1024)
        attr = _PHASE_MAP.get(self.phase_group)
        if attr:
            setattr(self.metrics, attr, getattr(self.metrics, attr, 0.0) + elapsed)
        self.metrics.total_execution_time += elapsed
        self.metrics.peak_memory = max(self.metrics.peak_memory, peak_mb)
        self.metrics.current_memory = peak_mb
        proc = psutil.Process(os.getpid())
        cpu = proc.cpu_percent()
        self.metrics.current_cpu = cpu
        self.metrics.peak_cpu = max(self.metrics.peak_cpu, cpu)
        log_phase(f"{self.label} COMPLETED ({elapsed:.2f}s, peak={peak_mb:.1f}MB)")

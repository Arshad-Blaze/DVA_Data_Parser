"""Measure pipeline stage performance with time, memory, and CPU tracking."""
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from dav_tool._observability import _monitor_mem


@dataclass
class StageResult:
    stage: str
    elapsed_s: float
    peak_rss_mb: float
    rows_processed: int
    rows_per_sec: float


def benchmark(
    label: str,
    fn: Callable,
    rows: Optional[int] = None,
    *args,
    **kwargs,
) -> StageResult:
    """Execute fn(*args, **kwargs) and measure elapsed time + peak RSS."""
    stop = threading.Event()
    peak: List[float] = [0.0]
    monitor = threading.Thread(target=_monitor_mem, args=(os.getpid(), stop, peak), daemon=True)
    monitor.start()

    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    t1 = time.perf_counter()

    stop.set()
    monitor.join(timeout=1)

    elapsed = t1 - t0
    peak_mb = peak[0] / (1024 * 1024)
    rows_proc = rows if rows is not None else (len(result) if hasattr(result, "__len__") else 0)
    rps = rows_proc / elapsed if elapsed > 0 else 0.0

    return StageResult(
        stage=label,
        elapsed_s=round(elapsed, 3),
        peak_rss_mb=round(peak_mb, 1),
        rows_processed=rows_proc,
        rows_per_sec=round(rps, 0),
    )

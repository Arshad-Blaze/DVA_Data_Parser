"""Format and output benchmark results."""
from typing import List
from benchmarks.runner import StageResult


SEPARATOR = "-" * 100


def print_results(results: List[StageResult], label: str = "", file_size_mb: int = 0):
    if label:
        print(f"\n{'=' * 100}")
        print(f"  {label}" + (f"  ({file_size_mb} MB)" if file_size_mb else ""))
        print(f"{'=' * 100}")

    print(f"{'Stage':<30} {'Time (s)':>10} {'Peak RSS (MB)':>15} {'Rows':>12} {'Rows/s':>12}")
    print(SEPARATOR)

    for r in results:
        print(f"{r.stage:<30} {r.elapsed_s:>10.3f} {r.peak_rss_mb:>15.1f} {r.rows_processed:>12,} {r.rows_per_sec:>12,.0f}")

    if len(results) > 1:
        total_time = sum(r.elapsed_s for r in results)
        total_rows = max(r.rows_processed for r in results) if results else 0
        peak = max(r.peak_rss_mb for r in results) if results else 0
        print(f"\n{'TOTAL':<30} {total_time:>10.3f} {peak:>15.1f} {total_rows:>12,} {total_rows / total_time:>12,.0f}" if total_time > 0 else "")

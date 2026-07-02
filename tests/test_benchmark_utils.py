"""Smoke tests for benchmark utilities."""
import os
import polars as pl
from benchmarks.data_gen import estimate_rows, generate_delimited, generate_folder
from benchmarks.runner import benchmark, StageResult
from benchmarks.report import print_results


def test_estimate_rows():
    n = estimate_rows(65 * 1000)
    assert n == 1000


def test_generate_delimited_single(tmp_path):
    output = generate_delimited(65 * 10, output_dir=str(tmp_path), num_files=1)
    files = [f for f in os.listdir(output) if f.endswith(".csv")]
    assert len(files) == 1


def test_generate_delimited_multiple(tmp_path):
    output = generate_delimited(65 * 1000, output_dir=str(tmp_path), num_files=5)
    files = [f for f in os.listdir(output) if f.endswith(".csv")]
    assert len(files) == 5


def test_generate_folder(tmp_path):
    output = generate_folder(65 * 10000)
    files = [f for f in os.listdir(output) if f.endswith(".csv")]
    assert 2 <= len(files) <= 20


def test_benchmark_runner(tmp_path):
    def dummy():
        import time
        time.sleep(0.01)
        return pl.DataFrame({"a": [1, 2, 3]})
    result = benchmark("dummy", dummy, rows=3)
    assert isinstance(result, StageResult)
    assert result.stage == "dummy"
    assert result.elapsed_s > 0
    assert result.rows_processed == 3
    assert result.rows_per_sec > 0


def test_benchmark_runner_empty():
    def empty_fn():
        return pl.DataFrame()
    result = benchmark("empty", empty_fn, rows=0)
    assert result.rows_processed == 0
    assert result.elapsed_s >= 0


def test_report_prints(capsys):
    results = [StageResult("test", 0.5, 100.0, 1000, 2000.0)]
    print_results(results, label="Smoke")
    captured = capsys.readouterr()
    assert "test" in captured.out
    assert "0.5" in captured.out

#!/usr/bin/env python3
"""
Benchmark suite runner.

Usage:
    python3 run_benchmarks.py               # Run all sizes
    python3 run_benchmarks.py --size 100    # Run 100 MB only
    python3 run_benchmarks.py --quick       # Run 50 MB + folder only
"""
import argparse
import os
import sys
import tempfile

from dav_tool._aggregators import stream_store_aggregate, stream_item_aggregate
from dav_tool._reports import generate_file_review
from dav_tool.validation.store import storelevelvalidation

from benchmarks.data_gen import generate_delimited, generate_folder
from benchmarks.runner import benchmark
from benchmarks.report import print_results


def _count_data_rows(paths):
    """Count raw rows (minus header) in CSV files."""
    total = 0
    for p in paths:
        with open(p) as f:
            total += sum(1 for _ in f) - 1
    return total


def _csv_paths(data_dir):
    return sorted(
        os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".csv")
    )


def run_single(size_mb: int, seed: int = 42):
    target = size_mb * 1024 * 1024
    data_dir = generate_delimited(target, num_files=1, seed=seed)
    paths = _csv_paths(data_dir)
    rows = _count_data_rows(paths)

    print(f"\n{'#' * 100}")
    print(f"#  BENCHMARK: {size_mb} MB  (1 file, {rows:,} rows)")
    print(f"{'#' * 100}")

    results = []

    # --- Aggregate (store) ---
    r = benchmark(
        "stream_store_aggregate",
        stream_store_aggregate,
        rows=rows,
        file_paths=paths,
        file_type="delimited",
        delimiter=",",
        store_col="Store",
        units_col="Units",
        price_col="Price",
    )
    results.append(r)

    # --- Aggregate (item) ---
    r = benchmark(
        "stream_item_aggregate",
        stream_item_aggregate,
        rows=rows,
        file_paths=paths,
        file_type="delimited",
        delimiter=",",
        upc_col="UPC",
        desc_col="Description",
        units_col="Units",
        dollars_col="Price",
    )
    results.append(r)

    # --- File review ---
    r = benchmark(
        "generate_file_review",
        generate_file_review,
        rows=rows,
        file_paths=paths,
        file_type="delimited",
        delimiter=",",
        store_col="Store",
        upc_col="UPC",
        units_col="Units",
        dollars_col="Price",
    )
    results.append(r)

    # --- Validation (same data for prod + test) ---
    r = benchmark(
        "storelevelvalidation",
        storelevelvalidation,
        rows=rows,
        prod_paths=paths,
        test_paths=paths,
        prod_type="delimited",
        test_type="delimited",
        prod_delim=",",
        test_delim=",",
        prod_layout=None,
        test_layout=None,
        prod_store_col="Store",
        prod_units_col="Units",
        prod_price_col="Price",
        test_store_col="Store",
        test_units_col="Units",
        test_price_col="Price",
        price_type_bau="Total Price",
        price_type_test="Total Price",
        isimplied_dollars_prod=False,
        isimplied_units_prod=False,
        isimplied_dollars_test=False,
        isimplied_units_test=False,
    )
    results.append(r)

    print_results(results, label=f"Single File, {size_mb} MB", file_size_mb=size_mb)
    return results


def run_folder(size_mb: int, seed: int = 42):
    target = size_mb * 1024 * 1024
    data_dir = generate_folder(target, seed=seed)
    paths = _csv_paths(data_dir)
    rows = _count_data_rows(paths)

    print(f"\n{'#' * 100}")
    print(f"#  BENCHMARK: Folder ({size_mb} MB, {len(paths)} files, {rows:,} rows)")
    print(f"{'#' * 100}")

    results = [
        benchmark(
            "stream_store_aggregate",
            stream_store_aggregate,
            rows=rows,
            file_paths=paths,
            file_type="delimited",
            delimiter=",",
            store_col="Store",
            units_col="Units",
            price_col="Price",
        ),
        benchmark(
            "generate_file_review",
            generate_file_review,
            rows=rows,
            file_paths=paths,
            file_type="delimited",
            delimiter=",",
            store_col="Store",
            upc_col="UPC",
            units_col="Units",
            dollars_col="Price",
        ),
    ]
    print_results(results, label=f"Folder, {size_mb} MB ({len(paths)} files)", file_size_mb=size_mb)
    return results


def main():
    parser = argparse.ArgumentParser(description="Run benchmark suite")
    parser.add_argument("--quick", action="store_true", help="Run 50 MB + folder only")
    parser.add_argument("--size", type=int, default=None, help="Run single size (MB)")
    args = parser.parse_args()

    if args.size is not None:
        run_single(args.size)
        run_folder(args.size)
        return

    if args.quick:
        sizes = [50]
    else:
        sizes = [100, 500]

    for mb in sizes:
        run_single(mb)
        run_folder(mb)

    print("\nDone.")


if __name__ == "__main__":
    main()

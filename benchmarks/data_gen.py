"""Generate realistic delimited test data at target sizes."""
import csv
import math
import os
import random
import tempfile


STORE_IDS = [f"S{i:05d}" for i in range(1, 501)]
UPC_CODES = [f"{random.randint(100000, 999999)}" for _ in range(5000)]
DESCRIPTIONS = [
    "Widget Alpha", "Gadget Beta", "Doohickey Gamma", "Thingamajig Delta",
    "Whatchamacallit Epsilon", "Foo Bar", "Baz Qux", "Corflam Floon",
]
_ESTIMATED_BYTES_PER_ROW = 65


def _pick_weighted(pool, rng):
    return pool[rng.randint(0, len(pool) - 1)]


def estimate_rows(target_bytes: int) -> int:
    return math.ceil(target_bytes / _ESTIMATED_BYTES_PER_ROW)


def generate_delimited(
    target_bytes: int,
    output_dir: str = None,
    num_files: int = 1,
    seed: int = 42,
) -> str:
    """Generate CSV files totalling ~target_bytes. Returns the output directory path."""
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="bench_data_")

    total_rows = estimate_rows(target_bytes)
    rows_per_file = math.ceil(total_rows / num_files)
    rng = random.Random(seed)

    for i in range(num_files):
        path = os.path.join(output_dir, f"data_{i:04d}.csv")
        n = rows_per_file if i < num_files - 1 else total_rows - i * rows_per_file
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Store", "UPC", "Description", "Units", "Price"])
            done = set()
            for _ in range(n):
                store = _pick_weighted(STORE_IDS, rng)
                upc = _pick_weighted(UPC_CODES, rng)
                desc = _pick_weighted(DESCRIPTIONS, rng)
                units = rng.randint(1, 50)
                price = round(rng.uniform(1.0, 500.0), 2)
                done.add(upc)
                f.write(f"{store},{upc},{desc},{units},{price}\n")

    return output_dir


def generate_folder(target_bytes: int, seed: int = 42) -> str:
    """Generate a folder of multiple files totalling ~target_bytes."""
    num_files = max(2, min(20, estimate_rows(target_bytes) // 100_000))
    return generate_delimited(target_bytes, num_files=num_files, seed=seed)

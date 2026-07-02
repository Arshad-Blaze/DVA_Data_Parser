import polars as pl
from dav_tool.config import DEFAULT_ENCODING, FALLBACK_ENCODING


def safe_read_csv(path: str, **kwargs) -> pl.DataFrame:
    try:
        return pl.read_csv(path, encoding=FALLBACK_ENCODING, **kwargs)
    except Exception:
        import csv

        with open(path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return pl.DataFrame()
        return pl.DataFrame(rows[1:], schema=rows[0], orient="row")

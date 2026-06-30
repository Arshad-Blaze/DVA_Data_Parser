import polars as pl


def safe_read_csv(path: str, **kwargs) -> pl.DataFrame:
    try:
        return pl.read_csv(path, encoding="utf8-lossy", **kwargs)
    except Exception:
        import csv

        with open(path, "r", encoding="cp1252", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return pl.DataFrame()
        return pl.DataFrame(rows[1:], schema=rows[0], orient="row")

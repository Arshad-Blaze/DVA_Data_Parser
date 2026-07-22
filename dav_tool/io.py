import csv
import logging
import polars as pl
from typing import Optional
from dav_tool.config import DEFAULT_ENCODING, FALLBACK_ENCODING
from dav_tool.datasource.base import IDataSource

logger = logging.getLogger(__name__)


def safe_read_csv(path: str, source: Optional[IDataSource] = None, **kwargs) -> pl.DataFrame:
    local_path = path
    if source is not None:
        try:
            local_path = source.download_if_required(path)
        except Exception:
            logger.warning("Could not download %s via source, falling back to direct path", path)
    try:
        return pl.read_csv(local_path, encoding=FALLBACK_ENCODING, **kwargs)
    except Exception as e:
        logger.warning("Polars read_csv failed for %s, falling back to csv.reader: %s", local_path, e)

        with open(local_path, "r", encoding=DEFAULT_ENCODING, errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return pl.DataFrame()
        return pl.DataFrame(rows[1:], schema=rows[0], orient="row")

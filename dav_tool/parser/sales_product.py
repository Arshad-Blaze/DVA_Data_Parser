"""Sales/Product parser — sales records optionally enriched by a product master.

This is a record-type addressable parser: given a discovery whose files carry
sales data (and optionally a product-master file), it:
  1. Parses the sales file via the delimited parent-child path.
  2. When a product master is supplied, keeps supplier/sub/upc linkage by
     joining sales rows to product attributes.

The parser owns the sales↔product relationship; the UI only supplies the
discovery and an optional product master.
"""
import logging
from typing import Any, List, Optional

import polars as pl

from dav_tool.parser.base import BaseParser, ParsedResult
from dav_tool.parser.factory import register_parser
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


@register_parser
class SalesProductParser(BaseParser):
    name = "sales_product"
    description = "Delimited sales records, optionally joined to a product master."
    priority = 50

    @classmethod
    def supports(cls, discovery: DiscoveryResult) -> bool:
        if discovery.recommended_parser == "sales_product":
            return True
        return (
            discovery.file_type in ("delimited", "csv", "tsv")
            and _product_master_available(discovery)
        )

    def parse(self, discovery: DiscoveryResult, **kwargs: Any) -> ParsedResult:
        warnings: List[str] = []

        transformed = kwargs.get("transformed")
        if transformed is not None and transformed.records is not None:
            sales_df = transformed.records
            joined = bool(transformed.join_operations)
            return ParsedResult(
                canonical_data=sales_df,
                metadata={
                    "parser": self.name,
                    "file_type": discovery.file_type,
                    "rows": sales_df.height,
                    "product_master_joined": joined,
                    "transformed": True,
                },
                discovery=discovery,
                schema=list(sales_df.columns),
                warnings=warnings,
            )

        sales_df = _read_delimited(discovery, kwargs.get("source"))
        product_df = kwargs.get("product_master")
        if product_df is None:
            product_df = _load_product_master(discovery, kwargs.get("source"))

        join_keys = discovery.candidate_keys or []
        link_col = kwargs.get("link_col")
        if product_df is not None and not product_df.is_empty():
            sales_df = _join_sales_product(
                sales_df, product_df, link_col, join_keys, warnings,
            )

        return ParsedResult(
            canonical_data=sales_df,
            metadata={
                "parser": self.name,
                "file_type": discovery.file_type,
                "rows": sales_df.height,
                "product_master_joined": product_df is not None and not product_df.is_empty(),
            },
            discovery=discovery,
            schema=list(sales_df.columns),
            warnings=warnings,
        )


def _read_delimited(discovery: DiscoveryResult, source) -> pl.DataFrame:
    from dav_tool._parsers import parse_delimited_chunks

    delimiter = discovery.delimiter or ","
    chunks = list(parse_delimited_chunks(discovery.file_paths, delimiter, source=source))
    return pl.concat(chunks) if chunks else pl.DataFrame()


def _load_product_master(discovery: DiscoveryResult, source) -> Optional[pl.DataFrame]:
    from dav_tool.io import safe_read_csv

    pm = getattr(discovery, "product_master_path", None)
    if not pm:
        return None
    if pm.lower().endswith((".xlsx", ".xls")):
        return pl.read_excel(pm)
    try:
        return safe_read_csv(pm, separator=discovery.delimiter or ",", source=source)
    except Exception as exc:
        logger.warning("Could not load product master %s: %s", pm, exc)
        return None


def _product_master_available(discovery: DiscoveryResult) -> bool:
    return bool(getattr(discovery, "product_master_path", None))


def _join_sales_product(
    sales_df: pl.DataFrame,
    product_df: pl.DataFrame,
    link_col: Optional[str],
    join_keys: List[Any],
    warnings: List[str],
) -> pl.DataFrame:
    """Merge product attributes into sales rows via a shared key.

    Falls back to the first matching ``candidate_keys`` mapping when no
    explicit *link_col* is provided.
    """
    if sales_df.is_empty() or product_df.is_empty():
        return sales_df

    link = link_col
    if not link and join_keys:
        for k in join_keys:
            if isinstance(k, dict):
                sales_key = k.get("sales_col") or k.get("left")
                prod_key = k.get("product_col") or k.get("right")
                if sales_key in sales_df.columns and prod_key in product_df.columns:
                    link = sales_key
                    break
    if not link:
        warnings.append("No sales/product join key available — no enrichment performed.")
        return sales_df

    prod_key = None
    for k in join_keys:
        if isinstance(k, dict) and (k.get("sales_col") or k.get("left")) == link:
            prod_key = k.get("product_col") or k.get("right")
            break
    prod_key = prod_key or link
    if link not in sales_df.columns or prod_key not in product_df.columns:
        warnings.append(f"Join key {link!r} not present in both datasets — skipped.")
        return sales_df

    try:
        # Normalize join keys to string to tolerate dtype mismatches.
        sales_df = sales_df.with_columns(pl.col(link).cast(pl.Utf8, strict=False))
        product_df = product_df.with_columns(pl.col(prod_key).cast(pl.Utf8, strict=False))
        extra = [c for c in product_df.columns if c != prod_key]
        return sales_df.join(product_df.select([prod_key] + extra), on=link, how="left")
    except Exception as exc:
        warnings.append(f"Sales/product join failed: {exc}")
        return sales_df
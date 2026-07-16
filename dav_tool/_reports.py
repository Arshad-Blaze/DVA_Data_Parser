import gc
import os
import polars as pl
from typing import List, Dict, Optional, Union

from dav_tool._aggregators import stream_store_aggregate, stream_upc_summary
from dav_tool.datasource.base import IDataSource


def _summarize(store_agg: Optional[pl.DataFrame], upc_summary: Optional[pl.DataFrame]) -> dict:
    """Build a single summary dict from store/upc aggregation frames."""
    store_count = store_agg.height if store_agg is not None else 0
    upc_count = upc_summary.height if upc_summary is not None else 0
    total_units = (
        upc_summary["UNITS_SOLD"].sum()
        if upc_summary is not None and "UNITS_SOLD" in upc_summary.columns
        else 0.0
    )
    total_dollars = (
        upc_summary["TOTAL_DOLLARS"].sum()
        if upc_summary is not None and "TOTAL_DOLLARS" in upc_summary.columns
        else 0.0
    )
    return {
        "store_count": store_count,
        "upc_count": upc_count,
        "total_units": float(total_units),
        "total_dollars": round(float(total_dollars), 2),
    }


def generate_file_review(
    file_paths: Union[str, List[str]],
    file_type: str,
    store_col: str,
    upc_col: str,
    units_col: str,
    dollars_col: str,
    date_col: Optional[str] = None,
    delimiter: Optional[str] = None,
    layout: Optional[List[Dict]] = None,
    price_type: str = "Total Price",
    implied_dollars: bool = False,
    implied_units: bool = False,
    start_line: int = 0,
    record_type: Optional[str] = None,
    multiline_record_types: Optional[List[str]] = None,
    multiline_delimiter: str = "|",
    column_names: Optional[List[str]] = None,
    header_prefix: Optional[str] = None,
    header_layout: Optional[List[Dict]] = None,
    detail_layout: Optional[List[Dict]] = None,
    trailer_prefix: Optional[str] = None,
    trailer_layout: Optional[List[Dict]] = None,
    precomputed_store_agg: Optional[pl.DataFrame] = None,
    precomputed_upc_summary: Optional[pl.DataFrame] = None,
    source: Optional[IDataSource] = None,
    quantity_type: str = "units",
    weight_col: Optional[str] = None,
    weight_uom: str = "lb",
    weight_uom_col: Optional[str] = None,
) -> pl.DataFrame:
    """Generate per-file summary statistics.

    When *precomputed_store_agg* and *precomputed_upc_summary* are provided
    (from a previous aggregate pass), they are used directly instead of
    re-parsing the dataset. These summaries are global (aggregated across all
    input files), so the report returns a single consolidated row rather than
    repeating the same global totals once per file.

    When precomputed summaries are NOT provided, each file is streamed
    sequentially (opening a remote stream when *source* is given) and
    aggregated independently, producing one correct row per file.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    file_list = list(file_paths)

    if precomputed_store_agg is not None and precomputed_upc_summary is not None:
        summary = _summarize(precomputed_store_agg, precomputed_upc_summary)
        if len(file_list) == 1:
            fname = os.path.basename(file_list[0])
        else:
            fname = f"{len(file_list)} files (aggregated)"
        return pl.DataFrame([{"filename": fname, **summary}])

    rows = []
    for f in file_list:
        fname = os.path.basename(f)

        sa = stream_store_aggregate(
            [f], file_type, store_col, units_col, dollars_col,
            delimiter=delimiter, layout=layout,
            price_type=price_type,
            implied_dollars=implied_dollars, implied_units=implied_units,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix,
            header_layout=header_layout,
            detail_layout=detail_layout,
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
            source=source,
            quantity_type=quantity_type,
            weight_col=weight_col,
            weight_uom=weight_uom,
            weight_uom_col=weight_uom_col,
        )
        
        ua = stream_upc_summary(
            [f], file_type, upc_col, units_col, dollars_col,
            delimiter=delimiter, layout=layout,
            implied_units=implied_units, implied_dollars=implied_dollars,
            start_line=start_line, record_type=record_type,
            multiline_record_types=multiline_record_types,
            multiline_delimiter=multiline_delimiter,
            column_names=column_names,
            header_prefix=header_prefix,
            header_layout=header_layout,
            detail_layout=detail_layout,
            trailer_prefix=trailer_prefix,
            trailer_layout=trailer_layout,
            source=source,
            quantity_type=quantity_type,
            weight_col=weight_col,
            weight_uom=weight_uom,
            weight_uom_col=weight_uom_col,
        )

        store_count = sa.height if sa is not None and not sa.is_empty() else 0
        upc_count = ua.height if ua is not None and not ua.is_empty() else 0
        total_units = ua["UNITS_SOLD"].sum() if ua is not None and "UNITS_SOLD" in ua.columns else 0.0
        total_dollars = ua["TOTAL_DOLLARS"].sum() if ua is not None and "TOTAL_DOLLARS" in ua.columns else 0.0

        rows.append({
            "filename": fname,
            "store_count": store_count,
            "upc_count": upc_count,
            "total_units": float(total_units),
            "total_dollars": round(float(total_dollars), 2),
        })
        del sa, ua
        gc.collect()

    return pl.DataFrame(rows)


def generate_summary_analytics(
    prod_store_agg: Optional[pl.DataFrame] = None,
    test_store_agg: Optional[pl.DataFrame] = None,
    prod_upc_summary: Optional[pl.DataFrame] = None,
    test_upc_summary: Optional[pl.DataFrame] = None,
    prod_item_comparison: Optional[pl.DataFrame] = None,
    store_diff: Optional[pl.DataFrame] = None,
    execution_metrics: Optional[dict] = None,
    prod_label: str = "BAU",
    test_label: str = "TEST",
) -> pl.DataFrame:
    """Produce a summary analytics dataset from pre-computed outputs.

    All inputs are already-aggregated canonical DataFrames — no re-parsing
    or re-aggregation occurs.  This is the single source of summary analytics
    for the ``Summary`` worksheet.

    Parameters
    ----------
    prod_store_agg, test_store_agg : pl.DataFrame, optional
        Store-level aggregations (``STORE_NUMBER``, ``Units``, ``Totalprice``).
    prod_upc_summary, test_upc_summary : pl.DataFrame, optional
        UPC-level summaries (``UPC_CODE``, ``PRODUCT_DESCRIPTION``,
        ``UNITS_SOLD``, ``TOTAL_DOLLARS``).
    prod_item_comparison : pl.DataFrame, optional
        Comparison of BAU vs TEST UPC data (from ``item_comparison``).
    store_diff : pl.DataFrame, optional
        Store diff output (from ``store_diffs``).
    execution_metrics : dict, optional
        Metrics dict with keys like ``rows_processed``, ``total_execution_time``,
        ``peak_memory``, ``files_processed``.
    prod_label, test_label : str
        Labels for prod/BAU and test columns.

    Returns
    -------
    pl.DataFrame
        A single-row DataFrame with columns for every summary metric.
    """
    metrics = {}

    # -- Store metrics -------------------------------------------------
    prod_store = prod_store_agg if prod_store_agg is not None else pl.DataFrame()
    test_store = test_store_agg if test_store_agg is not None else pl.DataFrame()
    prod_upc = prod_upc_summary if prod_upc_summary is not None else pl.DataFrame()
    test_upc = test_upc_summary if test_upc_summary is not None else pl.DataFrame()

    metrics["Store Count (Prod)"] = prod_store.height if not prod_store.is_empty() else 0
    metrics["Store Count (Test)"] = test_store.height if not test_store.is_empty() else 0
    metrics["UPC Count (Prod)"] = prod_upc.height if not prod_upc.is_empty() else 0
    metrics["UPC Count (Test)"] = test_upc.height if not test_upc.is_empty() else 0

    # Total sales and quantity — prefer UPC-level (granular) over store-level
    for prefix, store_df, upc_df, label in [
        ("Prod", prod_store, prod_upc, "UPC"),
        ("Test", test_store, test_upc, "UPC"),
    ]:
        upc_df = upc_df if not upc_df.is_empty() else pl.DataFrame()
        if not upc_df.is_empty() and "UNITS_SOLD" in upc_df.columns and "TOTAL_DOLLARS" in upc_df.columns:
            tq = float(upc_df["UNITS_SOLD"].sum())
            td = float(upc_df["TOTAL_DOLLARS"].sum())
        elif not store_df.is_empty() and "Units" in store_df.columns and "Totalprice" in store_df.columns:
            tq = float(store_df["Units"].sum())
            td = float(store_df["Totalprice"].sum())
        else:
            tq = td = 0.0
        metrics[f"Total Quantity ({prefix})"] = round(tq, 2)
        metrics[f"Total Sales ({prefix})"] = round(td, 2)

    # -- Top / Bottom Stores -------------------------------------------
    for side, df, label in [
        (prod_label, prod_store, "Prod"),
        (test_label, test_store, "Test"),
    ]:
        if df.is_empty() or "STORE_NUMBER" not in df.columns:
            continue
        sf = df.filter(pl.col("Units").is_not_null())
        top_sales = sf.top_k(5, by="Totalprice") if "Totalprice" in sf.columns else pl.DataFrame()
        top_qty = sf.top_k(5, by="Units")
        bot_sales = sf.bottom_k(5, by="Totalprice") if "Totalprice" in sf.columns else pl.DataFrame()
        bot_qty = sf.bottom_k(5, by="Units")

        for rank_key, rank_df, val_col in [
            (f"Top 5 Stores by Sales ({label})", top_sales, "Totalprice"),
            (f"Top 5 Stores by Quantity ({label})", top_qty, "Units"),
            (f"Bottom 5 Stores by Sales ({label})", bot_sales, "Totalprice"),
            (f"Bottom 5 Stores by Quantity ({label})", bot_qty, "Units"),
        ]:
            if not rank_df.is_empty():
                metrics[rank_key] = "; ".join(
                    f"{r['STORE_NUMBER']}: {r[val_col]:.2f}"
                    for r in rank_df.to_dicts()
                )
            else:
                metrics[rank_key] = ""

    # -- Top / Bottom UPCs ---------------------------------------------
    for side, df, label in [
        (prod_label, prod_upc, "Prod"),
        (test_label, test_upc, "Test"),
    ]:
        if df.is_empty():
            continue
        top_selling = df.top_k(5, by="TOTAL_DOLLARS") if "TOTAL_DOLLARS" in df.columns else pl.DataFrame()
        low_selling = df.bottom_k(5, by="TOTAL_DOLLARS") if "TOTAL_DOLLARS" in df.columns else pl.DataFrame()
        for rank_key, rank_df, val_col in [
            (f"Top 5 Selling UPCs ({label})", top_selling, "TOTAL_DOLLARS"),
            (f"Bottom 5 Selling UPCs ({label})", low_selling, "TOTAL_DOLLARS"),
        ]:
            if not rank_df.is_empty():
                metrics[rank_key] = "; ".join(
                    f"{r.get('UPC_CODE', '?')}: ${r[val_col]:.2f}"
                    for r in rank_df.to_dicts()
                )
            else:
                metrics[rank_key] = ""

    # -- Price / Quantity Variance (from comparison) --------------------
    if prod_item_comparison is not None and not prod_item_comparison.is_empty():
        for var_key, col in [
            (f"Largest Price Variance ({prod_label} vs {test_label})", "Dollar Difference"),
            (f"Largest Quantity Variance ({prod_label} vs {test_label})", "Units Difference"),
        ]:
            if col in prod_item_comparison.columns:
                extreme = prod_item_comparison.sort(col, descending=True).head(5)
                metrics[var_key] = "; ".join(
                    f"{r.get('UPC_CODE', '?')}: {r[col]:+.2f}"
                    for r in extreme.to_dicts()
                )
            else:
                metrics[var_key] = ""

    # -- Growth rates (from store_diff) ---------------------------------
    if store_diff is not None and not store_diff.is_empty():
        for direction, ascending, key_suffix in [
            ("Highest", False, "Growth"),
            ("Lowest", True, "Growth"),
        ]:
            for col_name in ["Units_Diff_%", "Sales_Diff_%"]:
                if col_name in store_diff.columns:
                    ranked = store_diff.sort(col_name, descending=not ascending).head(5)
                    metrics[f"{direction} {col_name} ({key_suffix} — Stores)"] = "; ".join(
                        f"{r['STORE_NUMBER']}: {r[col_name]:+.2f}%"
                        for r in ranked.to_dicts()
                    )

    # -- Averages -------------------------------------------------------
    for side, upc_df, store_df, label in [
        (prod_label, prod_upc, prod_store, "UPC"),
        (test_label, test_upc, test_store, "UPC"),
    ]:
        use_df = upc_df if not upc_df.is_empty() else store_df
        if not use_df.is_empty():
            n = float(use_df.height)
            qty_candidate = "UNITS_SOLD" if "UNITS_SOLD" in use_df.columns else ("Units" if "Units" in use_df.columns else None)
            dol_candidate = "TOTAL_DOLLARS" if "TOTAL_DOLLARS" in use_df.columns else ("Totalprice" if "Totalprice" in use_df.columns else None)
            if qty_candidate and dol_candidate:
                tq = float(use_df[qty_candidate].sum())
                td = float(use_df[dol_candidate].sum())
                metrics[f"Average Basket ({label} — {side})"] = round(td / n, 2) if n > 0 else 0.0
                metrics[f"Average Price ({label} — {side})"] = round(td / tq, 2) if tq > 0 else 0.0
            else:
                metrics[f"Average Basket ({label} — {side})"] = 0.0
                metrics[f"Average Price ({label} — {side})"] = 0.0
        else:
            metrics[f"Average Basket ({label} — {side})"] = 0.0
            metrics[f"Average Price ({label} — {side})"] = 0.0

    # -- Execution metrics ----------------------------------------------
    if execution_metrics:
        for k, v in execution_metrics.items():
            metrics[k.replace("_", " ").title()] = v

    # -- Missing data (from comparison) ---------------------------------
    if prod_item_comparison is not None and not prod_item_comparison.is_empty():
        if "Present In" in prod_item_comparison.columns:
            presence_counts = prod_item_comparison["Present In"].value_counts()
            for row in presence_counts.to_dicts():
                metrics[f"UPCs — {row['Present In']}"] = int(row["count"])

    return pl.DataFrame([metrics])


"""Flush Layer — controlled cleanup at end of workflow lifecycle.

Responsible for:
- Closing SSH connections
- Deleting temporary files
- Releasing DataFrames from registry
- Clearing session state
- Releasing caches
- Logging execution metrics

This is the FINAL layer in the pipeline. Called once per workflow execution.
"""
import gc
import logging
import os
import tempfile
from typing import List, Optional, Set

from dav_tool._observability import (
    ProcessingMetrics, log_phase, print_memory_snapshot,
    release_df, unregister_df, log_dataframe_summary,
)
from dav_tool.datasource.manager import disconnect, is_connected, get_active_source
from dav_tool.workflow.data_access import cleanup_all as cleanup_data_access

logger = logging.getLogger(__name__)

_TRACKED_TEMP_DIRS: Set[str] = set()


def track_temp_dir(path: str):
    """Register a temp directory for later cleanup by flush()."""
    if path and os.path.isdir(path):
        _TRACKED_TEMP_DIRS.add(path)


def flush(
    metrics: Optional[ProcessingMetrics] = None,
    clear_session: bool = False,
    ctx_objects: Optional[List] = None,
):
    """Execute the full flush sequence.

    Call this once at the end of a workflow execution.

    Args:
        metrics: ProcessingMetrics to finalize (logs them if provided).
        clear_session: If True, clear Streamlit session state keys.
        ctx_objects: List of context objects whose DataFrames to release.
    """
    log_phase("Flush Layer STARTED")
    print_memory_snapshot("FLUSH START")

    _flush_temp_files()
    cleanup_data_access()
    _flush_connection()
    _flush_dataframes(ctx_objects)
    _flush_registry()
    if clear_session:
        _flush_session_state()

    gc.collect()

    print_memory_snapshot("FLUSH END")
    if metrics:
        _log_metrics(metrics)
    log_phase("Flush Layer COMPLETED")


def _flush_temp_files():
    """Delete tracked temporary directories."""
    global _TRACKED_TEMP_DIRS
    dirs = list(_TRACKED_TEMP_DIRS)
    for d in dirs:
        try:
            for root, dirs_inner, files_inner in os.walk(d, topdown=False):
                for f in files_inner:
                    os.unlink(os.path.join(root, f))
                for sd in dirs_inner:
                    os.rmdir(os.path.join(root, sd))
            os.rmdir(d)
            logger.debug("Removed temp dir: %s", d)
        except Exception as e:
            logger.warning("Could not remove temp dir %s: %s", d, e)
    _TRACKED_TEMP_DIRS.clear()


def _flush_connection():
    """Disconnect active data source if connected."""
    if is_connected():
        source = get_active_source()
        if source is not None:
            try:
                source.disconnect()
                logger.debug("Disconnected data source")
            except Exception as e:
                logger.warning("Error disconnecting data source: %s", e)
        disconnect()


def _flush_dataframes(ctx_objects: Optional[List]):
    """Release DataFrames from context objects."""
    df_attrs = [
        "store_agg", "item_agg", "upc_summary", "file_review",
        "store_df", "comparison_df", "summary_df",
        "fr_prod", "fr_test",
    ]
    if ctx_objects:
        for ctx in ctx_objects:
            for attr in df_attrs:
                df = getattr(ctx, attr, None)
                if df is not None:
                    release_df(df, name=attr, owner="flush")
                    try:
                        setattr(ctx, attr, None)
                    except Exception as e:
                        logger.debug("Could not clear context attr %s: %s", attr, e)


def _flush_registry():
    """Clear the DataFrame tracking registry."""
    unregister_df("", owner="")


def _flush_session_state():
    """Clear workflow-related Streamlit session state keys."""
    try:
        import streamlit as st
        keys_to_clear = [
            k for k in st.session_state.keys()
            if k.startswith("onb_") or k.startswith("ex_")
            or k.startswith("_cm_")
            or k == "_show_config"
        ]
        for k in keys_to_clear:
            try:
                del st.session_state[k]
            except Exception as e:
                logger.debug("Could not clear session key %s: %s", k, e)
        logger.debug("Cleared %d session state keys", len(keys_to_clear))
    except Exception as e:
        logger.warning("Failed to clear session state: %s", e)


def _log_metrics(metrics: ProcessingMetrics):
    """Log final execution metrics."""
    log_phase(
        f"Final Metrics — {metrics.rows_processed} rows, "
        f"{metrics.total_execution_time:.2f}s, "
        f"{metrics.peak_memory:.1f}MB peak, "
        f"{metrics.peak_cpu:.1f}% CPU, "
        f"{len(metrics.warnings)} warnings, {len(metrics.errors)} errors"
    )
    log_dataframe_summary()

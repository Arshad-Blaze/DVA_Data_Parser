"""Discovery Stage — file detection only.

Responsibility: detect file structure and produce a DiscoveryResult.
Discovery must NOT parse, flatten, or aggregate.  It understands datasets,
not payloads.

After detection, user-supplied configuration (file type, layouts, delimiters)
is merged onto the DiscoveryResult so config-driven retailers keep detection
as the baseline and apply known overrides on top.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from dav_tool.workflow.discovery import detect_file

from ..contracts import DiscoveryResult  # noqa: F401  (re-export for type hints)
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class DiscoveryStage(BaseStage):
    """Produces a DiscoveryResult from the resolved file paths."""

    name = "discovery"
    label = "Discovery"

    def execute(self, ctx) -> StageResult:
        paths = list(ctx.file_paths or [])
        if not paths:
            raise FatalStageError(
                "Discovery requires at least one file path.",
                user_message="No input files selected.",
            )

        result = detect_file(paths, source=ctx.source)
        if result.error:
            raise FatalStageError(
                f"Discovery failed: {result.error}",
                user_message="Could not detect the file structure.",
            )

        _apply_user_overrides(result, ctx.user_config or {})
        ctx.discovery = result
        return StageResult(stage=self.name)


_OVERRIDE_FIELDS = (
    "file_type", "delimiter", "encoding", "start_line", "record_type",
    "header_prefix", "header_layout", "detail_layout", "trailer_prefix",
    "trailer_layout", "layout", "ml_record_types", "ml_delimiter",
    "column_names", "header_removal",
)


def _apply_user_overrides(discovery: DiscoveryResult, user_config: Dict[str, Any]) -> None:
    """Merge user/config overrides onto a detected DiscoveryResult.

    Only fields explicitly present in *user_config* are applied; everything
    else keeps the detection result.
    """
    for key in _OVERRIDE_FIELDS:
        if key not in user_config or user_config[key] in (None, ""):
            continue
        value = user_config[key]
        target = "columns" if key == "column_names" else key
        if target == "ml_record_types":
            target = "ml_record_types"
        if target in {"header_layout", "detail_layout", "trailer_layout", "layout"}:
            # Layout objects must be a list of field dicts.
            if isinstance(value, list):
                setattr(discovery, target, value)
                if target == "layout":
                    # Config-provided layout is authoritative; drop the
                    # detected candidate so parsers use the known layout.
                    discovery.candidate_layout = []
            continue
        if target == "columns":
            discovery.columns = list(value)
            if discovery.schema is None:
                discovery.schema = list(value)
            continue
        setattr(discovery, target, value)
        if target == "file_type" and value in ("fixed", "multiline"):
            discovery.delimiter = None

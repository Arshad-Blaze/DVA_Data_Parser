"""Connection Stage — establishes the active data source.

Responsibility: produce a :class:`ConnectionResult` from the UI-supplied
source.  Owns connection semantics only; performs no detection or parsing.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from dav_tool.datasource.base import IDataSource

from ..contracts import ConnectionResult
from ..stage import BaseStage, StageResult, FatalStageError

logger = logging.getLogger(__name__)


class ConnectionStage(BaseStage):
    """Wraps an existing active source into a ConnectionResult."""

    name = "connection"
    label = "Connection"

    def execute(self, ctx) -> StageResult:
        source = ctx.source
        if source is None:
            # Fall back to the global active source, if any.
            try:
                from dav_tool.datasource.manager import get_active_source
                source = get_active_source()
            except Exception as exc:  # noqa: BLE001 — degrade to fatal
                raise FatalStageError(
                    f"Could not resolve an active data source: {exc}",
                    user_message="No data source is connected.",
                ) from exc

        if source is None:
            raise FatalStageError(
                "No active data source for the Connection Stage.",
                user_message="Please connect a local folder or SSH host first.",
            )

        connection_string = getattr(source, "get_connection_string", lambda: "")()
        supports_direct = bool(getattr(source, "supports_direct_path", False))
        resolved = _resolve_paths(ctx, source)

        ctx.connection = ConnectionResult(
            source=source,
            resolved_paths=tuple(resolved),
            connection_string=connection_string or "",
            supports_direct_path=supports_direct,
        )
        ctx.file_paths = list(resolved)
        return StageResult(stage=self.name)


def _resolve_paths(ctx, source: Optional[IDataSource]) -> List[str]:
    """Resolve requested paths to concrete addresses for downstream stages."""
    requested = list(ctx.file_paths or [])
    if requested:
        return requested
    # No paths requested — nothing to resolve yet (UI drives path selection).
    return []

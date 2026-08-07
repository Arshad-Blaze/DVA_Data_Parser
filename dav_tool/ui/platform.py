"""UI platform accessor — presentation-layer bridge to the bootstrapped platform.

The UI never constructs business objects (engine, registries) directly.  It
reads them from the ServiceRegistry created by :func:`bootstrap()`.  This
module is part of the Presentation layer: it only *reads* already-initialized
services, it never performs parsing, validation, or orchestration logic.

The UI calls :func:`bootstrap()` once at startup (see ``ui/app.py``); pages
then request services through :func:`get_workflow_engine` and friends.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from dav_tool.pipeline.bootstrap import bootstrap, get_service_registry

logger = logging.getLogger(__name__)


def ensure_bootstrap() -> Any:
    """Ensure the platform is bootstrapped exactly once and return services.

    Safe to call from any page; the underlying :func:`bootstrap` is idempotent
    and thread-safe.  Returns the ServiceRegistry.
    """
    try:
        services = get_service_registry()
    except RuntimeError:
        services = bootstrap()
    return services


def get_workflow_engine():
    """Return the WorkflowEngine from the bootstrapped service registry."""
    return ensure_bootstrap().get("workflow_engine")


def get_pipeline_registry():
    """Return the PipelineRegistry from the bootstrapped service registry."""
    return ensure_bootstrap().get("pipeline_registry")

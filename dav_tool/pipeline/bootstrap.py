"""Bootstrap — one-time initialization of the DVA Platform.

Initializes (only once):
- Service Registry
- Pipeline Registry + standard pipelines
- Workflow Engine
- Rule Registry + standard rules
- Parser Registry (populated by parser package imports)
- Configuration
- Logging
- Observability

The UI calls :func:`bootstrap()` once at startup and reuses the initialized
registries and engine for every retailer/pipeline.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_INITIALIZED = False
_LOCK = threading.Lock()
_SERVICES: Optional[ServiceRegistry] = None


class ServiceRegistry:
    """Minimal service registry holding the platform singletons.

    Services are looked up by name; the UI consumes these via the Bootstrap.
    """

    def __init__(self) -> None:
        self._services: dict = {}

    def register(self, name: str, service) -> None:
        self._services[name] = service

    def get(self, name: str):
        return self._services.get(name)

    def names(self) -> list:
        return sorted(self._services.keys())


def bootstrap(
    *,
    tolerance_pct: float = 5.0,
    log_level: Optional[str] = None,
) -> ServiceRegistry:
    """Initialize the platform exactly once.

    Idempotent: subsequent calls return the already-built registry.
    """
    global _INITIALIZED, _SERVICES
    with _LOCK:
        if _INITIALIZED:
            return _SERVICES

        _setup_logging(log_level)

        services = ServiceRegistry()

        # ── Configuration ──────────────────────────────────────────
        from dav_tool import config as app_config
        services.register("config", app_config)

        # ── Observability ──────────────────────────────────────────
        from dav_tool import _observability
        services.register("observability", _observability)

        # ── Parser Registry (populated at import time) ─────────────
        import dav_tool.parser  # noqa: F401  — triggers @register_parser decorators
        from dav_tool.parser.factory import _REGISTRY as parser_registry
        services.register("parser_registry", parser_registry)
        services.register("parser_factory", _parser_factory())

        # ── Pipeline Registry + standard pipelines ─────────────────
        from dav_tool.pipeline.registry import PipelineRegistry
        from dav_tool.pipeline.standard_pipelines import register_standard_pipelines

        pipeline_registry = PipelineRegistry()
        register_standard_pipelines(pipeline_registry)
        services.register("pipeline_registry", pipeline_registry)

        # ── Rule Registry + standard rules ─────────────────────────
        from dav_tool.validation.rules.registry import RuleRegistry
        from dav_tool.validation.rules.loader import register_standard_rules

        rule_registry = RuleRegistry()
        register_standard_rules(rule_registry, tolerance_pct=tolerance_pct)
        services.register("rule_registry", rule_registry)

        # ── Workflow Engine ────────────────────────────────────────
        from dav_tool.pipeline.engine import WorkflowEngine
        services.register("workflow_engine", WorkflowEngine(registry=pipeline_registry))

        _INITIALIZED = True
        _SERVICES = services
        logger.info("DVA Platform bootstrapped — services=%s", services.names())
        return services


def _parser_factory():
    from dav_tool.parser.factory import default_factory
    return default_factory


def get_service_registry() -> ServiceRegistry:
    """Return the existing registry (raises if bootstrap() was never called)."""
    if _SERVICES is None:
        raise RuntimeError("bootstrap() has not been called yet.")
    return _SERVICES


def reset_bootstrap() -> None:
    """Reset the initialized flag (test helper only)."""
    global _INITIALIZED, _SERVICES
    _INITIALIZED = False
    _SERVICES = None


def _setup_logging(log_level: Optional[str] = None) -> None:
    from dav_tool._observability import setup_logging
    setup_logging(log_level or "INFO")

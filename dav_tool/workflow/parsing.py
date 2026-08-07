"""Parsing Service — workflow facade over the Parser Factory.

Workflow-level entry point for parsing.  The UI calls this service instead
of reaching into the Parser Factory directly; the service owns parser
selection via the factory and keeps the UI free of parser logic.
"""
from __future__ import annotations

import logging

from dav_tool.parser import default_factory
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


def parse_from_discovery(
    discovery: DiscoveryResult,
    source=None,
):
    """Parse a discovery result through the Parser Factory.

    Selects the parser via ``recommended_parser`` (falling back to factory
    ``supports()`` scanning) and returns the parsed result.
    """
    if not discovery.file_paths:
        raise ValueError("Discovery must contain at least one file path.")

    parser = default_factory.create(discovery)
    return parser.parse(discovery, source=source)

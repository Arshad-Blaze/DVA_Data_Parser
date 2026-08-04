"""Parser Factory — selects and instantiates the right parser.

The factory is the ONLY component that knows which parser handles a given
DiscoveryResult.  It is parser-driven: given a
:class:`~dav_tool.workflow.discovery.DiscoveryResult`, it either uses the
recommended parser name (``recommended_parser``) or falls back to iterating
registered parsers and asking each ``supports()``.

The UI never selects a parser directly — it calls ``ParserFactory.create()``.
"""
import logging
from typing import Dict, List, Optional, Type

from dav_tool.parser.base import BaseParser, ParserError
from dav_tool.workflow.discovery import DiscoveryResult

logger = logging.getLogger(__name__)


class ParserRegistry:
    """Registry mapping parser names to parser classes."""

    def __init__(self) -> None:
        self._parsers: Dict[str, Type[BaseParser]] = {}

    def register(self, parser: Type[BaseParser]) -> Type[BaseParser]:
        if not parser.name:
            raise ValueError(f"Parser class {parser.__name__} has no name")
        self._parsers[parser.name] = parser
        return parser

    def get(self, name: str) -> Optional[Type[BaseParser]]:
        return self._parsers.get(name)

    def names(self) -> List[str]:
        return sorted(self._parsers.keys())


#: Module-level registry shared across the app.
_REGISTRY = ParserRegistry()


def register_parser(parser: Type[BaseParser]) -> Type[BaseParser]:
    """Decorator to register a parser class at import time."""
    _REGISTRY.register(parser)
    return parser


class ParserFactory:
    """Selects and instantiates parsers from a DiscoveryResult."""

    def __init__(self, registry: Optional[ParserRegistry] = None) -> None:
        self._registry = registry or _REGISTRY

    def available_parsers(self) -> List[str]:
        return self._registry.names()

    def get_parser(self, name: str) -> BaseParser:
        cls = self._registry.get(name)
        if cls is None:
            raise ParserError(
                f"No parser registered under name '{name}'. "
                f"Available: {', '.join(self._registry.names())}"
            )
        return cls()

    def create(self, discovery: DiscoveryResult) -> BaseParser:
        """Return a parser instance able to handle *discovery*.

        Prefers ``discovery.recommended_parser`` when present and registered;
        otherwise asks every registered parser ``supports()`` and picks the
        first match.
        """
        recommended = discovery.recommended_parser
        if recommended:
            parser = self._registry.get(recommended)
            if parser is not None:
                return parser()

        # Order registered parsers so more specific ones win the fallback.
        # Lower priority value = higher precedence.
        ordered = sorted(
            (self._registry.get(n) for n in self._registry.names()),
            key=lambda c: (getattr(c, "priority", 100), c.name),
        )
        for cls in ordered:
            try:
                if cls.supports(discovery):
                    return cls()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("supports() raised for %s: %s", cls.name, exc)

        raise ParserError(
            "No parser could handle the discovery result "
            f"(file_type={discovery.file_type!r}). "
            f"Registered: {', '.join(self._registry.names())}"
        )

    def parse(self, discovery: DiscoveryResult, **kwargs) -> object:
        parser = self.create(discovery)
        return parser.parse(discovery, **kwargs)


#: Convenience singleton.
default_factory = ParserFactory()
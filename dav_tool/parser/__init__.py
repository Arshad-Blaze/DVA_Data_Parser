"""Parser Factory subsystem — parser-driven pipeline.

This package owns parser selection and execution.  The UI never selects a
parser; it consumes ``ParserFactory`` results only.

Pipeline:
    Discovery → ParserFactory → SpecificParser → ParsedResult
                                               → Canonical Dataset
"""
# Import parser modules so their @register_parser decorators run at import time.
from dav_tool.parser import delimited  # noqa: F401
from dav_tool.parser import excel  # noqa: F401
from dav_tool.parser import fixed_width  # noqa: F401
from dav_tool.parser import parent_child  # noqa: F401
from dav_tool.parser import record_based  # noqa: F401
from dav_tool.parser import sales_product  # noqa: F401

from dav_tool.parser.base import BaseParser, ParsedResult, ParserError
from dav_tool.parser.record_tree import RecordNode, RecordTree
from dav_tool.parser.factory import (
    ParserFactory,
    ParserRegistry,
    default_factory,
    register_parser,
)

__all__ = [
    "BaseParser",
    "ParsedResult",
    "ParserError",
    "RecordNode",
    "RecordTree",
    "ParserFactory",
    "ParserRegistry",
    "default_factory",
    "register_parser",
]
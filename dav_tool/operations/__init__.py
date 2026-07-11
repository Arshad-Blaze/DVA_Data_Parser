"""Data Operations Framework — reusable, config-driven operations on canonical data.

Every operation:
- Accepts a ``pl.DataFrame`` (canonical dataset)
- Returns an ``OperationResult``
- Knows nothing about retailer-specific columns
- Is fully configuration driven
"""

from dav_tool.operations.base import IDataOperation, OperationResult, OperationOptions
from dav_tool.operations.registry import register, get, list_operations
from dav_tool.operations.aggregate import AggregateOperation, AggregateOptions
from dav_tool.operations.filter import FilterOperation, FilterOptions, FilterCondition
from dav_tool.operations.sort import SortOperation, SortOptions, SortColumn
from dav_tool.operations.sample import SampleOperation, SampleOptions
from dav_tool.operations.statistics import StatisticsOperation, StatisticsOptions
from dav_tool.operations.export import ExportOperation, ExportOptions
from dav_tool.operations.preview import PreviewOperation, PreviewOptions

# Auto-register all built-in operations
register(AggregateOperation())
register(FilterOperation())
register(SortOperation())
register(SampleOperation())
register(StatisticsOperation())
register(ExportOperation())
register(PreviewOperation())

__all__ = [
    "IDataOperation", "OperationResult", "OperationOptions",
    "register", "get", "list_operations",
    "AggregateOperation", "AggregateOptions",
    "FilterOperation", "FilterOptions", "FilterCondition",
    "SortOperation", "SortOptions", "SortColumn",
    "SampleOperation", "SampleOptions",
    "StatisticsOperation", "StatisticsOptions",
    "ExportOperation", "ExportOptions",
    "PreviewOperation", "PreviewOptions",
]

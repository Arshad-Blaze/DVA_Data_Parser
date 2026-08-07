"""Standard pipelines — compositions of reusable stages.

Every pipeline follows the identical stage sequence.  Pipelines differ only
in the parsing stage selected for a given DiscoveryResult.  Each pipeline
produces exactly one ParsedDataset.
"""
from __future__ import annotations

from .registry import Pipeline, PipelineRegistry
from .stages.aggregation import AggregationStage
from .stages.canonical_dataset import CanonicalDatasetStage
from .stages.canonical_mapping import CanonicalMappingStage
from .stages.connection import ConnectionStage
from .stages.data_quality import DataQualityStage
from .stages.dataset_graph import DatasetGraphStage
from .stages.discovery import DiscoveryStage
from .stages.insights import InsightsEngineStage
from .stages.parser_pipeline import ParserPipelineStage
from .stages.quantity_resolution import QuantityResolutionStage
from .stages.reporting import ReportingStage
from .stages.transform_plan import TransformationPlanningStage
from .stages.transformation_engine import TransformationEngineStage
from .stages.validation import ValidationStage


def _base_stages(
    connection: bool = False,
    discovery: bool = False,
    graph: bool = False,
    plan: bool = False,
    transform: bool = False,
    parser: bool = True,
    canonical_mapping: bool = True,
    quantity_resolution: bool = True,
    canonical: bool = True,
    data_quality: bool = True,
    aggregation: bool = True,
    validation: bool = True,
    insights: bool = True,
    reporting: bool = True,
) -> list:
    stages = []
    if connection:
        stages.append(ConnectionStage())
    if discovery:
        stages.append(DiscoveryStage())
    if graph:
        stages.append(DatasetGraphStage())
    if plan:
        stages.append(TransformationPlanningStage())
    if transform:
        stages.append(TransformationEngineStage())
    if parser:
        stages.append(ParserPipelineStage())
    if canonical_mapping:
        stages.append(CanonicalMappingStage())
    if quantity_resolution:
        stages.append(QuantityResolutionStage())
    if canonical:
        stages.append(CanonicalDatasetStage())
    if data_quality:
        stages.append(DataQualityStage())
    if aggregation:
        stages.append(AggregationStage())
    if validation:
        stages.append(ValidationStage())
    if insights:
        stages.append(InsightsEngineStage())
    if reporting:
        stages.append(ReportingStage())
    return stages


def build_standard_delimited_pipeline(
    connection: bool = True,
    discovery: bool = True,
    graph: bool = True,
    plan: bool = True,
    transform: bool = True,
    aggregation: bool = True,
    validation: bool = True,
    reporting: bool = True,
) -> Pipeline:
    """Standard delimited pipeline (CSV/TSV flat files)."""
    return Pipeline(
        name="standard_delimited",
        description="Flat delimited files (CSV/TSV) — the default pipeline.",
        stages=_base_stages(
            connection=connection,
            discovery=discovery,
            graph=graph,
            plan=plan,
            transform=transform,
            parser=True,
            canonical=True,
            aggregation=aggregation,
            validation=validation,
            reporting=reporting,
        ),
    )


def build_fixed_width_pipeline(
    connection: bool = True,
    discovery: bool = True,
    graph: bool = True,
    plan: bool = True,
    transform: bool = True,
    aggregation: bool = True,
    validation: bool = True,
    reporting: bool = True,
) -> Pipeline:
    """Fixed-width record pipeline."""
    return Pipeline(
        name="fixed_width",
        description="Fixed-width record files.",
        stages=_base_stages(
            connection=connection,
            discovery=discovery,
            graph=graph,
            plan=plan,
            transform=transform,
            parser=True,
            canonical=True,
            aggregation=aggregation,
            validation=validation,
            reporting=reporting,
        ),
    )


def build_record_based_pipeline(
    connection: bool = True,
    discovery: bool = True,
    graph: bool = True,
    plan: bool = True,
    transform: bool = True,
    aggregation: bool = True,
    validation: bool = True,
    reporting: bool = True,
) -> Pipeline:
    """Record-based (HEB / multiline) pipeline — zero UI interaction."""
    return Pipeline(
        name="record_based",
        description="Record-based / multiline (HEB) files.",
        stages=_base_stages(
            connection=connection,
            discovery=discovery,
            graph=graph,
            plan=plan,
            transform=transform,
            parser=True,
            canonical=True,
            aggregation=aggregation,
            validation=validation,
            reporting=reporting,
        ),
    )


def build_sales_product_pipeline(
    connection: bool = True,
    discovery: bool = True,
    graph: bool = True,
    plan: bool = True,
    transform: bool = True,
    aggregation: bool = True,
    validation: bool = True,
    reporting: bool = True,
) -> Pipeline:
    """Sales + Product pipeline (delimited sales with optional product master)."""
    return Pipeline(
        name="sales_product",
        description="Delimited sales joined with an optional product master.",
        stages=_base_stages(
            connection=connection,
            discovery=discovery,
            graph=graph,
            plan=plan,
            transform=transform,
            parser=True,
            canonical=True,
            aggregation=aggregation,
            validation=validation,
            reporting=reporting,
        ),
    )


def build_excel_pipeline(
    connection: bool = True,
    discovery: bool = True,
    graph: bool = True,
    plan: bool = True,
    transform: bool = True,
    aggregation: bool = True,
    validation: bool = True,
    reporting: bool = True,
) -> Pipeline:
    """Excel workbook pipeline."""
    return Pipeline(
        name="excel",
        description="Excel workbooks.",
        stages=_base_stages(
            connection=connection,
            discovery=discovery,
            graph=graph,
            plan=plan,
            transform=transform,
            parser=True,
            canonical=True,
            aggregation=aggregation,
            validation=validation,
            reporting=reporting,
        ),
    )


def register_standard_pipelines(
    registry: PipelineRegistry,
    *,
    full: bool = True,
) -> None:
    """Register the standard pipelines on *registry*.

    ``full=True`` composes the complete stage chain (connection through
    reporting).  ``full=False`` composes only the processing spine
    (transformation → parser → canonical → aggregation → validation →
    reporting), which is used by the UI to drive already-discovered files.
    """
    kwargs = {} if full else dict(
        connection=False, discovery=False, graph=False, plan=False, transform=False,
    )
    registry.register(build_standard_delimited_pipeline(**kwargs))
    registry.register(build_fixed_width_pipeline(**kwargs))
    registry.register(build_record_based_pipeline(**kwargs))
    registry.register(build_sales_product_pipeline(**kwargs))
    registry.register(build_excel_pipeline(**kwargs))

    # Aliases so parser names and file types resolve to a pipeline.
    registry.register_alias("delimited", "standard_delimited")
    registry.register_alias("csv", "standard_delimited")
    registry.register_alias("tsv", "standard_delimited")
    registry.register_alias("tab", "standard_delimited")
    registry.register_alias("fixed", "fixed_width")
    registry.register_alias("multiline", "record_based")
    registry.register_alias("parent_child", "record_based")
    registry.register_alias("sales_product", "sales_product")
    registry.register_alias("excel", "excel")

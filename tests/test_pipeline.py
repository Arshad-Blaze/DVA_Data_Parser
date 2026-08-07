"""Tests for the pipeline package (contracts, registry, engine, stages, rules).

The pipeline layer is the target architecture for the sprint:
UI → Workflow Engine → Pipeline Registry → Pipeline Context → stages.
These tests exercise the new contracts and orchestration without touching
the legacy UI or the Operation Layer.
"""
import time

import polars as pl
import pytest

from dav_tool.pipeline.bootstrap import bootstrap, get_service_registry, reset_bootstrap
from dav_tool.pipeline.contracts import (
    AggregatedDataset,
    ConnectionResult,
    DatasetGraph,
    DatasetNode,
    ParsedDataset,
    ReportDataset,
    RuleResult,
    TransformedDataset,
    TransformationPlan,
    ValidationDataset,
)
from dav_tool.pipeline.context import PipelineContext
from dav_tool.pipeline.engine import WorkflowEngine
from dav_tool.pipeline.factory import PipelineFactory
from dav_tool.pipeline.registry import Pipeline, PipelineRegistry
from dav_tool.pipeline.stage import (
    BaseStage,
    FatalStageError,
    RecoverableStageError,
    StageError,
    StageResult,
)
from dav_tool.pipeline.standard_pipelines import (
    build_standard_delimited_pipeline,
    register_standard_pipelines,
)
from dav_tool.validation.rules.difference import StoreDifferenceRule
from dav_tool.validation.rules.integrity import (
    DuplicateUPCRule,
    MissingStoreRule,
    NegativeSalesRule,
)
from dav_tool.validation.rules.registry import RuleRegistry, ValidationRule
from dav_tool.validation.rules.tolerance import CustomRule, ToleranceRule
from dav_tool.workflow.discovery import DiscoveryResult


# ── Contracts ────────────────────────────────────────────────────────


def test_contracts_are_frozen():
    """Pipeline contracts must be immutable dataclasses."""
    for cls in (
        ConnectionResult,
        DatasetNode,
        DatasetGraph,
        TransformationPlan,
        TransformedDataset,
        ParsedDataset,
        AggregatedDataset,
        RuleResult,
        ValidationDataset,
        ReportDataset,
    ):
        with pytest.raises(Exception):
            obj = cls()
            if cls is ConnectionResult:
                obj.source = object()
            elif cls is DatasetNode:
                obj.role = "x"
            elif cls is DatasetGraph:
                obj.confidence = 1.0
            elif cls is TransformationPlan:
                obj.header_removal = 5
            elif cls is TransformedDataset:
                obj.operations = ("x",)
            elif cls is ParsedDataset:
                obj.row_count = 9
            elif cls is AggregatedDataset:
                obj.level = "store"
            elif cls is RuleResult:
                obj.passed = False
            elif cls is ValidationDataset:
                obj.errors = ("x",)
            elif cls is ReportDataset:
                obj.metrics = {}


def test_dataset_graph_primary_returns_sales_node():
    sales = DatasetNode(role="sales", file_paths=("a.csv",))
    product = DatasetNode(role="product", file_paths=("b.csv",))
    graph = DatasetGraph(datasets=(product, sales))
    assert graph.primary is sales


def test_dataset_graph_primary_falls_back_to_first_node():
    node = DatasetNode(role="other", file_paths=("a.csv",))
    graph = DatasetGraph(datasets=(node,))
    assert graph.primary is node


def test_pipeline_rejects_non_stage_members():
    with pytest.raises(TypeError):
        Pipeline(name="bad", stages=("not-a-stage",))


# ── Pipeline Context ──────────────────────────────────────────────────


def test_context_sections_and_has_flags():
    ctx = PipelineContext()
    assert not ctx.has_connection
    ctx.connection = ConnectionResult()
    assert ctx.has_connection
    assert ctx.summarize()["pipeline"] == "standard_delimited"


def test_context_records_errors_and_warnings():
    ctx = PipelineContext()
    ctx.add_warning("w1")
    ctx.add_error("e1")
    assert ctx.warnings == ["w1"]
    assert ctx.errors == ["e1"]


# ── Stage framework ──────────────────────────────────────────────────


class _OkStage(BaseStage):
    name = "ok"
    label = "OK"

    def execute(self, ctx) -> StageResult:
        ctx.marker = "ran"
        return StageResult(stage=self.name)


class _RecoverableStage(BaseStage):
    name = "flaky"
    label = "Flaky"
    max_retries = 2
    retry_delay = 0.0

    def execute(self, ctx) -> StageResult:
        ctx.attempts = getattr(ctx, "attempts", 0) + 1
        if ctx.attempts <= 2:
            raise RecoverableStageError("transient")
        return StageResult(stage=self.name)


class _FatalStage(BaseStage):
    name = "boom"
    label = "Boom"

    def execute(self, ctx) -> StageResult:
        raise FatalStageError("cannot continue")


def test_stage_run_success():
    stage = _OkStage()
    ctx = PipelineContext()
    result = stage.run(ctx)
    assert result.success
    assert result.stage == "ok"
    assert ctx.marker == "ran"


def test_recoverable_stage_retries_then_succeeds():
    stage = _RecoverableStage()
    ctx = PipelineContext()
    result = stage.run(ctx)
    assert result.success
    assert ctx.attempts == 3


def test_fatal_stage_error_returns_failed_result():
    stage = _FatalStage()
    ctx = PipelineContext()
    result = stage.run(ctx)
    assert not result.success
    assert "cannot continue" in result.errors[0]


def test_stage_error_base_class():
    err = StageError("m", user_message="friendly")
    assert err.user_message == "friendly"
    assert not err.recoverable


# ── Pipeline Registry ────────────────────────────────────────────────


def _mk_pipeline(name, stages):
    return Pipeline(name=name, stages=tuple(stages))


def test_registry_register_and_get():
    reg = PipelineRegistry()
    p = _mk_pipeline("p1", (_OkStage(),))
    reg.register(p)
    assert reg.get("p1") is p
    assert "p1" in reg.names()


def test_registry_alias_resolves():
    reg = PipelineRegistry()
    reg.register(_mk_pipeline("target", (_OkStage(),)))
    reg.register_alias("nick", "target")
    assert reg.get("nick").name == "target"


def test_registry_select_by_recommended_parser():
    reg = PipelineRegistry()
    reg.register(_mk_pipeline("delimited", (_OkStage(),)))
    reg.register(_mk_pipeline("fixed", (_OkStage(),)))
    discovery = DiscoveryResult(file_paths=["a.txt"], recommended_parser="fixed")
    assert reg.select(discovery).name == "fixed"


def test_registry_select_falls_back_to_supports():
    class _OnlyFixed(BaseStage):
        name = "parser_pipeline"
        label = "P"

        @classmethod
        def supports(cls, discovery):
            return discovery.file_type == "fixed"

        def execute(self, ctx) -> StageResult:
            return StageResult(stage=self.name)

    reg = PipelineRegistry()
    reg.register(_mk_pipeline("delimited", (_OkStage(),)))
    fixed = _mk_pipeline("fixed", (_OnlyFixed(),))
    reg.register(fixed)
    discovery = DiscoveryResult(file_paths=["a.txt"], file_type="fixed")
    assert reg.select(discovery).name == "fixed"


def test_registry_select_unknown_recommendation_falls_through():
    reg = PipelineRegistry()
    reg.register(_mk_pipeline("standard_delimited", (_OkStage(),)))
    discovery = DiscoveryResult(file_paths=["a.csv"], recommended_parser="nope")
    assert reg.select(discovery).name == "standard_delimited"


# ── Workflow Engine ──────────────────────────────────────────────────


def test_engine_runs_all_stages_in_order():
    reg = PipelineRegistry()

    class _A(BaseStage):
        name = "a"

        def execute(self, ctx) -> StageResult:
            return StageResult(stage=self.name)

    class _B(BaseStage):
        name = "b"

        def execute(self, ctx) -> StageResult:
            return StageResult(stage=self.name)

    reg.register(Pipeline(name="two", stages=(_A(), _B())))
    ctx = PipelineContext()
    run = WorkflowEngine(registry=reg, context=ctx).run(ctx)
    assert run.pipeline_name == "two"
    assert run.stages_completed == ("a", "b")
    assert ctx.completed_stages == ["a", "b"]


def test_engine_skips_already_completed_stages():
    reg = PipelineRegistry()

    class _A(BaseStage):
        name = "a"

        def execute(self, ctx) -> StageResult:
            return StageResult(stage=self.name)

    class _B(BaseStage):
        name = "b"

        def execute(self, ctx) -> StageResult:
            return StageResult(stage=self.name)

    reg.register(Pipeline(name="two", stages=(_A(), _B())))
    ctx = PipelineContext()
    ctx.completed_stages.append("a")
    engine = WorkflowEngine(registry=reg, context=ctx)
    run = engine.run(ctx)
    assert run.stages_completed == ("a", "b")
    assert run.pipeline_name == "two"


def test_engine_fatal_stage_records_error():
    reg = PipelineRegistry()
    reg.register(Pipeline(name="boom", stages=(_FatalStage(),)))
    ctx = PipelineContext()
    engine = WorkflowEngine(registry=reg, context=ctx)
    run = engine.run(ctx)
    assert len(run.errors) >= 1
    assert "boom" in run.errors[0]


def test_engine_selects_pipeline_from_discovery():
    reg = PipelineRegistry()
    reg.register(_mk_pipeline("fixed", (_OkStage(),)))
    reg.register(_mk_pipeline("standard_delimited", (_OkStage(),)))
    ctx = PipelineContext()
    ctx.discovery = DiscoveryResult(file_paths=["a"], recommended_parser="fixed")
    engine = WorkflowEngine(registry=reg, context=ctx)
    assert engine.select_pipeline(ctx).name == "fixed"


# ── Pipeline Factory ─────────────────────────────────────────────────


def test_factory_lists_standard_pipelines():
    reg = PipelineRegistry()
    register_standard_pipelines(reg)
    factory = PipelineFactory(registry=reg)
    names = factory.available_pipelines()
    for expected in ("excel", "fixed_width", "record_based", "sales_product", "standard_delimited"):
        assert expected in names


def test_standard_pipeline_composition():
    reg = PipelineRegistry()
    register_standard_pipelines(reg)
    pipeline = reg.get("standard_delimited")
    assert pipeline is not None
    stage_names = [s.name for s in pipeline.stages]
    assert stage_names == [
        "connection",
        "discovery",
        "dataset_graph",
        "transform_plan",
        "transformation_engine",
        "parser_pipeline",
        "canonical_mapping",
        "quantity_resolution",
        "canonical_dataset",
        "data_quality",
        "aggregation",
        "validation",
        "insights",
        "reporting",
    ]


def test_standard_pipeline_spine_without_processing_prefix():
    reg = PipelineRegistry()
    register_standard_pipelines(reg, full=False)
    pipeline = reg.get("standard_delimited")
    stage_names = [s.name for s in pipeline.stages]
    assert stage_names[0] == "parser_pipeline"
    assert "reporting" in stage_names


def test_build_standard_delimited_aliases():
    reg = PipelineRegistry()
    register_standard_pipelines(reg)
    for alias in ("delimited", "csv", "tsv"):
        assert reg.get(alias).name == "standard_delimited"


# ── Bootstrap ────────────────────────────────────────────────────────


def test_bootstrap_registers_services():
    reset_bootstrap()
    services = bootstrap(tolerance_pct=5.0)
    for name in (
        "config",
        "observability",
        "parser_registry",
        "parser_factory",
        "pipeline_registry",
        "rule_registry",
        "workflow_engine",
    ):
        assert services.get(name) is not None, f"missing service: {name}"


def test_bootstrap_is_idempotent():
    reset_bootstrap()
    services1 = bootstrap()
    services2 = bootstrap()
    assert services1 is services2


def test_get_service_registry_requires_bootstrap():
    reset_bootstrap()
    with pytest.raises(RuntimeError):
        get_service_registry()


# ── Validation Rules ─────────────────────────────────────────────────


def _two_sided_dataset():
    prod_store = pl.DataFrame({"STORE_NUMBER": ["S1", "S2"], "Units": [100.0, 200.0], "Totalprice": [1000.0, 2000.0]})
    test_store = pl.DataFrame({"STORE_NUMBER": ["S1", "S2"], "Units": [110.0, 200.0], "Totalprice": [1100.0, 2000.0]})
    prod_item = pl.DataFrame({"UPC_CODE": ["1001", "1002"], "PRODUCT_DESCRIPTION": ["A", "B"], "UNITS_SOLD": [10.0, 20.0], "TOTAL_DOLLARS": [100.0, 200.0]})
    test_item = prod_item.clone()
    return AggregatedDataset(
        level="item",
        prod_store=prod_store,
        test_store=test_store,
        prod_item=prod_item,
        test_item=test_item,
    )


def test_store_difference_rule_produces_diff():
    dataset = _two_sided_dataset()
    result = StoreDifferenceRule().evaluate(dataset)
    assert result.rule == "store_difference"
    assert result.data is not None


def test_duplicate_upc_rule_detects_dupes():
    item = pl.DataFrame({"UPC_CODE": ["1001", "1001"], "UNITS_SOLD": [1.0, 2.0]})
    dataset = AggregatedDataset(level="item", item=item)
    result = DuplicateUPCRule().evaluate(dataset)
    assert not result.passed
    assert "duplicate" in result.message


def test_missing_store_rule_detects_missing():
    store = pl.DataFrame({"STORE_NUMBER": ["S1", None, ""]})
    dataset = AggregatedDataset(level="store", store=store)
    result = MissingStoreRule().evaluate(dataset)
    assert not result.passed


def test_negative_sales_rule_error_severity():
    item = pl.DataFrame({"UPC_CODE": ["1001"], "UNITS_SOLD": [-5.0]})
    dataset = AggregatedDataset(level="item", item=item)
    rule = NegativeSalesRule()
    assert rule.severity == "error"
    result = rule.evaluate(dataset)
    assert not result.passed


def test_tolerance_rule_flags_over_threshold():
    store_diff = pl.DataFrame({"STORE_NUMBER": ["S1"], "Units_Diff_%": [50.0], "Sales_Diff_%": [0.0]})
    dataset = _two_sided_dataset()
    result = ToleranceRule(tolerance_pct=5.0).evaluate(dataset, store_difference=store_diff)
    assert not result.passed


def test_tolerance_rule_passes_within_threshold():
    store_diff = pl.DataFrame({"STORE_NUMBER": ["S1"], "Units_Diff_%": [1.0], "Sales_Diff_%": [2.0]})
    dataset = _two_sided_dataset()
    result = ToleranceRule(tolerance_pct=5.0).evaluate(dataset, store_difference=store_diff)
    assert result.passed


def test_custom_rule_uses_callable():
    def fn(dataset):
        return RuleResult(rule="custom", passed=False, message="custom failed")

    rule = CustomRule(rule_name="my_rule", fn=fn)
    assert rule.name == "my_rule"
    result = rule.evaluate(_two_sided_dataset())
    assert not result.passed


def test_rule_registry_run_enabled():
    registry = RuleRegistry()
    registry.register(StoreDifferenceRule())
    registry.register(ToleranceRule(tolerance_pct=5.0))
    dataset = _two_sided_dataset()
    results = registry.run_enabled(dataset)
    names = {r.rule for r in results}
    assert "store_difference" in names
    assert "tolerance" in names


def test_rule_registry_run_unknown_returns_none():
    registry = RuleRegistry()
    assert registry.run("does_not_exist", _two_sided_dataset()) is None


def test_rule_registry_enabled_filter():
    registry = RuleRegistry()
    registry.register(StoreDifferenceRule())
    registry.register(ToleranceRule())
    results = registry.run_enabled(_two_sided_dataset(), enabled=["store_difference"])
    assert [r.rule for r in results] == ["store_difference"]


def test_rule_registry_rejects_nameless_rule():
    class Nameless(ValidationRule):
        name = ""

        def evaluate(self, dataset, **kwargs):
            return RuleResult(rule="", passed=True)

    registry = RuleRegistry()
    with pytest.raises(ValueError):
        registry.register(Nameless())


# ── Reporting stage does not aggregate (H6 contract) ──────────────────


def test_reporting_consumes_only_validation_contract():
    """Reporting must render a ValidationDataset without touching aggregations."""
    from dav_tool.pipeline.stages.reporting import ReportingStage

    ctx = PipelineContext()
    ctx.validation = ValidationDataset(
        summaries={
            "prod_store": pl.DataFrame({"STORE_NUMBER": ["S1"], "Units": [10.0], "Totalprice": [50.0]}),
            "prod_item": pl.DataFrame({"UPC_CODE": ["1001"], "UNITS_SOLD": [10.0], "TOTAL_DOLLARS": [50.0]}),
        },
        metadata={"prod_label": "BAU", "test_label": "TEST"},
    )
    stage = ReportingStage()
    result = stage.run(ctx)
    assert result.success
    assert ctx.report is not None
    assert ctx.report.summary_kpis is not None
    assert "Store Count" in str(ctx.report.summary_kpis.columns)


def test_reporting_requires_validation_dataset():
    from dav_tool.pipeline.stages.reporting import ReportingStage

    ctx = PipelineContext()
    result = ReportingStage().run(ctx)
    assert not result.success


# ── Transformation Engine (Sprint 3) ─────────────────────────────────


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


def test_transformation_engine_requires_plan():
    from dav_tool.pipeline.transformation import TransformationEngine

    discovery = DiscoveryResult(file_paths=["a.csv"], file_type="delimited")
    with pytest.raises(ValueError):
        TransformationEngine().execute(discovery, None)


def test_transformation_engine_flattens_multiline_delimited(tmp_path):
    from dav_tool.pipeline.transformation import TransformationEngine

    path = _write(
        tmp_path,
        "wholesale.txt",
        "H|S001|2024-01-15\n"
        "D|S001|100001|Widget A|10|99.90\n"
        "D|S001|100002|Gadget B|5|49.95\n"
        "H|S002|2024-01-15\n"
        "D|S002|100001|Widget A|8|79.92\n",
    )
    discovery = DiscoveryResult(
        file_paths=[path],
        file_type="multiline",
        delimiter="|",
        ml_record_types=["D", "H"],
    )
    plan = TransformationPlan(
        flatten_operations=[
            {
                "operation": "flatten_hierarchy",
                "hierarchy": {"H": "D"},
                "parent": "H",
                "children": ["D"],
            }
        ]
    )
    transformed = TransformationEngine().execute(discovery, plan)
    assert transformed.operations == ("flatten_hierarchy",)
    assert transformed.records.height == 3, "Only detail rows survive flattening"
    assert "Column_0" in transformed.records.columns


def test_transformation_engine_header_removal_flat_delimited(tmp_path):
    from dav_tool.pipeline.transformation import TransformationEngine

    path = _write(
        tmp_path,
        "sales.csv",
        "Report generated 2024-01-15\n"
        "Store,UPC,Units,Price\n"
        "S001,100001,10,99.90\n"
        "S001,100002,5,49.95\n",
    )
    discovery = DiscoveryResult(
        file_paths=[path], file_type="delimited", delimiter=",", columns=["Store", "UPC", "Units", "Price"],
    )
    plan = TransformationPlan(header_removal=1)
    transformed = TransformationEngine().execute(discovery, plan)
    assert "header_removal" in transformed.operations
    assert transformed.records.height == 2
    assert transformed.records.columns == ["Store", "UPC", "Units", "Price"]


def test_transformation_engine_applies_product_join(tmp_path):
    from dav_tool.pipeline.transformation import TransformationEngine

    sales = _write(
        tmp_path,
        "sales.csv",
        "Store,UPC,Units\nS001,100001,10\nS001,100002,5\n",
    )
    prod = _write(
        tmp_path,
        "product.csv",
        "UPC,Brand\n100001,Alpha\n100002,Beta\n",
    )
    discovery = DiscoveryResult(
        file_paths=[sales],
        file_type="delimited",
        delimiter=",",
        product_master_path=prod,
    )
    plan = TransformationPlan(
        join_operations=[{"operation": "left_join", "source": "UPC", "target": "UPC"}]
    )
    transformed = TransformationEngine().execute(discovery, plan)
    assert transformed.records.height == 2
    assert "Brand" in transformed.records.columns
    assert transformed.join_operations == tuple(plan.join_operations)


def test_transformation_engine_missing_product_joins_gracefully(tmp_path):
    from dav_tool.pipeline.transformation import TransformationEngine

    sales = _write(
        tmp_path,
        "sales.csv",
        "Store,UPC,Units\nS001,100001,10\n",
    )
    discovery = DiscoveryResult(
        file_paths=[sales], file_type="delimited", delimiter=",",
    )
    plan = TransformationPlan(
        join_operations=[{"operation": "left_join", "source": "UPC", "target": "UPC"}]
    )
    transformed = TransformationEngine().execute(discovery, plan)
    assert transformed.records.height == 1
    assert transformed.warnings, "Expected a warning when the product master is absent"


def test_transformation_engine_stage_requires_plan():
    from dav_tool.pipeline.stages.transformation_engine import TransformationEngineStage

    ctx = PipelineContext()
    ctx.discovery = DiscoveryResult(file_paths=["a"], file_type="delimited")
    result = TransformationEngineStage().run(ctx)
    assert not result.success


def test_full_pipeline_runs_transformation_end_to_end(tmp_path):
    """Record-based (HEB) file: transform flattens before parsing."""
    from dav_tool.datasource.manager import connect_local, disconnect

    disconnect()
    path = _write(
        tmp_path,
        "heb.txt",
        "H|S001|2024-01-15\n"
        "D|S001|100001|Widget A|10|99.90\n"
        "D|S001|100002|Gadget B|5|49.95\n"
        "T|2|149.85\n",
    )
    connect_local()

    reset_bootstrap()
    reg = bootstrap().get("pipeline_registry")
    from dav_tool.workflow.discovery import detect_file

    ctx = PipelineContext()
    ctx.file_paths = [path]
    ctx.discovery = detect_file([path])
    engine = WorkflowEngine(registry=reg, context=ctx)
    run = engine.run(ctx)
    assert run.errors == ()
    assert "transformation_engine" in run.stages_completed
    assert "parser_pipeline" in run.stages_completed
    assert ctx.transformed is not None
    assert ctx.transformed.operations == ("flatten_hierarchy",)
    assert ctx.transformed.records.height == 2
    assert ctx.parsed is not None and ctx.parsed.row_count == 2
    assert ctx.canonical is not None
    assert ctx.aggregated is not None


# ── Dataset Graph enrichment ─────────────────────────────────────────


def test_dataset_graph_stage_captures_record_types_and_layout():
    from dav_tool.pipeline.stages.dataset_graph import DatasetGraphStage

    ctx = PipelineContext()
    ctx.discovery = DiscoveryResult(
        file_paths=["heb.txt"],
        file_type="multiline",
        ml_record_types=["H", "D", "T"],
        trailer_prefix="T",
        delimiter="|",
        recommended_parser="record_based",
    )
    result = DatasetGraphStage().run(ctx)
    assert result.success
    assert ctx.graph is not None
    assert ctx.graph.metadata["record_types"] == ["H", "D", "T"]
    assert ctx.graph.hierarchy == {"H": "D"}


def test_dataset_graph_stage_captures_fixed_width_layout():
    from dav_tool.pipeline.stages.dataset_graph import DatasetGraphStage

    layout = [{"field": "store", "start": 0, "end": 5, "type": "numeric"}]
    ctx = PipelineContext()
    ctx.discovery = DiscoveryResult(
        file_paths=["fw.txt"],
        file_type="fixed",
        header_prefix="H",
        fixed_width_detail_prefixes=["D"],
        detail_layout=layout,
        recommended_parser="fixed_width",
    )
    result = DatasetGraphStage().run(ctx)
    assert result.success
    assert ctx.graph.metadata["layout"]["detail"] == layout
    assert ctx.graph.metadata["record_types"] == ["H", "D"]
    assert ctx.graph.hierarchy == {"H": "D"}


def test_dataset_graph_stage_flat_delimited_has_no_record_types():
    from dav_tool.pipeline.stages.dataset_graph import DatasetGraphStage

    ctx = PipelineContext()
    ctx.discovery = DiscoveryResult(
        file_paths=["sales.csv"],
        file_type="delimited",
        delimiter=",",
        columns=["Store", "UPC", "Units", "Price"],
        recommended_parser="delimited",
    )
    result = DatasetGraphStage().run(ctx)
    assert result.success
    assert ctx.graph.metadata["record_types"] == []
    assert ctx.graph.metadata["layout"] == {}
    assert ctx.graph.hierarchy == {}

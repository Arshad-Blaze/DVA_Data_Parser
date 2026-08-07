"""Tests for PipelineCertificationRunner — the 14-stage certification."""
import os

import pytest

from dav_tool.certification.pipeline_cert import (
    PipelineCertificationRunner,
    REQUIRED_STAGES,
    SCENARIO_MANIFEST,
    SCENARIO_LABELS,
)
from dav_tool.certification.runner import CERTIFICATION_ROOT


@pytest.fixture(scope="module")
def runner():
    """A PipelineCertificationRunner bound to the real certification root."""
    assert os.path.isdir(CERTIFICATION_ROOT), (
        f"Certification root not found: {CERTIFICATION_ROOT}"
    )
    return PipelineCertificationRunner(CERTIFICATION_ROOT)


def test_required_stages_are_fourteen():
    assert len(REQUIRED_STAGES) == 14
    assert REQUIRED_STAGES == [
        "connection", "discovery", "dataset_graph", "transform_plan",
        "transformation_engine", "parser_pipeline", "canonical_mapping",
        "quantity_resolution", "canonical_dataset", "data_quality",
        "aggregation", "validation", "insights", "reporting",
    ]


def test_scenario_manifest_covers_all_datasets():
    from dav_tool.certification.runner import discover_retailer_datasets

    datasets = discover_retailer_datasets(CERTIFICATION_ROOT)
    assert datasets, "No certification datasets discovered"
    for category, retailer in datasets:
        assert (category, retailer) in SCENARIO_MANIFEST, (
            f"{category}/{retailer} missing from SCENARIO_MANIFEST"
        )


def test_scenario_labels_cover_all_manifest_scenarios():
    manifest_scenarios = {
        s for scenarios in SCENARIO_MANIFEST.values() for s in scenarios
    }
    assert manifest_scenarios <= set(SCENARIO_LABELS)


def test_all_retailers_certify(runner):
    """Every retailer must execute the identical 14-stage sequence."""
    suite = runner.run_all()
    assert suite.total > 0
    assert suite.passed == suite.total, (
        f"{suite.passed}/{suite.total} passed; failures: "
        + "; ".join(
            f"{r.category}/{r.retailer}: {r.errors}" for r in suite.results
            if not r.passed
        )
    )
    for r in suite.results:
        assert r.stages == REQUIRED_STAGES, (
            f"{r.category}/{r.retailer} executed wrong stage sequence"
        )


def test_run_one_passes_all_stages(runner):
    result = runner.run_one("delimited", "retailer_grocery")
    assert result.passed
    assert result.stages == REQUIRED_STAGES
    assert result.duration > 0
    assert result.details["mapping_confidence"] is not None
    assert result.details["aggregated_rows"] >= 0


def test_every_retailer_has_mapping_and_quality(runner):
    suite = runner.run_all()
    for r in suite.results:
        assert r.details["mapping_confidence"] is not None, (
            f"{r.category}/{r.retailer} missing canonical mapping confidence"
        )
        assert r.details["quality_checks"] > 0, (
            f"{r.category}/{r.retailer} ran no data-quality checks"
        )


def test_every_retailer_produces_insights_and_report(runner):
    suite = runner.run_all()
    for r in suite.results:
        assert r.details["insight_frames"], (
            f"{r.category}/{r.retailer} produced no insight frames"
        )
        assert r.details["artifacts"], (
            f"{r.category}/{r.retailer} produced no report artifacts"
        )


def test_heb_record_based_pipeline(runner):
    """HEB is the record-based retailer; verify via the unified pipeline."""
    result = runner.run_one("record_based", "retailer_heb")
    assert result.passed, result.errors
    assert result.scenarios == [3]


def test_missing_retailer(runner):
    result = runner.run_one("delimited", "nonexistent_retailer")
    assert not result.passed
    assert result.errors

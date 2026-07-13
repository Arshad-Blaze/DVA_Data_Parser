"""Tests for CertificationRunner and certification datasets."""
import json
import os
import tempfile

import pytest

from dav_tool.certification.runner import (
    CertificationRunner, CertificationSuiteResult,
    discover_retailer_datasets, CERTIFICATION_ROOT,
)
from dav_tool.certification.datasets import generate_all


@pytest.fixture(scope="module")
def cert_root():
    """Use the real certification root."""
    return CERTIFICATION_ROOT


def test_datasets_exist(cert_root):
    """Verify the retailer_certification directory has datasets."""
    assert os.path.isdir(cert_root), f"Certification root not found: {cert_root}"
    datasets = discover_retailer_datasets(cert_root)
    assert len(datasets) > 0, "No datasets discovered"
    categories = set(c for c, _ in datasets)
    assert "delimited" in categories
    assert "fixed_width" in categories
    assert "multiline" in categories
    assert "header_detail" in categories
    assert "unicode" in categories
    assert "malformed" in categories


def test_discover_datasets(cert_root):
    """Test dataset discovery returns expected structure."""
    datasets = discover_retailer_datasets(cert_root)
    for category, retailer in datasets:
        retailer_dir = os.path.join(cert_root, category, retailer)
        assert os.path.isdir(os.path.join(retailer_dir, "BAU")), f"BAU dir missing in {category}/{retailer}"
        assert os.path.isdir(os.path.join(retailer_dir, "TEST")), f"TEST dir missing in {category}/{retailer}"
        assert os.path.isdir(os.path.join(retailer_dir, "Config")), f"Config dir missing in {category}/{retailer}"
        assert os.path.isdir(os.path.join(retailer_dir, "Documentation")), f"Doc dir missing in {category}/{retailer}"


def test_missing_root():
    """Test runner handles missing root gracefully."""
    runner = CertificationRunner("/nonexistent/path")
    suite = runner.run_all()
    assert suite.total == 0
    assert suite.passed == 0


def test_run_all(cert_root):
    """Test running full certification suite."""
    runner = CertificationRunner(cert_root)
    suite = runner.run_all()
    assert suite.total > 0
    assert suite.passed > 0
    assert suite.passed + suite.failed == suite.total
    assert suite.duration > 0
    assert len(suite.results) == suite.total


def test_run_category(cert_root):
    """Test running a single category."""
    runner = CertificationRunner(cert_root)
    suite = runner.run_category("delimited")
    assert suite.total >= 1
    assert all(r.category == "delimited" for r in suite.results)


def test_run_one(cert_root):
    """Test running a single retailer."""
    runner = CertificationRunner(cert_root)
    result = runner.run_one("delimited", "retailer_grocery")
    assert result.passed
    assert result.discovery_ok
    assert result.config_ok
    assert result.processing_ok
    assert result.validation_ok
    assert result.duration > 0
    assert result.category == "delimited"
    assert result.retailer == "retailer_grocery"


def test_run_one_missing_retailer(cert_root):
    """Test running a non-existent retailer."""
    runner = CertificationRunner(cert_root)
    result = runner.run_one("delimited", "nonexistent_retailer")
    assert not result.passed
    assert len(result.errors) > 0


def test_report_json(cert_root):
    """Test JSON report generation."""
    runner = CertificationRunner(cert_root)
    suite = runner.run_all()
    report = runner.generate_report(suite, "json")
    data = json.loads(report)
    assert "suite" in data
    assert "results" in data
    assert data["suite"]["total"] == suite.total
    assert data["suite"]["passed"] == suite.passed
    assert len(data["results"]) == suite.total


def test_report_markdown(cert_root):
    """Test Markdown report generation."""
    runner = CertificationRunner(cert_root)
    suite = runner.run_all()
    report = runner.generate_report(suite, "markdown")
    assert "# Certification Suite Report" in report
    assert str(suite.passed) in report
    assert str(suite.total) in report


def test_report_html(cert_root):
    """Test HTML report generation."""
    runner = CertificationRunner(cert_root)
    suite = runner.run_all()
    report = runner.generate_report(suite, "html")
    assert "<table>" in report or "<h1>" in report


def test_runner_reuses_metrics(cert_root):
    """Test that runner populates metrics on results."""
    runner = CertificationRunner(cert_root)
    suite = runner.run_all()
    for r in suite.results:
        if r.passed:
            assert r.metrics is not None
            assert r.metrics.total_execution_time >= 0


def test_delimited_grocery_details(cert_root):
    """Test that the grocery retailer produces expected details."""
    runner = CertificationRunner(cert_root)
    result = runner.run_one("delimited", "retailer_grocery")
    assert result.details["bau_type"] == "delimited"
    assert result.details["test_type"] == "delimited"
    assert result.details["bau_stores"] >= 3
    assert result.details["test_stores"] >= 4


def test_suite_result_properties():
    """Test CertificationSuiteResult helper properties."""
    suite = CertificationSuiteResult()
    assert suite.summary == "0/0 passed (0.00s)"
    suite.total = 5
    suite.passed = 3
    suite.duration = 2.5
    assert "3/5" in suite.summary
    assert "2.50" in suite.summary


def test_regenerate_datasets(tmp_path):
    """Test that datasets can be regenerated."""
    root = str(tmp_path)
    generate_all(root)
    assert os.path.isdir(os.path.join(root, "delimited", "retailer_grocery", "BAU"))
    assert os.path.isdir(os.path.join(root, "fixed_width", "retailer_pharmacy_fw", "BAU"))
    assert os.path.isdir(os.path.join(root, "multiline", "retailer_wholesale", "BAU"))
    assert os.path.isdir(os.path.join(root, "header_detail", "retailer_apparel", "BAU"))
    assert os.path.isdir(os.path.join(root, "unicode", "retailer_global", "BAU"))
    assert os.path.isdir(os.path.join(root, "malformed", "retailer_legacy", "BAU"))
    datasets = discover_retailer_datasets(root)
    assert len(datasets) == 7


def test_regenerated_datasets_pass(tmp_path):
    """Test that regenerated datasets all pass certification."""
    root = str(tmp_path)
    generate_all(root)
    runner = CertificationRunner(root)
    suite = runner.run_all()
    # At minimum, all delimited datasets should pass
    delimited_results = [r for r in suite.results if r.category == "delimited"]
    assert len(delimited_results) >= 2
    assert all(r.passed for r in delimited_results)

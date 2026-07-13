"""CertificationRunner — orchestrates full pipeline against retailer datasets.

Scans retailer_certification/ for dataset categories and retailers,
runs Discovery → Configuration → Processing → Validation for each,
and compares results against expected outputs.
"""
import csv
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import polars as pl

from dav_tool.options import ParseOptions, ColumnMapping, ValidationOptions, OutputMode
from dav_tool.processing_context import ProcessingContext, ExistingContext
from dav_tool.workflow.discovery import detect_file, DiscoveryResult, flatten_multiline
from dav_tool.workflow.processing import run_store_aggregation, run_item_aggregation
from dav_tool.workflow.validation import run_existing_validation
from dav_tool._observability import ProcessingMetrics, log_phase
from dav_tool.config_builder import build_config
from dav_tool.format_config import load_format_config, apply_format_config, load_layout

logger = logging.getLogger(__name__)

CERTIFICATION_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "retailer_certification",
)


@dataclass
class CertificationResult:
    category: str = ""
    retailer: str = ""
    passed: bool = False
    duration: float = 0.0
    discovery_ok: bool = False
    config_ok: bool = False
    processing_ok: bool = False
    validation_ok: bool = False
    expected_outputs_match: bool = False
    errors: List[str] = field(default_factory=list)
    metrics: Optional[ProcessingMetrics] = None
    details: Dict = field(default_factory=dict)


@dataclass
class CertificationSuiteResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    duration: float = 0.0
    results: List[CertificationResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"{self.passed}/{self.total} passed ({self.duration:.2f}s)"


def discover_retailer_datasets(root: Optional[str] = None) -> List[Tuple[str, str]]:
    """Discover all (category, retailer_name) pairs under root."""
    root = root or CERTIFICATION_ROOT
    datasets: List[Tuple[str, str]] = []
    if not os.path.isdir(root):
        logger.warning("Certification root not found: %s", root)
        return datasets
    for entry in sorted(os.listdir(root)):
        cat_path = os.path.join(root, entry)
        if not os.path.isdir(cat_path) or entry in ("configs", "expected", "large_files"):
            continue
        for retailer in sorted(os.listdir(cat_path)):
            retailer_path = os.path.join(cat_path, retailer)
            if os.path.isdir(retailer_path):
                datasets.append((entry, retailer))
    return datasets


class CertificationRunner:
    """Runs full certification pipeline for one or more retailer datasets."""

    def __init__(self, root: Optional[str] = None):
        self.root = root or CERTIFICATION_ROOT
        self.suite_result = CertificationSuiteResult()

    def run_all(self) -> CertificationSuiteResult:
        datasets = discover_retailer_datasets(self.root)
        t0 = time.perf_counter()
        for category, retailer in datasets:
            result = self.run_one(category, retailer)
            self.suite_result.results.append(result)
            self.suite_result.total += 1
            if result.passed:
                self.suite_result.passed += 1
            else:
                self.suite_result.failed += 1
        self.suite_result.duration = time.perf_counter() - t0
        return self.suite_result

    def run_category(self, category: str) -> CertificationSuiteResult:
        datasets = [(c, r) for c, r in discover_retailer_datasets(self.root) if c == category]
        t0 = time.perf_counter()
        for cat, retailer in datasets:
            result = self.run_one(cat, retailer)
            self.suite_result.results.append(result)
            self.suite_result.total += 1
            if result.passed:
                self.suite_result.passed += 1
            else:
                self.suite_result.failed += 1
        self.suite_result.duration = time.perf_counter() - t0
        return self.suite_result

    def run_one(self, category: str, retailer: str) -> CertificationResult:
        result = CertificationResult(category=category, retailer=retailer)
        t0 = time.perf_counter()
        retailer_dir = os.path.join(self.root, category, retailer)
        bau_dir = os.path.join(retailer_dir, "BAU")
        test_dir = os.path.join(retailer_dir, "TEST")
        expected_dir = os.path.join(retailer_dir, "expected")
        config_path = os.path.join(retailer_dir, "Config", "config.json")
        layout_dir = os.path.join(retailer_dir, "Layout")

        log_phase(f"Certification: {category}/{retailer}")

        if not os.path.isdir(bau_dir):
            result.errors.append(f"BAU directory not found: {bau_dir}")
            result.duration = time.perf_counter() - t0
            return result
        if not os.path.isdir(test_dir):
            result.errors.append(f"TEST directory not found: {test_dir}")
            result.duration = time.perf_counter() - t0
            return result

        bau_files = sorted([
            os.path.join(bau_dir, f) for f in os.listdir(bau_dir)
            if os.path.isfile(os.path.join(bau_dir, f)) and not f.startswith(".")
        ])
        test_files = sorted([
            os.path.join(test_dir, f) for f in os.listdir(test_dir)
            if os.path.isfile(os.path.join(test_dir, f)) and not f.startswith(".")
        ])

        if not bau_files:
            result.errors.append("No BAU files found")
            result.duration = time.perf_counter() - t0
            return result
        if not test_files:
            result.errors.append("No TEST files found")
            result.duration = time.perf_counter() - t0
            return result

        ctx = ExistingContext()

        # ——— Load Config (if available) ———
        format_cfg = None
        if os.path.exists(config_path):
            try:
                format_cfg = load_format_config(config_path)
                result.config_ok = True
            except Exception as e:
                result.errors.append(f"Config load error: {e}")
                logger.exception("Config load failed for %s/%s", category, retailer)

        # ——— Discovery (or apply config if loaded) ———
        try:
            if format_cfg is not None:
                apply_format_config(format_cfg, ctx.prod, os.path.dirname(config_path), bau_files)
                apply_format_config(format_cfg, ctx.test, os.path.dirname(config_path), test_files)
                ctx.prod.file_paths = bau_files
                ctx.test.file_paths = test_files
                ctx.prod.config_locked = True
                ctx.test.config_locked = True
                result.discovery_ok = True
            else:
                bau_discovery = detect_file(bau_files)
                test_discovery = detect_file(test_files)
                if bau_discovery.error:
                    result.errors.append(f"BAU discovery failed: {bau_discovery.error}")
                if test_discovery.error:
                    result.errors.append(f"TEST discovery failed: {test_discovery.error}")
                if bau_discovery.error or test_discovery.error:
                    result.duration = time.perf_counter() - t0
                    return result
                bau_discovery.apply_to_context(ctx.prod)
                test_discovery.apply_to_context(ctx.test)
                ctx.prod.file_paths = bau_files
                ctx.test.file_paths = test_files
                result.discovery_ok = True
        except Exception as e:
            result.errors.append(f"Discovery error: {e}")
            logger.exception("Discovery failed for %s/%s", category, retailer)

        # ——— Configuration (only if no config was loaded) ———
        if result.discovery_ok and not ctx.prod.config_locked:
            try:
                cfg = build_config(
                    bau_files,
                    file_type=ctx.prod.file_type,
                    delimiter=ctx.prod.delimiter,
                    layout=ctx.prod.layout,
                    header_prefix=ctx.prod.header_prefix,
                    header_layout=ctx.prod.header_layout,
                    detail_layout=ctx.prod.detail_layout,
                    trailer_prefix=ctx.prod.trailer_prefix,
                    trailer_layout=ctx.prod.trailer_layout,
                    ml_record_types=ctx.prod.ml_record_types,
                    ml_delimiter=ctx.prod.ml_delimiter or "|",
                )
                if cfg and cfg.store_col:
                    ctx.prod.store_col = cfg.store_col
                    ctx.prod.upc_col = cfg.upc_col
                    ctx.prod.desc_col = cfg.desc_col
                    ctx.prod.units_col = cfg.units_col
                    ctx.prod.price_col = cfg.price_col
                    ctx.prod.price_type = cfg.price_type
                    ctx.prod.implied_dollars = cfg.implied_dollars
                    ctx.prod.implied_units = cfg.implied_units
                    ctx.prod.config_locked = True
                    ctx.test.store_col = cfg.store_col
                    ctx.test.upc_col = cfg.upc_col
                    ctx.test.desc_col = cfg.desc_col
                    ctx.test.units_col = cfg.units_col
                    ctx.test.price_col = cfg.price_col
                    ctx.test.config_locked = True
                    result.config_ok = True
                else:
                    result.errors.append("build_config returned incomplete config")
            except Exception as e:
                result.errors.append(f"Configuration error: {e}")
                logger.exception("Configuration failed for %s/%s", category, retailer)

        # ——— Processing ———
        if result.config_ok:
            try:
                prod_parse = ParseOptions.from_context(ctx.prod)
                test_parse = ParseOptions.from_context(ctx.test)
                prod_mapping = ColumnMapping.from_context(ctx.prod)
                test_mapping = ColumnMapping.from_context(ctx.test)

                prod_store_agg, _ = run_store_aggregation(bau_files, prod_parse, prod_mapping)
                test_store_agg, _ = run_store_aggregation(test_files, test_parse, test_mapping)
                prod_item_agg, _ = run_item_aggregation(bau_files, prod_parse, prod_mapping)
                test_item_agg, _ = run_item_aggregation(test_files, test_parse, test_mapping)

                ctx.prod.store_agg = prod_store_agg
                ctx.test.store_agg = test_store_agg
                ctx.prod.item_agg = prod_item_agg
                ctx.test.item_agg = test_item_agg
                result.processing_ok = True
            except Exception as e:
                result.errors.append(f"Processing error: {e}")
                logger.exception("Processing failed for %s/%s", category, retailer)

        # ——— Validation ———
        if result.processing_ok:
            try:
                prod_parse = ParseOptions.from_context(ctx.prod)
                test_parse = ParseOptions.from_context(ctx.test)
                prod_mapping = ColumnMapping.from_context(ctx.prod)
                test_mapping = ColumnMapping.from_context(ctx.test)

                val_opts = ValidationOptions(
                    run_store_validation=True,
                    run_item_validation=True,
                    run_compare_store_list=True,
                    run_summary=True,
                    run_file_review=True,
                )

                val_result = run_existing_validation(
                    bau_files, test_files,
                    prod_parse, test_parse,
                    prod_mapping, test_mapping,
                    ctx.prod.store_agg, ctx.test.store_agg,
                    ctx.prod.item_agg, ctx.test.item_agg,
                    val_opts,
                    ctx.metrics,
                )

                ctx.compare_result = val_result.store_list_result
                ctx.store_df = val_result.store_comparison
                ctx.comparison_df = val_result.item_comparison
                ctx.summary_df = val_result.item_summary
                result.validation_ok = len(val_result.errors) == 0
                for err in val_result.errors:
                    result.errors.append(f"Validation: {err}")
            except Exception as e:
                result.errors.append(f"Validation error: {e}")
                logger.exception("Validation failed for %s/%s", category, retailer)

        # ——— Compare against expected outputs ———
        if result.processing_ok and os.path.isdir(expected_dir):
            result.expected_outputs_match = _compare_expected(
                ctx, expected_dir, result.errors
            )

        passed_checks = [
            result.discovery_ok,
            result.config_ok,
            result.processing_ok,
            result.validation_ok,
        ]
        result.passed = all(passed_checks) and len(result.errors) == 0
        result.metrics = ctx.metrics
        result.duration = time.perf_counter() - t0

        result.details = {
            "bau_files": len(bau_files),
            "test_files": len(test_files),
            "bau_type": ctx.prod.file_type,
            "test_type": ctx.test.file_type,
            "bau_columns": len(ctx.prod.columns or []),
            "test_columns": len(ctx.test.columns or []),
            "bau_stores": ctx.prod.store_agg.height if ctx.prod.store_agg is not None else 0,
            "test_stores": ctx.test.store_agg.height if ctx.test.store_agg is not None else 0,
        }

        return result

    def generate_report(self, suite_result: CertificationSuiteResult, fmt: str = "json") -> str:
        if fmt == "json":
            return _report_json(suite_result)
        elif fmt == "markdown":
            return _report_markdown(suite_result)
        elif fmt == "html":
            return _report_html(suite_result)
        else:
            return _report_text(suite_result)


def _compare_expected(ctx, expected_dir: str, errors: List[str]) -> bool:
    """Compare processing results against expected CSV outputs."""
    all_match = True
    expected_files = {
        "store_agg.csv": ctx.prod.store_agg,
        "item_agg.csv": ctx.prod.item_agg,
        "test_store_agg.csv": ctx.test.store_agg,
        "test_item_agg.csv": ctx.test.item_agg,
    }
    for exp_name, result_df in expected_files.items():
        exp_path = os.path.join(expected_dir, exp_name)
        if not os.path.exists(exp_path):
            continue
        if result_df is None:
            errors.append(f"Expected {exp_name} but no result available")
            all_match = False
            continue
        try:
            expected = pl.read_csv(exp_path, truncate_ragged_lines=True)
            if expected.shape != result_df.shape:
                errors.append(f"{exp_name}: shape mismatch expected {expected.shape}, got {result_df.shape}")
                all_match = False
                continue
            for col in expected.columns:
                if col not in result_df.columns:
                    errors.append(f"{exp_name}: missing column '{col}' in result")
                    all_match = False
                    continue
                exp_col = expected[col].cast(pl.Utf8).fill_null("")
                res_col = result_df[col].cast(pl.Utf8).fill_null("")
                if not (exp_col.to_list() == res_col.to_list()):
                    errors.append(f"{exp_name}: column '{col}' values differ")
                    all_match = False
        except Exception as e:
            errors.append(f"Expected comparison failed for {exp_name}: {e}")
            all_match = False
    return all_match


def _report_json(suite: CertificationSuiteResult) -> str:
    data = {
        "suite": {
            "total": suite.total,
            "passed": suite.passed,
            "failed": suite.failed,
            "duration_seconds": round(suite.duration, 3),
        },
        "results": [],
    }
    for r in suite.results:
        data["results"].append({
            "category": r.category,
            "retailer": r.retailer,
            "passed": r.passed,
            "duration_seconds": round(r.duration, 3),
            "discovery_ok": r.discovery_ok,
            "config_ok": r.config_ok,
            "processing_ok": r.processing_ok,
            "validation_ok": r.validation_ok,
            "expected_outputs_match": r.expected_outputs_match,
            "errors": r.errors,
            "details": r.details,
        })
    return json.dumps(data, indent=2)


def _report_markdown(suite: CertificationSuiteResult) -> str:
    lines = [
        "# Certification Suite Report",
        "",
        f"**Total:** {suite.total} | **Passed:** {suite.passed} | **Failed:** {suite.failed} | **Duration:** {suite.duration:.2f}s",
        "",
        "| Category | Retailer | Status | Duration | Discovery | Config | Processing | Validation | Expected |",
        "|----------|----------|--------|----------|-----------|--------|------------|------------|----------|",
    ]
    for r in suite.results:
        status = "✓" if r.passed else "✗"
        lines.append(
            f"| {r.category} | {r.retailer} | {status} | {r.duration:.2f}s "
            f"| {'✓' if r.discovery_ok else '✗'} | {'✓' if r.config_ok else '✗'} "
            f"| {'✓' if r.processing_ok else '✗'} | {'✓' if r.validation_ok else '✗'} "
            f"| {'✓' if r.expected_outputs_match else '—'} |"
        )
    lines.append("")
    failed = [r for r in suite.results if not r.passed]
    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.category}/{r.retailer}")
            for err in r.errors:
                lines.append(f"- {err}")
            lines.append("")
    return "\n".join(lines)


def _report_html(suite: CertificationSuiteResult) -> str:
    md = _report_markdown(suite)
    try:
        import markdown
        return markdown.markdown(md, extensions=["tables"])
    except ImportError:
        return f"<pre>{md}</pre>"


def _report_text(suite: CertificationSuiteResult) -> str:
    lines = [
        f"Certification Suite: {suite.passed}/{suite.total} passed ({suite.duration:.2f}s)",
        "",
    ]
    for r in suite.results:
        lines.append(f"  {'✓' if r.passed else '✗'} {r.category}/{r.retailer} ({r.duration:.2f}s)")
        if r.errors:
            for err in r.errors:
                lines.append(f"    - {err}")
    lines.append("")
    return "\n".join(lines)

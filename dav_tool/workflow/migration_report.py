"""Migration Report Service — generates migration report data and recommendations.

Pure logic, no Streamlit, no UI.
"""
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Set

from dav_tool.workflow.schema_comparison import SchemaDiff
from dav_tool.workflow.operation_comparison import OperationComparison


@dataclass
class MigrationReport:
    prod_file_type: Optional[str] = None
    test_file_type: Optional[str] = None
    prod_delimiter: Optional[str] = None
    test_delimiter: Optional[str] = None
    prod_columns: List[str] = field(default_factory=list)
    test_columns: List[str] = field(default_factory=list)
    schema_diff: Optional[SchemaDiff] = None
    operation_compare: Optional[OperationComparison] = None
    store_missing_in_test: str = ""
    store_missing_in_prod: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rows_processed: int = 0
    total_execution_time: float = 0.0
    peak_memory: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    @property
    def schema_differences(self) -> dict:
        diff = self.schema_diff
        if diff is None:
            return {"common_columns": [], "bau_only": [], "test_only": []}
        return {
            "common_columns": sorted(diff.common),
            "bau_only": sorted(diff.only_prod),
            "test_only": sorted(diff.only_test),
        }

    def to_json(self, indent: int = 2) -> str:
        report = {
            "certification_type": "Configuration Certification",
            "bau": {
                "file_type": self.prod_file_type,
                "delimiter": self.prod_delimiter,
                "column_count": len(self.prod_columns),
                "columns": self.prod_columns,
            },
            "test": {
                "file_type": self.test_file_type,
                "delimiter": self.test_delimiter,
                "column_count": len(self.test_columns),
                "columns": self.test_columns,
            },
            "schema_differences": self.schema_differences,
            "validation": {
                "store_list_missing_in_test": self.store_missing_in_test,
                "store_list_missing_in_prod": self.store_missing_in_prod,
                "errors": self.errors,
                "warnings": self.warnings,
            },
            "metrics": {
                "rows_processed": self.rows_processed,
                "total_execution_time": self.total_execution_time,
                "peak_memory_mb": self.peak_memory,
            },
        }
        return json.dumps(report, indent=indent)


def build_recommendations(
    schema_diff: Optional[SchemaDiff] = None,
    prod_file_type: Optional[str] = None,
    test_file_type: Optional[str] = None,
    store_missing_in_test: str = "",
    store_missing_in_prod: str = "",
    errors: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> List[str]:
    """Build migration recommendations from comparison results."""
    recommendations = []

    if schema_diff:
        if schema_diff.only_test:
            recommendations.append(
                f"New columns detected in Test data: {', '.join(sorted(schema_diff.only_test))[:200]}. "
                "Verify these columns are expected in the new format."
            )
        if schema_diff.only_prod:
            recommendations.append(
                f"Columns removed in Test data: {', '.join(sorted(schema_diff.only_prod))[:200]}. "
                "Confirm these columns are no longer required."
            )

    if prod_file_type and test_file_type and prod_file_type != test_file_type:
        recommendations.append(
            f"File type mismatch ({prod_file_type} vs {test_file_type}). "
            "Ensure processing handles both formats."
        )

    if store_missing_in_test:
        recommendations.append(
            "Stores missing in Test: Review the store list to ensure coverage is complete."
        )
    if store_missing_in_prod:
        recommendations.append(
            "Stores missing in BAU: Review the store list for completeness."
        )

    if errors:
        recommendations.append(
            f"{len(errors)} errors encountered during processing. "
            "Review error log before migration."
        )
    if warnings:
        recommendations.append(
            f"{len(warnings)} warnings generated. "
            "Review warnings for potential issues."
        )

    if not recommendations:
        recommendations.append(
            "No issues detected — the Test data is certified for migration."
        )

    return recommendations


def generate_report(
    prod_file_type: Optional[str] = None,
    test_file_type: Optional[str] = None,
    prod_delimiter: Optional[str] = None,
    test_delimiter: Optional[str] = None,
    prod_columns: Optional[List[str]] = None,
    test_columns: Optional[List[str]] = None,
    store_missing_in_test: str = "",
    store_missing_in_prod: str = "",
    errors: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    rows_processed: int = 0,
    total_execution_time: float = 0.0,
    peak_memory: float = 0.0,
    operation_compare: Optional[OperationComparison] = None,
    schema_diff: Optional[SchemaDiff] = None,
) -> MigrationReport:
    """Generate a complete MigrationReport with recommendations.

    All parameters are optional — pass what you have.
    """
    prod_cols = prod_columns or []
    test_cols = test_columns or []

    recom = build_recommendations(
        schema_diff=schema_diff,
        prod_file_type=prod_file_type,
        test_file_type=test_file_type,
        store_missing_in_test=store_missing_in_test,
        store_missing_in_prod=store_missing_in_prod,
        errors=errors,
        warnings=warnings,
    )

    return MigrationReport(
        prod_file_type=prod_file_type,
        test_file_type=test_file_type,
        prod_delimiter=prod_delimiter,
        test_delimiter=test_delimiter,
        prod_columns=prod_cols,
        test_columns=test_cols,
        schema_diff=schema_diff,
        operation_compare=operation_compare,
        store_missing_in_test=store_missing_in_test,
        store_missing_in_prod=store_missing_in_prod,
        errors=errors or [],
        warnings=warnings or [],
        rows_processed=rows_processed,
        total_execution_time=total_execution_time,
        peak_memory=peak_memory,
        recommendations=recom,
    )

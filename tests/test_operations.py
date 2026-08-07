"""Unit tests for the Data Operations Framework.

Tests the Aggregate operation (the only remaining data operation) against a
canonical DataFrame, plus the shared registry and OperationResult primitives.
"""

import pytest
import polars as pl

from dav_tool.operations import (
    AggregateOperation, AggregateOptions,
    get, list_operations,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    return pl.DataFrame({
        "STORE_NUMBER": ["S001", "S001", "S002", "S002", "S003"],
        "UPC_CODE": ["A1", "A2", "A1", "A3", "A1"],
        "PRODUCT_DESCRIPTION": ["Widget", "Gadget", "Widget", "Doohickey", "Widget"],
        "Units": [10, 20, 15, 5, 8],
        "Totalprice": [100.0, 200.0, 150.0, 50.0, 80.0],
    })


# ── Registry ────────────────────────────────────────────────────────

def test_registry_has_aggregate():
    ops = list_operations()
    assert "Aggregate" in ops


def test_registry_get():
    op = get("Aggregate")
    assert op is not None
    assert op.name == "Aggregate"


def test_registry_unknown():
    assert get("Nonexistent") is None


# ── Aggregate ───────────────────────────────────────────────────────

def test_aggregate_sum_by_store(sample_df):
    op = AggregateOperation()
    opts = AggregateOptions(
        group_by=["STORE_NUMBER"],
        aggregations={"Units": "sum", "Totalprice": "sum"},
    )
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3
    assert "STORE_NUMBER" in result.df.columns
    assert "Units" in result.df.columns
    assert "Totalprice" in result.df.columns


def test_aggregate_count(sample_df):
    op = AggregateOperation()
    opts = AggregateOptions(
        group_by=["STORE_NUMBER"],
        aggregations={"UPC_CODE": "count"},
    )
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3


def test_aggregate_multiple_group_by(sample_df):
    op = AggregateOperation()
    opts = AggregateOptions(
        group_by=["STORE_NUMBER", "UPC_CODE"],
        aggregations={"Units": "sum"},
    )
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 5  # all rows unique on (STORE_NUMBER, UPC_CODE)


def test_aggregate_no_group_by(sample_df):
    op = AggregateOperation()
    opts = AggregateOptions(group_by=[], aggregations={"Units": "sum"})
    result = op.execute(sample_df, opts)
    assert result.errors


def test_aggregate_missing_column(sample_df):
    op = AggregateOperation()
    opts = AggregateOptions(group_by=["NONEXISTENT"], aggregations={"Units": "sum"})
    result = op.execute(sample_df, opts)
    assert result.errors


def test_aggregate_all_functions(sample_df):
    op = AggregateOperation()
    for func in ["sum", "count", "avg", "min", "max", "first", "last"]:
        opts = AggregateOptions(
            group_by=["STORE_NUMBER"],
            aggregations={"Units": func},
        )
        result = op.execute(sample_df, opts)
        assert not result.errors, f"Function {func} failed: {result.errors}"


# ── OperationResult ─────────────────────────────────────────────────

def test_result_from_df():
    from dav_tool.operations.base import OperationResult
    df = pl.DataFrame({"a": [1, 2]})
    result = OperationResult.from_df(df, "test", 0.1)
    assert result.row_count == 2
    assert result.column_count == 1
    assert result.operation == "test"
    assert result.elapsed_seconds == 0.1


def test_result_error():
    from dav_tool.operations.base import OperationResult
    result = OperationResult.error("test", "something went wrong")
    assert result.errors == ["something went wrong"]
    assert result.row_count == 0


# ── Edge Cases ──────────────────────────────────────────────────────

def test_aggregate_empty_df():
    df = pl.DataFrame({"A": [], "B": []}).cast({"A": pl.Utf8, "B": pl.Float64})
    op = AggregateOperation()
    opts = AggregateOptions(group_by=["A"], aggregations={"B": "sum"})
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 0


def test_aggregate_single_row():
    df = pl.DataFrame({"STORE_NUMBER": ["S001"], "Units": [10], "Totalprice": [100.0]})
    op = AggregateOperation()
    opts = AggregateOptions(group_by=["STORE_NUMBER"], aggregations={"Units": "sum"})
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 1
    assert result.df["Units"][0] == 10


def test_aggregate_with_nulls():
    df = pl.DataFrame({
        "GROUP": ["A", "A", "B"],
        "VALUE": [1.0, None, 3.0],
    })
    op = AggregateOperation()
    opts = AggregateOptions(group_by=["GROUP"], aggregations={"VALUE": "sum"})
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 2
    a_val = result.df.filter(pl.col("GROUP") == "A")["VALUE"][0]
    assert a_val == 1.0  # null treated as 0 in sum


# ── Integration: Validation Consuming Operations ───────────────────

def test_validation_uses_aggregate_operation():
    from dav_tool.validation.store import storelevelvalidation_from_df
    prod = pl.DataFrame({
        "STORE_NUMBER": ["S001", "S001", "S002"],
        "Units": [10.0, 20.0, 15.0],
        "Totalprice": [100.0, 200.0, 150.0],
    })
    test = pl.DataFrame({
        "STORE_NUMBER": ["S001", "S002", "S002"],
        "Units": [12.0, 18.0, 5.0],
        "Totalprice": [120.0, 180.0, 50.0],
    })
    result = storelevelvalidation_from_df(prod, test)
    assert not result.is_empty()
    assert "STORE_NUMBER" in result.columns
    assert "Units_Diff" in result.columns


def test_item_summary_uses_aggregate_operation():
    from dav_tool.calculations.core import item_comparison, item_summary
    bau = pl.DataFrame({
        "UPC_CODE": ["A1", "A2"],
        "PRODUCT_DESCRIPTION": ["Widget", "Gadget"],
        "UNITS_SOLD": [100.0, 200.0],
        "TOTAL_DOLLARS": [1000.0, 2000.0],
    })
    test = pl.DataFrame({
        "UPC_CODE": ["A1", "A3"],
        "PRODUCT_DESCRIPTION": ["Widget", "Thingamajig"],
        "UNITS_SOLD": [110.0, 50.0],
        "TOTAL_DOLLARS": [1100.0, 500.0],
    })
    comparison = item_comparison(bau, test)
    summary = item_summary(comparison)
    assert "Present In" in summary.columns
    assert "Units Difference" in summary.columns
    assert summary.height == 3  # Both, BAU only, Test only


# ── Large Dataset ───────────────────────────────────────────────────

def test_aggregate_large_dataset():
    n = 100_000
    df = pl.DataFrame({
        "STORE": [f"S{i % 100:03d}" for i in range(n)],
        "Units": [float(i) for i in range(n)],
        "Price": [float(i * 10) for i in range(n)],
    })
    op = AggregateOperation()
    opts = AggregateOptions(group_by=["STORE"], aggregations={"Units": "sum", "Price": "sum"})
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 100

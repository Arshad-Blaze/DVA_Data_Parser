"""Unit tests for the Data Operations Framework.

Tests every operation independently against a canonical DataFrame.
"""

import os
import pytest
import polars as pl

from dav_tool.operations import (
    AggregateOperation, AggregateOptions,
    FilterOperation, FilterOptions, FilterCondition,
    SortOperation, SortOptions, SortColumn,
    SampleOperation, SampleOptions,
    StatisticsOperation, StatisticsOptions,
    ExportOperation, ExportOptions,
    PreviewOperation, PreviewOptions,
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

def test_registry_has_all_operations():
    ops = list_operations()
    assert "Aggregate" in ops
    assert "Filter" in ops
    assert "Sort" in ops
    assert "Sample" in ops
    assert "Statistics" in ops
    assert "Export" in ops
    assert "Preview" in ops


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


# ── Filter ──────────────────────────────────────────────────────────

def test_filter_eq(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="STORE_NUMBER", operator="eq", value="S001")])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 2


def test_filter_gt(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="Units", operator="gt", value=10)])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 2  # 15, 20


def test_filter_contains(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="PRODUCT_DESCRIPTION", operator="contains", value="get")])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 4  # Widget, Gadget, Widget, Widget all contain "get"


def test_filter_in_list(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="STORE_NUMBER", operator="in_list", value=["S001", "S003"])])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3


def test_filter_null_not_null(sample_df):
    df_with_null = sample_df.with_columns(pl.lit(None).alias("NULL_COL"))
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="NULL_COL", operator="null")])
    result = op.execute(df_with_null, opts)
    assert not result.errors
    assert result.row_count == 5


def test_filter_or_mode(sample_df):
    op = FilterOperation()
    opts = FilterOptions(
        conditions=[
            FilterCondition(column="STORE_NUMBER", operator="eq", value="S001"),
            FilterCondition(column="STORE_NUMBER", operator="eq", value="S002"),
        ],
        mode="or",
    )
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 4


def test_filter_no_conditions(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[])
    result = op.execute(sample_df, opts)
    assert result.errors


def test_filter_startswith_endswith(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="UPC_CODE", operator="startswith", value="A")])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 5


def test_filter_lte(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="Units", operator="lte", value=10)])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3  # 5, 8, 10


# ── Sort ────────────────────────────────────────────────────────────

def test_sort_ascending(sample_df):
    op = SortOperation()
    opts = SortOptions(columns=[SortColumn(column="Units", ascending=True)])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.df["Units"][0] == 5
    assert result.df["Units"][-1] == 20


def test_sort_descending(sample_df):
    op = SortOperation()
    opts = SortOptions(columns=[SortColumn(column="Units", ascending=False)])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.df["Units"][0] == 20
    assert result.df["Units"][-1] == 5


def test_sort_multiple_columns(sample_df):
    op = SortOperation()
    opts = SortOptions(columns=[
        SortColumn(column="STORE_NUMBER", ascending=True),
        SortColumn(column="Units", ascending=False),
    ])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 5


def test_sort_no_columns(sample_df):
    op = SortOperation()
    opts = SortOptions(columns=[])
    result = op.execute(sample_df, opts)
    assert result.errors


def test_sort_missing_column(sample_df):
    op = SortOperation()
    opts = SortOptions(columns=[SortColumn(column="NONEXISTENT")])
    result = op.execute(sample_df, opts)
    assert result.errors


# ── Sample ──────────────────────────────────────────────────────────

def test_sample_head(sample_df):
    op = SampleOperation()
    opts = SampleOptions(mode="head", n=3)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3


def test_sample_tail(sample_df):
    op = SampleOperation()
    opts = SampleOptions(mode="tail", n=2)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 2


def test_sample_random(sample_df):
    op = SampleOperation()
    opts = SampleOptions(mode="random", n=3, seed=42)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3


def test_sample_percentage(sample_df):
    op = SampleOperation()
    opts = SampleOptions(mode="percentage", pct=0.4)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 2  # 40% of 5 = 2


def test_sample_invalid_mode(sample_df):
    op = SampleOperation()
    opts = SampleOptions(mode="invalid", n=3)
    result = op.execute(sample_df, opts)
    assert result.errors


# ── Statistics ──────────────────────────────────────────────────────

def test_statistics_all_columns(sample_df):
    op = StatisticsOperation()
    opts = StatisticsOptions()
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 5  # one row per column
    assert "column" in result.df.columns
    assert "null_count" in result.df.columns
    assert "unique_count" in result.df.columns
    assert result.metadata["row_count"] == 5
    assert result.metadata["column_count"] == 5


def test_statistics_specific_columns(sample_df):
    op = StatisticsOperation()
    opts = StatisticsOptions(columns=["Units", "Totalprice"])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 2


def test_statistics_with_nulls(sample_df):
    df = sample_df.with_columns(pl.lit(None).alias("NULL_COL"))
    op = StatisticsOperation()
    opts = StatisticsOptions(columns=["NULL_COL"])
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 1


def test_statistics_missing_column(sample_df):
    op = StatisticsOperation()
    opts = StatisticsOptions(columns=["NONEXISTENT"])
    result = op.execute(sample_df, opts)
    assert result.errors


def test_statistics_memory(sample_df):
    op = StatisticsOperation()
    opts = StatisticsOptions(include_memory=True)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert "memory_bytes" in result.metadata
    assert "memory_mb" in result.metadata


# ── Export ──────────────────────────────────────────────────────────

def test_export_csv(sample_df, tmp_path):
    op = ExportOperation()
    path = str(tmp_path / "test.csv")
    opts = ExportOptions(path=path, format="csv")
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert os.path.exists(path)
    loaded = pl.read_csv(path)
    assert loaded.height == 5


def test_export_parquet(sample_df, tmp_path):
    op = ExportOperation()
    path = str(tmp_path / "test.parquet")
    opts = ExportOptions(path=path, format="parquet")
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert os.path.exists(path)
    loaded = pl.read_parquet(path)
    assert loaded.height == 5


def test_export_invalid_format(sample_df, tmp_path):
    op = ExportOperation()
    opts = ExportOptions(path=str(tmp_path / "test.xyz"), format="xyz")
    result = op.execute(sample_df, opts)
    assert result.errors


def test_export_no_path(sample_df):
    op = ExportOperation()
    opts = ExportOptions(path="", format="csv")
    result = op.execute(sample_df, opts)
    assert result.errors


# ── Preview ─────────────────────────────────────────────────────────

def test_preview_head(sample_df):
    op = PreviewOperation()
    opts = PreviewOptions(mode="head", n_rows=3)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3
    assert result.metadata["total_rows"] == 5
    assert result.metadata["preview_rows"] == 3


def test_preview_tail(sample_df):
    op = PreviewOperation()
    opts = PreviewOptions(mode="tail", n_rows=2)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 2


def test_preview_select_columns(sample_df):
    op = PreviewOperation()
    opts = PreviewOptions(n_rows=3, columns=["STORE_NUMBER", "Units"])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.df.columns == ["STORE_NUMBER", "Units"]


def test_preview_random(sample_df):
    op = PreviewOperation()
    opts = PreviewOptions(mode="random", n_rows=3, seed=42)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 3


def test_preview_missing_column(sample_df):
    op = PreviewOperation()
    opts = PreviewOptions(columns=["NONEXISTENT"])
    result = op.execute(sample_df, opts)
    assert result.errors


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


def test_filter_empty_df():
    df = pl.DataFrame({"A": [], "B": []}).cast({"A": pl.Utf8, "B": pl.Float64})
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="A", operator="eq", value="x")])
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 0


def test_sort_empty_df():
    df = pl.DataFrame({"A": [], "B": []}).cast({"A": pl.Utf8, "B": pl.Float64})
    op = SortOperation()
    opts = SortOptions(columns=[SortColumn(column="A")])
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 0


def test_sample_head_larger_than_df(sample_df):
    op = SampleOperation()
    opts = SampleOptions(mode="head", n=100)
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 5


def test_statistics_empty_df():
    df = pl.DataFrame({"A": [], "B": []}).cast({"A": pl.Utf8, "B": pl.Float64})
    op = StatisticsOperation()
    opts = StatisticsOptions()
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 2


def test_preview_empty_df():
    df = pl.DataFrame({"A": [], "B": []}).cast({"A": pl.Utf8, "B": pl.Float64})
    op = PreviewOperation()
    opts = PreviewOptions(n_rows=5)
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


def test_filter_all_rows_match(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="Units", operator="gt", value=0)])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 5


def test_filter_no_rows_match(sample_df):
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="Units", operator="gt", value=1000)])
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 0


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


def test_export_returns_empty_df(sample_df, tmp_path):
    op = ExportOperation()
    path = str(tmp_path / "test.csv")
    opts = ExportOptions(path=path, format="csv")
    result = op.execute(sample_df, opts)
    assert not result.errors
    assert result.row_count == 0
    assert os.path.exists(path)


# ── Integration: Operation Chaining ─────────────────────────────────

def test_filter_then_sort(sample_df):
    fop = FilterOperation()
    fopts = FilterOptions(conditions=[FilterCondition(column="STORE_NUMBER", operator="eq", value="S001")])
    filtered = fop.execute(sample_df, fopts)
    assert filtered.row_count == 2

    sop = SortOperation()
    sopts = SortOptions(columns=[SortColumn(column="Units", ascending=False)])
    sorted_result = sop.execute(filtered.df, sopts)
    assert not sorted_result.errors
    assert sorted_result.df["Units"][0] == 20
    assert sorted_result.df["Units"][1] == 10


def test_aggregate_then_filter():
    df = pl.DataFrame({
        "STORE": ["A", "A", "B", "B", "C"],
        "Units": [10, 20, 30, 40, 50],
    })
    agg = AggregateOperation()
    agg_result = agg.execute(df, AggregateOptions(
        group_by=["STORE"], aggregations={"Units": "sum"}
    ))
    assert agg_result.row_count == 3

    filt = FilterOperation()
    filt_result = filt.execute(agg_result.df, FilterOptions(
        conditions=[FilterCondition(column="Units", operator="gt", value=30)]
    ))
    assert not filt_result.errors
    assert filt_result.row_count == 2  # B=70, C=50


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


def test_filter_large_dataset():
    n = 100_000
    df = pl.DataFrame({
        "ID": list(range(n)),
        "VALUE": [float(i) for i in range(n)],
    })
    op = FilterOperation()
    opts = FilterOptions(conditions=[FilterCondition(column="VALUE", operator="gt", value=50_000)])
    result = op.execute(df, opts)
    assert not result.errors
    assert result.row_count == 49_999

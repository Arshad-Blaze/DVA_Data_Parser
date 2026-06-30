import polars as pl
from dav_tool.validation.store import compare_files, storelevelvalidation_from_df


def test_compare_files_perfect_match():
    df1 = pl.DataFrame({"store": ["A", "B", "C"]})
    df2 = pl.DataFrame({"store": ["A", "B", "C"]})
    result = compare_files(df1, df2, "store", "store")
    assert result["missing_in_test"] == ""
    assert result["missing_in_prod"] == ""


def test_compare_files_missing_in_test():
    df1 = pl.DataFrame({"store": ["A", "B", "C"]})
    df2 = pl.DataFrame({"store": ["A", "B"]})
    result = compare_files(df1, df2, "store", "store")
    assert "c" in result["missing_in_test"].lower()
    assert result["missing_in_prod"] == ""


def test_compare_files_missing_in_prod():
    df1 = pl.DataFrame({"store": ["A"]})
    df2 = pl.DataFrame({"store": ["A", "B"]})
    result = compare_files(df1, df2, "store", "store")
    assert result["missing_in_test"] == ""
    assert "b" in result["missing_in_prod"].lower()


def test_compare_files_normalization():
    df1 = pl.DataFrame({"store": [" Store1 "]})
    df2 = pl.DataFrame({"store": ["store1"]})
    result = compare_files(df1, df2, "store", "store")
    assert result["missing_in_test"] == ""
    assert result["missing_in_prod"] == ""


def test_store_validation_basic():
    prod = pl.DataFrame({"store": ["A"], "units": [10], "price": [100]})
    test = pl.DataFrame({"store": ["A"], "units": [10], "price": [100]})
    result = storelevelvalidation_from_df(
        prod, test,
        "store", "units", "price",
        "store", "units", "price",
        "Total Price", "Total Price",
        False, False, False, False
    )
    assert not result.is_empty()


def test_store_validation_units_mismatch():
    prod = pl.DataFrame({"store": ["A"], "units": [10], "price": [100]})
    test = pl.DataFrame({"store": ["A"], "units": [5], "price": [100]})
    result = storelevelvalidation_from_df(
        prod, test,
        "store", "units", "price",
        "store", "units", "price",
        "Total Price", "Total Price",
        False, False, False, False
    )
    assert not result.is_empty()


def test_store_validation_price_mismatch():
    prod = pl.DataFrame({"store": ["A"], "units": [10], "price": [100]})
    test = pl.DataFrame({"store": ["A"], "units": [10], "price": [200]})
    result = storelevelvalidation_from_df(
        prod, test,
        "store", "units", "price",
        "store", "units", "price",
        "Total Price", "Total Price",
        False, False, False, False
    )
    assert not result.is_empty()

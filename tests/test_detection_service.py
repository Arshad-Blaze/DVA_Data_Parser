from dav_tool.detection import (
    detect_file_type,
    is_multiline_record,
    has_header
)


def test_detect_csv_comma(tmp_path):
    file = tmp_path / "test.csv"
    file.write_text("a,b,c\n1,2,3\n")
    result = detect_file_type(str(file))
    assert result == ("delimited", ",")


def test_detect_pipe(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("a|b|c\n1|2|3\n")
    result = detect_file_type(str(file))
    assert result == ("delimited", "|")


def test_detect_tab(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("a\tb\tc\n1\t2\t3\n")
    result = detect_file_type(str(file))
    assert result == ("delimited", "\t")


def test_detect_fixed_width(tmp_path):
    file = tmp_path / "fixed.txt"
    file.write_text("ABCDEF123\nGHIJKL456\n")
    result = detect_file_type(str(file))
    assert result == ("fixed", None)


def test_detect_excel():
    result = detect_file_type("test.xlsx")
    assert result == ("excel", None)


def test_multiline_true(tmp_path):
    file = tmp_path / "multi.txt"
    file.write_text("line1\\\nline2\\\nline3\\\nline4\\\nline5\\\n")
    assert is_multiline_record(str(file)) is True


def test_multiline_false(tmp_path):
    file = tmp_path / "normal.txt"
    file.write_text("line1\nline2\nline3\n")
    assert is_multiline_record(str(file)) is False


def test_has_header_true(tmp_path):
    file = tmp_path / "header.csv"
    file.write_text("store,units,price\n1,10,100\n")
    assert has_header(str(file), ",") is True


def test_has_header_false(tmp_path):
    file = tmp_path / "noheader.csv"
    file.write_text("123,456,789\n1,10,100\n")
    assert has_header(str(file), ",") is False

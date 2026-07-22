from dav_tool.detection import (
    detect_file_type,
    is_multiline_record,
    has_header,
    detect_disclaimer_lines,
    detect_encoding,
    detect_start_line,
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


def test_detect_encoding_utf8(tmp_path):
    file = tmp_path / "utf8.csv"
    file.write_bytes("store,units\nS1,10\n".encode("utf-8"))
    assert detect_encoding(str(file)) in ("utf-8", "cp1252")


def test_detect_encoding_cp1252(tmp_path):
    file = tmp_path / "cp1252.csv"
    file.write_bytes("café,100\n".encode("cp1252"))
    enc = detect_encoding(str(file))
    assert enc == "cp1252" or enc == "utf8-lossy"


def test_detect_disclaimer_lines_none(tmp_path):
    file = tmp_path / "clean.csv"
    file.write_text("store,units,price\nS1,10,100\nS2,20,200\n")
    lines = detect_disclaimer_lines(str(file), file_type="delimited", delimiter=",")
    assert lines == []


def test_detect_disclaimer_lines_blank_lines(tmp_path):
    file = tmp_path / "blanks.csv"
    file.write_text("\n\nstore,units\nS1,10\n")
    lines = detect_disclaimer_lines(str(file), file_type="delimited", delimiter=",")
    assert len(lines) >= 2


def test_detect_disclaimer_lines_legal_text(tmp_path):
    file = tmp_path / "legal.csv"
    file.write_text("CONFIDENTIAL\nAll rights reserved\nstore,units\nS1,10\n")
    lines = detect_disclaimer_lines(str(file), file_type="delimited", delimiter=",")
    assert len(lines) >= 2


def test_detect_start_line_with_disclaimers(tmp_path):
    file = tmp_path / "with_disclaimers.csv"
    file.write_text("DISCLAIMER\nLEGAL TEXT\nstore,units\nS1,10\n")
    start = detect_start_line(str(file), file_type="delimited", delimiter=",")
    assert start >= 2


def test_detect_start_line_no_disclaimers(tmp_path):
    file = tmp_path / "no_disclaimers.csv"
    file.write_text("store,units,price\nS1,10,100\nS2,20,200\n")
    start = detect_start_line(str(file), file_type="delimited", delimiter=",")
    assert start == 0

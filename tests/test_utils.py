from datetime import datetime

from src.utils import (
    clean_abstract,
    clean_text,
    clean_unused,
    get_time_range,
    read_data,
    remove_duplicates,
    remove_newlines_in_brackets,
    strip_latex_command,
)


def test_get_time_range():
    start, end = get_time_range(1)
    now = datetime.now()
    assert end.startswith(now.isoformat()[:10])  # Check if end is the current date in ISO format
    assert int(start[:4]) == now.year - 1  # Check if start date is 1 year back


def test_read_data(tmp_path):
    # Create a temporary file with JSON data
    test_file = tmp_path / "test.json"
    test_file.write_text('{"key": "value"}\n{"key2": "value2"}\n')

    result = read_data(str(test_file))
    assert len(result) == 2  # Ensure both lines were read
    assert result[0] == {"key": "value"}
    assert result[1] == {"key2": "value2"}


def test_read_data_empty_file(tmp_path):
    test_file = tmp_path / "empty.json"
    test_file.touch()  # Create an empty file

    result = read_data(str(test_file))
    assert result == []  # Ensure empty file returns an empty list


def test_read_data_invalid_json(tmp_path):
    test_file = tmp_path / "invalid.json"
    test_file.write_text('{"key": "value"\n')  # Invalid JSON format

    result = read_data(str(test_file))
    assert result == []  # Ensure invalid JSON returns an empty list


def test_clean_unused():
    text = "Hello, World! This is a test."
    result = clean_unused(text)
    assert result == "Hello World This is a test"  # Check if punctuation is removed


def test_remove_duplicates():
    data = [
        {"timestamp": "2022-01-01T12:00:00", "data": "A"},
        {"timestamp": "2022-01-01T12:00:00", "data": "A"},  # Duplicate
        {"timestamp": "2022-01-02T12:00:00", "data": "B"},
    ]
    result = remove_duplicates(data)
    assert len(result) == 2  # One duplicate should be removed
    assert result[0]["data"] == "A"
    assert result[1]["data"] == "B"


def test_clean_text():
    text = "This is a test.\n See also \n Sources\n thumb| right|200px|"
    result = clean_text(text, "wikipedia")
    assert "\n See also" not in result  # Check if 'See also' section is removed
    assert "thumb|" not in result  # Check if 'thumb|' is removed
    assert "right|" not in result  # Check if 'right|' is removed


def test_clean_abstract():
    text = "This is MATH a $test$ with https : //example.com"
    result = clean_abstract(text)
    assert "MATH" not in result  # Check if 'MATH' is removed
    assert "$" not in result  # Check if dollar signs are removed
    assert "URL" in result  # Check if URL placeholder is inserted


def test_remove_newlines_in_brackets():
    text = "This is a {test\nwith newlines} inside brackets."
    result = remove_newlines_in_brackets(text)
    assert "\n" not in result  # Ensure no newlines inside the brackets
    assert result == "This is a {testwith newlines} inside brackets."


def test_strip_latex_command():
    text = r"\textbf{bold} normal \DIFdel{deleted} \DIFadd{added}"
    result = strip_latex_command(text)
    assert "bold" in result  # Check if content inside commands remains
    assert "\\DIFdel" in result  # Commands like \DIFdel should not be removed
    assert "\\DIFadd" in result

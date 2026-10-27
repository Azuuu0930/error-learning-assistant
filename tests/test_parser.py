import pytest

from src.parser import parse_python_traceback


@pytest.mark.parametrize("name,message", [
    ("NameError", "name 'user_name' is not defined"),
    ("SyntaxError", "expected ':'"),
    ("IndentationError", "expected an indented block"),
    ("TypeError", "unsupported operand type(s) for +: 'int' and 'str'"),
    ("ValueError", "invalid literal for int() with base 10: 'abc'"),
    ("IndexError", "list index out of range"),
    ("KeyError", "'age'"),
    ("AttributeError", "'str' object has no attribute 'append'"),
    ("ModuleNotFoundError", "No module named 'missing_package'"),
    ("ImportError", "cannot import name 'missing' from 'math'"),
    ("FileNotFoundError", "[Errno 2] No such file or directory: 'data.txt'"),
    ("ZeroDivisionError", "division by zero"),
])
def test_extract_type_line_and_message(name, message):
    log = f'Traceback (most recent call last):\n  File "main.py", line 8, in <module>\n    failing_operation()\n{name}: {message}'
    error = parse_python_traceback(log)
    assert error.error_type == name
    assert error.file == "main.py"
    assert error.line == 8
    assert error.message == message
    assert error.status == "complete"


def test_syntax_error_without_traceback_header():
    error = parse_python_traceback('  File "lesson.py", line 3\n    if True\n           ^\nSyntaxError: expected \':\'')
    assert (error.file, error.line, error.error_type) == ("lesson.py", 3, "SyntaxError")
    assert error.frames[0].source == "if True"


def test_last_frame_is_failure_location():
    log = 'Traceback (most recent call last):\n  File "main.py", line 10, in <module>\n    call()\n  File "helper.py", line 2, in call\n    return items[99]\nIndexError: list index out of range'
    error = parse_python_traceback(log)
    assert len(error.frames) == 2
    assert (error.file, error.line) == ("helper.py", 2)


def test_chained_exception_does_not_reuse_old_frame():
    log = 'Traceback (most recent call last):\n  File "old.py", line 4\nKeyError: \'x\'\n\nDuring handling of the above exception, another exception occurred:\n\nTraceback (most recent call last):\n  File "new.py", line 9\nValueError: invalid input'
    error = parse_python_traceback(log)
    assert (error.error_type, error.file, error.line) == ("ValueError", "new.py", 9)
    assert len(error.frames) == 1 and error.warnings
    without_final_frame = parse_python_traceback(log.replace('  File "new.py", line 9\n', ""))
    assert without_final_frame.line is None
    assert without_final_frame.file is None


@pytest.mark.parametrize("log", ["", "   ", "not a traceback", "Traceback (most recent call last):", '  File "a.py", line 2', "NameError", "NameError:", "File: broken", "INFO: starting", "x: 5", "x = {'a': 1}"])
def test_incomplete_or_invalid_log_never_crashes(log):
    error = parse_python_traceback(log)
    assert error.status in {"partial", "unrecognized"}
    assert error.warnings


@pytest.mark.parametrize("name", ["RuntimeError", "CustomFailure", "my_app.CustomError"])
def test_unknown_exception_keeps_type_and_message(name):
    error = parse_python_traceback(f'{name}: unexpected problem')
    assert error.error_type == name
    assert error.message == "unexpected problem"


@pytest.mark.parametrize("message,name,target", [
    ("name 'user_name' is not defined", "NameError", "user_name"),
    ('name "user_name" is not defined', "NameError", "user_name"),
    ("'age'", "KeyError", "age"),
    ("42", "KeyError", "42"),
    ("No module named 'example.submodule'", "ModuleNotFoundError", "example.submodule"),
    ("cannot import name 'missing' from 'math'", "ImportError", "missing"),
    ("'str' object has no attribute 'append'", "AttributeError", "append"),
    ("[Errno 2] No such file or directory: 'data.txt'", "FileNotFoundError", "data.txt"),
])
def test_target_extraction(message, name, target):
    assert parse_python_traceback(f"{name}: {message}").target == target


def test_windows_path_crlf_and_ansi_colors():
    log = '\x1b[31mTraceback (most recent call last):\x1b[0m\r\n  File "C:\\class\\main.py", line 7, in <module>\r\nNameError: name \'x\' is not defined\r\n'
    error = parse_python_traceback(log)
    assert (error.file, error.line) == (r"C:\class\main.py", 7)
    assert error.message == "name 'x' is not defined"


def test_indented_source_is_not_an_exception():
    log = '  File "main.py", line 5\n    ValueError: this_is_source\nNameError: name \'x\' is not defined'
    assert parse_python_traceback(log).error_type == "NameError"


def test_multiline_message_is_preserved():
    error = parse_python_traceback("RuntimeError: first line\nsecond line\n")
    assert error.message == "first line\nsecond line"


def test_invalid_line_numbers_are_not_used():
    for number in ("0", "9" * 5000):
        error = parse_python_traceback(f'  File "a.py", line {number}\nNameError: unknown name')
        assert error.line is None

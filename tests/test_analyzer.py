import pytest

from src.analyzer import analyze_error
from src.explanations import CATEGORIES
from src.models import Explanation
from src.view import render_code_context


@pytest.mark.parametrize("name,category", CATEGORIES.items())
def test_supported_explanations_and_categories(name, category):
    result = analyze_error(f"{name}: example")
    assert result.error.category == category
    assert result.explanation.summary and result.explanation.cause
    assert len(result.explanation.checkpoints) >= 3
    assert len(result.hints) == 3
    assert result.explanation.fix_example
    compile(result.explanation.fix_example, "<fix-example>", "exec")


def test_name_error_explanation_uses_target():
    result = analyze_error("NameError: name 'user_name' is not defined")
    assert "user_name" in result.explanation.summary
    assert "user_name" in result.hints[1]
    assert 'user_name = "Taro"' in result.explanation.fix_example
    assert "line" in result.hints[0]


def test_context_shows_two_lines_around_error_and_marks_only_error():
    code = "\n".join(f"value_{i} = {i}" for i in range(1, 11))
    result = analyze_error('  File "main.py", line 8\nNameError: missing', code)
    assert [line.number for line in result.code_context] == [6, 7, 8, 9, 10]
    assert [line.number for line in result.code_context if line.is_error] == [8]
    assert result.code_context[2].text == "value_8 = 8"


@pytest.mark.parametrize("line", [1, 3])
def test_context_at_file_boundaries(line):
    result = analyze_error(f'  File "main.py", line {line}\nNameError: missing', "a\nb\nc")
    assert len(result.code_context) == 3
    assert sum(item.is_error for item in result.code_context) == 1


def test_out_of_range_and_missing_line_are_explained():
    assert analyze_error('  File "a.py", line 100\nTypeError: example', "x = 1").notes
    assert analyze_error("TypeError: example", "x = 1").notes
    assert not analyze_error("TypeError: example").code_context


@pytest.mark.parametrize("log", ["", "not a traceback", "CustomFailure: reason"])
def test_fallback_does_not_invent_a_fix(log):
    result = analyze_error(log)
    assert result.error.category == "unknown"
    assert result.explanation.fix_example is None
    assert result.explanation.checkpoints


def test_protocol_boundary_accepts_another_explanation_provider():
    class CustomProvider:
        def explain(self, error):
            return Explanation("独自の説明", error.message, ("確認する",), "読み方")
    result = analyze_error("RuntimeError: reason", provider=CustomProvider())
    assert result.explanation.summary == "独自の説明"
    assert result.hints[2] == "確認する"


@pytest.mark.parametrize("message,expected", [
    ("'int' object is not callable", "count = 3"),
    ("greet() missing 1 required positional argument: 'name'", "def greet(name)"),
    ("'int' object is not subscriptable", "names ="),
])
def test_type_error_explanation_matches_message(message, expected):
    assert expected in analyze_error(f"TypeError: {message}").explanation.fix_example


def test_code_context_escapes_html():
    result = analyze_error('  File "main.py", line 1\nNameError: missing', '<script>alert("x")</script>')
    html = render_code_context(result.code_context)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "▶" in html


def test_context_html_keeps_lines_outside_markdown_code_block():
    result = analyze_error('  File "main.py", line 2\nNameError: missing', 'x = 1\nprint(user_name)\ny = 3')
    html = render_code_context(result.code_context)
    assert "print(user_name)" in html
    assert "background:#FFF0C2" in html
    assert "<pre" not in html and "<code" not in html


def test_name_error_target_cannot_inject_code_into_example():
    result = analyze_error("NameError: name 'x; dangerous()' is not defined")
    assert "dangerous()" not in result.explanation.fix_example
    compile(result.explanation.fix_example, "<example>", "exec")


def test_log_and_source_are_never_executed(tmp_path):
    sentinel = tmp_path / "executed.txt"
    source = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')"
    analyze_error("NameError: name 'x' is not defined", source)
    assert not sentinel.exists()

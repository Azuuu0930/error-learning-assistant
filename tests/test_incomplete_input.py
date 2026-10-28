"""短い対話環境のログでも、入力し直さずに構文の手がかりを得られる。"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.analyzer import analyze_error


APP = Path(__file__).resolve().parents[1] / "app.py"
LOG = "IncompleteInputError: incomplete input"
CODE = 'age = 20\nif age >= 18\n    print("成人です")'


@pytest.mark.parametrize("name", ["IncompleteInputError", "console.IncompleteInputError"])
def test_incomplete_input_has_an_explanation_without_code(name):
    result = analyze_error(f"{name}: incomplete input")
    assert result.error.error_type == name
    assert result.error.category == "syntax"
    assert "未完成" in result.explanation.summary
    assert result.explanation.fix_example is not None
    assert result.code_analysis is None


@pytest.mark.parametrize("code,word,line", [
    (CODE, "コロン", 2),
    ('values = [1, 2', "括弧", 1),
    ('a = np.array([1, 5, 10, 3, 4, 25, 30]', "括弧", 1),
    ('title = "hello', "文字列", 1),
    ('if True:\nprint("hello")', "字下げ", 2),
])
def test_incomplete_log_uses_actual_code_syntax_for_explanation_and_hints(code, word, line):
    result = analyze_error(LOG, code)
    issue = result.code_analysis.syntax_error
    assert issue.line == line
    assert word in issue.explanation.summary + issue.explanation.cause
    assert word in result.explanation.summary + result.explanation.cause
    assert f"{line}行目" in result.hints[0]
    assert word not in result.hints[0]
    assert word in result.hints[2]
    # 入力コードの構文診断を、元ログのファイルや行番号として捏造しない。
    assert result.error.error_type == "IncompleteInputError"
    assert result.error.message == "incomplete input"
    assert result.error.file is None and result.error.line is None


def test_valid_code_does_not_get_a_syntax_diagnosis_from_incomplete_log():
    result = analyze_error(LOG, 'print("hello")')
    assert result.code_analysis.syntax_error is None
    assert not result.code_analysis.findings
    assert "コロン" not in result.explanation.cause


def test_code_syntax_diagnostic_does_not_replace_a_different_logged_exception():
    result = analyze_error('  File "other.py", line 9\nNameError: missing', CODE)
    assert result.error.error_type == "NameError"
    assert result.error.file == "other.py" and result.error.line == 9
    assert result.code_analysis.syntax_error.line == 2
    assert "コロン" not in result.explanation.cause


def test_notebook_line_and_pasted_fragment_line_are_kept_separate():
    code = 'a = np.array([1, 5, 10, 3, 4, 25, 30]'
    result = analyze_error('  File "/tmp/ipykernel_533/193525177.py", line 2\n'
                           f'    {code}\nIncompleteInputError: incomplete input', code)
    assert result.error.line == 2
    assert result.code_analysis.syntax_error.line == 1
    assert "括弧" in result.explanation.cause
    assert "1行目" in result.hints[0]
    assert not result.code_context
    assert not any("全体を貼り付けてください" in note for note in result.notes)


def test_sidebar_selection_loads_both_inputs_without_an_extra_button_click():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.selectbox(key="source_language").select("C++").run()
    app.selectbox(key="sample_choice").select("文の最後のコロンが抜けている").run()
    assert app.text_area(key="error_log").value.endswith("SyntaxError: expected ':'")
    assert "if age >= 18" in app.text_area(key="source_code").value
    assert app.selectbox(key="source_language").value == "Python"
    assert not app.exception


def test_incomplete_log_displays_actionable_code_location_without_reentering_log():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.text_area(key="error_log").input(LOG)
    app.text_area(key="source_code").input(CODE)
    app.button(key="analyze").click().run()
    assert not app.exception
    assert not any("エラー種類を特定できませんでした" in item.value for item in app.subheader)
    assert any("2行目" in item.value for item in app.info)
    assert not any("エラー履歴全体を貼り付けてください" in item.value for item in app.caption)
    app.button(key="next_hint").click().run()
    assert any("2行目" in item.value for item in app.text)
    app.text_area(key="source_code").input('print("hello")').run()
    assert "analysis" not in app.session_state
    app.button(key="analyze").click().run()
    assert app.session_state["analysis"].code_analysis.syntax_error is None
    assert not any("2行目" in item.value for item in app.info)


def test_unknown_named_exception_is_reported_as_unsupported_instead_of_unidentified():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.text_area(key="error_log").input("MyCustomError: detail")
    app.button(key="analyze").click().run()
    assert any("専用の説明がないエラー" in item.value for item in app.subheader)
    assert not app.exception

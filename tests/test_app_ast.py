"""ASTの情報がヒントの前に答えとして漏れず、通常モードでは読めること。"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"
LOG = '  File "main.py", line 2\nNameError: name \'user_name\' is not defined'
CODE = "username = input()\nprint(user_name)"


@pytest.fixture
def app():
    return AppTest.from_file(str(APP), default_timeout=20).run()


def analyze(app, code=CODE, log=LOG):
    app.text_area(key="error_log").input(log)
    app.text_area(key="source_code").input(code)
    app.button(key="analyze").click().run()
    assert not app.exception


def visible_text(app):
    return "\n".join(item.value for item in app.text)


def test_normal_mode_shows_context_section_and_confidence(app):
    analyze(app)
    app.radio(key="display_mode").set_value("通常モード").run()
    assert any(item.value == "コードから分かったこと" for item in app.subheader)
    assert "タイプミスの可能性" in visible_text(app)
    assert "信頼度：中" in visible_text(app)
    assert "username" in visible_text(app)


def test_hint_mode_keeps_detailed_findings_hidden_until_third_hint(app):
    analyze(app)
    assert "username" not in visible_text(app)
    for _ in range(2):
        app.button(key="next_hint").click().run()
        assert "タイプミスの可能性" not in visible_text(app)
        assert "username" not in visible_text(app)
    app.button(key="next_hint").click().run()
    assert "username" in visible_text(app)
    assert "タイプミスの可能性" in visible_text(app)
    assert not app.session_state["show_fix"]
    assert not app.exception


def test_switching_to_hint_mode_hides_ast_details_again(app):
    analyze(app)
    app.radio(key="display_mode").set_value("通常モード").run()
    assert "username" in visible_text(app)
    app.radio(key="display_mode").set_value("ヒントモード").run()
    assert "username" not in visible_text(app)
    assert app.session_state["hint_step"] == 0


def test_log_only_has_no_ast_section(app):
    analyze(app, code="")
    assert app.session_state["analysis"].code_analysis is None
    assert not any(item.value == "コードから分かったこと" for item in app.subheader)


def test_ast_syntax_failure_keeps_existing_ui_and_hints(app):
    analyze(app, code="if True\n    pass", log="SyntaxError: expected ':'")
    assert app.session_state["analysis"].code_analysis.status == "unavailable"
    assert any("ASTを生成" in item.value for item in app.info)
    app.button(key="next_hint").click().run()
    assert app.session_state["hint_step"] == 1
    assert not app.exception


def test_editing_code_removes_old_ast_analysis(app):
    analyze(app)
    app.text_area(key="source_code").input("user_name = 'Taro'\nprint(user_name)").run()
    assert "analysis" not in app.session_state
    assert app.session_state["hint_step"] == 0
    app.button(key="analyze").click().run()
    assert not app.session_state["analysis"].code_analysis.findings
    assert not app.exception

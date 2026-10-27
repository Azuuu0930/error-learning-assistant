from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"
SAMPLES = json.loads((APP.parent / "examples" / "sample_errors.json").read_text(encoding="utf-8"))


@pytest.fixture
def app():
    instance = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not instance.exception
    return instance


def analyze(app, log="NameError: name 'user_name' is not defined"):
    app.text_area(key="error_log").input(log)
    app.button(key="analyze").click().run()
    assert not app.exception
    return app


def has_fix(app):
    return any('user_name = "Taro"' in block.value for block in app.code)


def test_hints_require_three_steps_then_explicit_reveal(app):
    analyze(app)
    assert app.session_state["hint_step"] == 0
    assert not has_fix(app)
    assert not any("見つけられませんでした" in text.value for text in app.text)
    for step in range(1, 4):
        app.button(key="next_hint").click().run()
        assert app.session_state["hint_step"] == step
        assert not has_fix(app)
    app.button(key="reveal_fix").click().run()
    assert has_fix(app)
    assert not app.exception


def test_normal_mode_and_mode_switch_reset_hints(app):
    analyze(app)
    app.radio(key="display_mode").set_value("通常モード").run()
    assert has_fix(app)
    assert any("user_name" in text.value and "見つけられませんでした" in text.value for text in app.text)
    app.radio(key="display_mode").set_value("ヒントモード").run()
    assert not has_fix(app)
    assert app.session_state["hint_step"] == 0


def test_editing_input_removes_stale_result(app):
    analyze(app)
    app.button(key="next_hint").click().run()
    app.text_area(key="error_log").input("IndexError: list index out of range").run()
    assert "analysis" not in app.session_state
    assert app.session_state["hint_step"] == 0
    app.button(key="analyze").click().run()
    assert app.session_state["analysis"].error.error_type == "IndexError"


def test_source_edit_invalidates_result(app):
    analyze(app)
    app.text_area(key="source_code").input("print(user_name)").run()
    assert "analysis" not in app.session_state


def test_empty_input_has_validation_message(app):
    app.button(key="analyze").click().run()
    assert app.warning
    assert "analysis" not in app.session_state
    assert not app.exception


@pytest.mark.parametrize("log", ["broken log", "MyCustomFailure: reason", '  File "a.py", line 2'])
def test_incomplete_and_unknown_logs_are_rendered_safely(app, log):
    analyze(app, log)
    assert app.session_state["analysis"].error.category == "unknown"


def test_input_size_is_bounded(app):
    analyze(app, "x" * 100_001)
    assert "analysis" not in app.session_state
    assert any("長すぎます" in warning.value for warning in app.warning)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["id"])
def test_sample_can_be_loaded_and_analyzed_from_sidebar(app, sample):
    analyze(app)
    app.button(key="next_hint").click().run()
    app.selectbox(key="sample_choice").select(sample["title"]).run()
    app.button(key="load_sample").click().run()
    assert app.text_area(key="error_log").value == sample["error_log"]
    assert app.text_area(key="source_code").value == sample["code"]
    assert "analysis" not in app.session_state
    assert app.session_state["hint_step"] == 0
    app.button(key="analyze").click().run()
    assert app.session_state["analysis"].error.error_type == sample["error_type"]
    assert not app.exception

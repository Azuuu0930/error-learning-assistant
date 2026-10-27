"""Search, state transitions, and failure recovery in the learning workspace."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.analyzer import analyze_error


APP = Path(__file__).resolve().parents[1] / "app.py"


def test_catalog_provides_searchable_japanese_examples_for_all_supported_errors():
    from src.error_catalog import ERROR_CATALOG

    expected = {
        "SyntaxError", "IndentationError", "NameError", "TypeError", "ValueError",
        "IndexError", "KeyError", "AttributeError", "ModuleNotFoundError", "ImportError",
        "FileNotFoundError", "ZeroDivisionError", "UnboundLocalError", "RecursionError",
        "StopIteration", "AssertionError", "RuntimeError", "UnicodeDecodeError",
    }
    assert {entry.error_type for entry in ERROR_CATALOG} == expected
    for entry in ERROR_CATALOG:
        assert entry.error_type in entry.search_label
        assert any(ord(char) > 127 for char in entry.search_label)
        assert entry.code.strip()
        result = analyze_error(entry.error_log, entry.code)
        assert result.error.error_type == entry.error_type
        assert result.error.category != "unknown"


def test_autocomplete_selection_populates_input_and_resets_previous_learning():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.text_area(key="error_log").input("NameError: name 'x' is not defined")
    app.button(key="analyze").click().run()
    for _ in range(3):
        app.button(key="next_hint").click().run()
    app.button(key="reveal_fix").click().run()
    assert app.session_state["show_fix"] is True
    app.selectbox(key="error_search").select("StopIteration").run()
    assert not app.exception
    assert "StopIteration" in app.text_area(key="error_log").value
    assert "next(" in app.text_area(key="source_code").value
    assert "analysis" not in app.session_state
    assert app.session_state["hint_step"] == 0
    assert app.session_state["show_fix"] is False
    app.button(key="analyze").click().run()
    assert app.session_state["analysis"].error.error_type == "StopIteration"


def test_animation_preference_persists_without_resetting_learning_progress():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.text_area(key="error_log").input("NameError: name 'x' is not defined")
    app.button(key="analyze").click().run()
    app.button(key="next_hint").click().run()
    app.toggle(key="reduce_motion").set_value(True).run()
    assert app.session_state["hint_step"] == 1
    assert app.session_state["analysis"].error.error_type == "NameError"
    app.button(key="next_hint").click().run()
    assert app.toggle(key="reduce_motion").value is True
    assert app.session_state["hint_step"] == 2


def test_failed_analysis_clears_loading_hides_exception_and_allows_retry(monkeypatch):
    import src.analyzer

    real_analyzer = src.analyzer.analyze_error

    def failing_analysis(log, source):
        raise RuntimeError("secret-local-path-and-sensitive-token")

    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.text_area(key="error_log").input("NameError: name 'x' is not defined")
    app.button(key="analyze").click().run()
    app.button(key="next_hint").click().run()
    monkeypatch.setattr(src.analyzer, "analyze_error", failing_analysis)
    app.button(key="analyze").click().run()
    assert not app.exception
    assert app.error
    assert "analysis" not in app.session_state
    assert app.session_state["hint_step"] == 0
    rendered = "\n".join(item.value for item in app.markdown)
    assert 'data-loading="true"' not in rendered
    assert "secret-local-path" not in rendered
    assert all("secret-local-path" not in error.value for error in app.error)
    monkeypatch.setattr(src.analyzer, "analyze_error", real_analyzer)
    app.button(key="analyze").click().run()
    assert not app.exception
    assert not app.error
    assert app.session_state["analysis"].error.error_type == "NameError"
    assert 'data-loading="true"' not in "\n".join(item.value for item in app.markdown)

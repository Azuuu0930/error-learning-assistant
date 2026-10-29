"""UI history tests use a fake DB, never a real visitor's log."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from src import history_ui
from src.error_history import HistoryConfig, HistoryStore

APP = Path(__file__).resolve().parents[1] / "app.py"

def setup(monkeypatch, *, fail=False):
    calls = []
    def transport(*args):
        calls.append(args)
        if fail:
            raise TimeoutError("PRIVATE_DB_KEY")
    store = HistoryStore(HistoryConfig.from_mapping({
        "enabled":True, "url":"https://abcdefghijklmnopqrst.supabase.co",
        "secret_key":"sb_secret_"+"a"*32}), transport=transport)
    monkeypatch.setattr(history_ui, "get_history_connection",
                        lambda: history_ui.HistoryConnection(store, "ready"))
    return AppTest.from_file(str(APP), default_timeout=20).run(), calls

def submit(app, log="NameError: name 'item' is not defined", code=""):
    app.text_area(key="error_log").input(log)
    app.text_area(key="source_code").input(code)
    return app.button(key="analyze").click().run()

def test_save_notice_precedes_input_and_nothing_saves_on_initial_render(monkeypatch):
    app, calls = setup(monkeypatch)
    assert not calls
    assert any("Supabase" in x.value and "保存" in x.value for x in app.info)
    assert not app.exception

def test_pending_is_written_before_analysis_and_source_is_not_sent(monkeypatch):
    from src import analyzer
    original = analyzer.analyze_error
    app, calls = setup(monkeypatch)
    def checked(*args, **kwargs):
        assert len(calls) == 1
        assert calls[0][0].endswith("/archive_error")
        return original(*args, **kwargs)
    monkeypatch.setattr(analyzer, "analyze_error", checked)
    submit(app, code="PRIVATE_SOURCE = 'do not save'")
    assert not app.exception
    assert len(calls) == 2 and calls[1][2]["p_status"] == "recognized"
    assert "PRIVATE_SOURCE" not in repr(calls)

@pytest.mark.parametrize("log",["unrecognized output","PrivateCustomError: help"])
def test_unknown_logs_are_saved_without_asserting_an_answer(monkeypatch, log):
    app, calls = setup(monkeypatch)
    submit(app, log)
    assert len(calls) == 2
    assert calls[0][2]["p_log"] == log
    assert calls[1][2]["p_status"] == "unrecognized"
    assert not app.exception

def test_analysis_exception_is_still_recorded(monkeypatch):
    from src import analyzer
    def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE_INTERNAL")
    monkeypatch.setattr(analyzer, "analyze_error", broken)
    app, calls = setup(monkeypatch)
    submit(app)
    assert calls[-1][2]["p_status"] == "failed"
    assert not app.exception
    assert "PRIVATE_INTERNAL" not in repr([x.value for x in app.error])

def test_rejected_input_is_saved_with_explicit_truncation(monkeypatch):
    app, calls = setup(monkeypatch)
    submit(app, "a"*100001)
    assert len(calls) == 2
    assert calls[0][2]["p_truncated"] is True
    assert calls[1][2]["p_status"] == "rejected"
    assert app.warning and not app.exception

def test_blank_input_is_not_saved(monkeypatch):
    app, calls = setup(monkeypatch)
    submit(app, " ")
    assert not calls

def test_no_duplicate_saves_on_rerenders_hints_or_role_switch(monkeypatch):
    app, calls = setup(monkeypatch)
    submit(app)
    app.run()
    app.button(key="next_hint").click().run()
    app.radio(key="workspace_role").set_value("先生").run()
    app.radio(key="workspace_role").set_value("学生").run()
    assert len(calls) == 2
    assert not app.exception
    submit(app)
    assert len(calls) == 4
    assert calls[0][2]["p_id"] != calls[2][2]["p_id"]

def test_failed_save_does_not_block_analysis_or_disclose_secret(monkeypatch):
    app, calls = setup(monkeypatch, fail=True)
    submit(app)
    assert app.session_state["analysis"].error.error_type == "NameError"
    assert len(calls) == 1
    assert any("保存できませんでした" in x.value for x in app.warning)
    assert "PRIVATE_DB_KEY" not in repr([x.value for x in app.warning])
    assert not app.exception

@pytest.mark.parametrize("state",["disabled","misconfigured"])
def test_unavailable_storage_never_claims_saved(monkeypatch, state):
    monkeypatch.setattr(history_ui, "get_history_connection", lambda: history_ui.HistoryConnection(None,state))
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    submit(app)
    assert not app.exception
    assert any("保存していません" in x.value for x in [*app.info,*app.warning])
    assert not any("記録しました" in x.value for x in app.caption)

"""AppTest uses a fake transport only: no real credentials or paid requests."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def app_with_service(monkeypatch, *, fail=False):
    from src import coach_ui
    from src.coach_provider import CoachConfig, CoachService
    calls = []
    def transport(body, _key):
        calls.append(body)
        if fail:
            raise TimeoutError("private-key-provider-error")
        candidate = json.loads(body["input"])["candidates"][0]
        return {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": json.dumps({"question_id": candidate["id"], "basis_ids": [candidate["basis_id"]]})}]}]}
    service = CoachService(CoachConfig(True, "fake-key", "trial-code-for-tests-only"), transport=transport)
    monkeypatch.setattr(coach_ui, "get_coach_service", lambda: service)
    return AppTest.from_file(str(APP), default_timeout=20).run(), calls


def analyze(app, *, reveal=True):
    app.text_area(key="error_log").input("NameError: name 'missing' is not defined")
    app.text_area(key="source_code").input("created = 1\nprint(missing)")
    app.button(key="analyze").click().run()
    if reveal:
        for _ in range(3):
            app.button(key="next_hint").click().run()
    return app


def approve(app):
    app.text_input(key="coach_access").input("trial-code-for-tests-only")
    app.checkbox(key="coach_consent").check().run()


def test_panel_does_not_leak_questions_before_existing_hint_gate(monkeypatch):
    app, calls = app_with_service(monkeypatch)
    analyze(app, reveal=False)
    assert not app.exception
    assert not any(b.key == "coach_standard" for b in app.button)
    assert "coach_consent" not in app.session_state
    assert calls == []


def test_preview_and_standard_guide_do_not_send_and_explicit_ai_action_sends_once(monkeypatch):
    app, calls = app_with_service(monkeypatch)
    analyze(app)
    assert app.button(key="coach_request").disabled
    assert calls == []
    assert any('"store":false' in item.value.replace(" ", "") for item in app.json)
    app.button(key="coach_standard").click().run()
    assert app.session_state["coach_outcome"].status == "standard"
    assert calls == []
    approve(app)
    assert calls == []
    app.button(key="coach_request").click().run()
    assert not app.exception
    assert app.session_state["coach_outcome"].status == "ai"
    assert len(calls) == 1
    app.toggle(key="reduce_motion").set_value(True).run()
    app.run()
    assert len(calls) == 1


def test_provider_failure_retains_original_results_and_shows_safe_standard_question(monkeypatch):
    app, calls = app_with_service(monkeypatch, fail=True)
    analyze(app)
    approve(app)
    app.button(key="coach_request").click().run()
    assert not app.exception
    assert app.session_state["analysis"].error.error_type == "NameError"
    assert app.session_state["coach_outcome"].status == "unavailable"
    assert app.session_state["hint_step"] == 3
    assert app.session_state["show_fix"] is False
    rendered = " ".join(x.value for x in app.text)
    assert "private-key" not in rendered
    assert len(calls) == 1


def test_code_edits_with_identical_anonymous_context_still_clear_consent_and_results(monkeypatch):
    app, calls = app_with_service(monkeypatch)
    analyze(app)
    approve(app)
    app.button(key="coach_request").click().run()
    session_id = app.session_state["coach_session_id"]
    app.text_area(key="source_code").input("created = 2\nprint(missing)").run()
    assert "coach_outcome" not in app.session_state
    assert "coach_consent" not in app.session_state
    assert "coach_access" not in app.session_state
    assert app.session_state["coach_session_id"] == session_id
    assert len(calls) == 1


def test_goal_and_mode_changes_clear_consent_without_sending(monkeypatch):
    app, calls = app_with_service(monkeypatch)
    analyze(app)
    approve(app)
    app.button(key="coach_standard").click().run()
    app.selectbox(key="coach_goal").select("locate").run()
    assert app.checkbox(key="coach_consent").value is False
    assert "coach_outcome" not in app.session_state
    approve(app)
    app.radio(key="display_mode").set_value("通常モード").run()
    assert app.checkbox(key="coach_consent").value is False
    assert app.session_state["hint_step"] == 0
    assert calls == []


def test_catalog_and_reanalysis_invalidate_ai_consent(monkeypatch):
    app, calls = app_with_service(monkeypatch)
    analyze(app)
    approve(app)
    app.selectbox(key="error_search").select("TypeError").run()
    assert "coach_consent" not in app.session_state
    analyze(app)
    approve(app)
    app.button(key="analyze").click().run()
    assert "coach_consent" not in app.session_state
    assert calls == []


def test_disabled_ai_keeps_standard_guide_usable(monkeypatch):
    from src import coach_ui
    from src.coach_provider import CoachConfig, CoachService
    monkeypatch.setattr(coach_ui, "get_coach_service", lambda: CoachService(CoachConfig()))
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    analyze(app)
    assert not any(b.key == "coach_request" for b in app.button)
    app.button(key="coach_standard").click().run()
    assert not app.exception
    assert app.session_state["coach_outcome"].status == "standard"

import json
from threading import Event, Thread

import pytest

from src.analyzer import analyze_error


def setup_service(transport=None, **limits):
    from src.coach_provider import CoachConfig, CoachService
    return CoachService(CoachConfig(True, "fake-key-never-use", "trial-code-for-tests-only"),
                        transport=transport or good_transport, **limits)


def context():
    from src.learning_coach import build_context
    return build_context(analyze_error("NameError: x", "print(missing)"), "check")


def good_transport(body, key):
    payload = json.loads(body["input"])
    candidate = payload["candidates"][0]
    answer = json.dumps({"question_id": candidate["id"], "basis_ids": [candidate["basis_id"]]})
    return {"status": "completed", "output": [{"type": "message", "role": "assistant",
        "content": [{"type": "output_text", "text": answer}]}]}


def test_requires_consent_and_trial_code_before_transport():
    calls = []
    service = setup_service(lambda *args: calls.append(args))
    assert service.choose(context(), consent=False, access_code="trial-code-for-tests-only", session_id="a").status == "consent_required"
    assert service.choose(context(), consent=True, access_code="wrong", session_id="a").status == "access_required"
    assert calls == []


def test_disabled_configuration_never_contacts_provider():
    from src.coach_provider import CoachConfig, CoachService
    service = CoachService(CoachConfig(), transport=lambda *_: pytest.fail("must not call"))
    outcome = service.choose(context(), consent=True, access_code="", session_id="a")
    assert outcome.status == "disabled" and outcome.question.text
    assert "fake-key" not in repr(service.config)


def test_success_uses_fixed_endpoint_request_schema_and_nonstored_bounded_output():
    from src.coach_provider import ENDPOINT, build_request
    body = build_request(context())
    assert ENDPOINT == "https://api.openai.com/v1/responses"
    assert body["store"] is False
    assert body["max_output_tokens"] == 256
    assert body["reasoning"] == {"effort": "none"}
    assert body["text"]["format"]["strict"] is True
    assert "tools" not in body
    outcome = setup_service().choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id="a")
    assert outcome.status == "ai" and outcome.question.text


@pytest.mark.parametrize("reply", [None, {}, {"status": "incomplete", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "secret"}]}]},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "not json"}]}]},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "x" * 70_000}]}]},
    {"status": "completed", "output": [{"type": "tool_call", "name": "execute"}]}])
def test_bad_provider_replies_fall_back_without_returning_model_text(reply):
    outcome = setup_service(lambda *_: reply).choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id="a")
    assert outcome.status == "unavailable"
    assert "secret" not in repr(outcome)
    assert outcome.question.text


@pytest.mark.parametrize("error", [TimeoutError("secret"), OSError("secret-path"), ValueError("private")])
def test_transport_errors_are_sanitized_and_not_retried(error):
    calls = []
    def transport(*_):
        calls.append(1)
        raise error
    outcome = setup_service(transport).choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id="a")
    assert outcome.status == "unavailable" and len(calls) == 1
    assert "secret" not in repr(outcome)


def test_failed_calls_count_against_session_and_global_limits():
    service = setup_service(lambda *_: {}, session_limit=1, total_limit=2)
    def call(session):
        return service.choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id=session).status
    assert call("a") == "unavailable"
    assert call("a") == "limited"
    assert call("b") == "unavailable"
    assert call("c") == "limited"


def test_global_limits_reset_after_window_and_busy_requests_do_not_enter_transport():
    entered, release = Event(), Event()
    now = [0.0]
    def transport(*args):
        entered.set()
        assert release.wait(3)
        return good_transport(*args)
    service = setup_service(transport, clock=lambda: now[0], session_limit=1, total_limit=1)
    results = []
    def call():
        results.append(service.choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id="a"))
    worker = Thread(target=call)
    worker.start()
    try:
        assert entered.wait(3)
        assert service.choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id="b").status == "limited"
    finally:
        release.set()
        worker.join(3)
    assert results[0].status == "ai"
    now[0] = 86_401
    assert service.choose(context(), consent=True, access_code="trial-code-for-tests-only", session_id="a").status == "ai"


@pytest.mark.parametrize("values", [{}, {"AI_TUTOR_ENABLED": "true"},
    {"AI_TUTOR_ENABLED": "false", "OPENAI_API_KEY": "key", "AI_TUTOR_ACCESS_CODE": "long-enough-trial-code"},
    {"AI_TUTOR_ENABLED": "true", "OPENAI_API_KEY": "key", "AI_TUTOR_ACCESS_CODE": "short"}])
def test_incomplete_operator_config_remains_disabled(values):
    from src.coach_provider import CoachConfig
    assert not CoachConfig.from_mapping(values).ready


def test_operator_config_is_explicit_and_repr_does_not_disclose_secrets():
    from src.coach_provider import CoachConfig
    cfg = CoachConfig.from_mapping({"AI_TUTOR_ENABLED": "true", "OPENAI_API_KEY": "private-secret-key",
                                   "AI_TUTOR_ACCESS_CODE": "private-access-code-123"})
    assert cfg.ready
    assert "private" not in repr(cfg)


def test_transport_refuses_redirects_and_oversized_http_reply(monkeypatch):
    from src import coach_provider as provider
    from urllib.error import HTTPError
    with pytest.raises(HTTPError):
        provider.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example/")
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, size): return b"x" * size
    class Opener:
        def open(self, request, timeout):
            assert timeout == 10
            assert request.full_url == provider.ENDPOINT
            return Reply()
    monkeypatch.setattr(provider.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(ValueError):
        provider.http_transport(provider.build_request(context()), "fake-key")

"""No real credentials or network: exercise the private archive boundary."""
import json
from uuid import UUID
import pytest
from src.error_history import HistoryConfig, HistoryStore, redact_log

URL = "https://abcdefghijklmnopqrst.supabase.co"
KEY = "sb_secret_" + "a" * 32

def config(**values):
    return HistoryConfig.from_mapping({"enabled": True, "url": URL, "secret_key": KEY, **values})

@pytest.mark.parametrize("raw,secret", [
    ('File "C:\\Users\\Alice\\work\\main.py", line 2', "Alice"),
    ('File "/home/bob/project/main.py", line 2', "bob"),
    ('open /tmp/private/data.csv failed', "private"),
    ('contact: student@example.edu', "student@example.edu"),
    ('API_KEY=abc123-private-value', "abc123-private-value"),
    ('password: "secret with spaces"', "secret with spaces"),
    ('Authorization: Bearer hidden-token', "hidden-token"),
    ('https://user:password@example.com/api?token=secret#private', "password"),
    ('https://example.com/path?key=private', "private"),
    ('sk-proj-' + 'a'*40, 'a'*40),
    ('ghp_' + 'b'*36, 'b'*36),
    ('-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----', 'SECRET'),
    ('File "/Users/Alice Smith/project/main.py", line 2', 'Smith'),
    ('File "/home/学生 一郎/演習/main.py", line 2', '一郎'),
    ('File "/home/O\'Brien/project/main.py", line 2', "Brien"),
])
def test_redacts_common_identifiers_and_credentials(raw, secret):
    text, count = redact_log(raw)
    assert secret not in text
    assert count >= 1

def test_redaction_preserves_useful_error_structure():
    raw = "NameError: name 'result' is not defined\nmain.c:8: error: expected ';'"
    assert redact_log(raw) == (raw, 0)

@pytest.mark.parametrize("url", [
    "http://abcdefghijklmnopqrst.supabase.co", URL+"/evil", URL+"?secret=x",
    "https://user:pass@abcdefghijklmnopqrst.supabase.co", URL+".evil.com",
    "https://localhost", URL+":444", URL+"#x",
])
def test_refuses_untrusted_destinations(url):
    with pytest.raises(ValueError):
        config(url=url)

def test_disabled_and_invalid_secrets():
    assert HistoryConfig.from_mapping({}) is None
    assert HistoryConfig.from_mapping({"enabled":False}) is None
    for key in ("", "public-anon-key", KEY+"\n"):
        with pytest.raises(ValueError):
            config(secret_key=key)
    assert KEY not in repr(config())

def test_pending_is_saved_before_diagnosis_without_source_or_identity():
    calls = []
    store = HistoryStore(config(), transport=lambda *args: calls.append(args))
    ident = store.begin('File "/home/alice/main.py"\nUnknownProblem: private@example.com', "python")
    assert UUID(ident).version == 4
    endpoint, headers, payload, timeout = calls[0]
    assert endpoint == URL + "/rest/v1/rpc/archive_error"
    assert headers["apikey"] == KEY
    assert timeout == 3
    assert set(payload) == {"p_id","p_language","p_log","p_redactions","p_truncated"}
    assert "alice" not in json.dumps(payload)
    assert "private@example.com" not in json.dumps(payload)
    assert payload["p_language"] == "python"

def test_updates_only_allowlisted_diagnosis_metadata():
    calls = []
    store = HistoryStore(config(), transport=lambda *args: calls.append(args))
    ident = store.begin("PrivateCustomError: secret", "cpp")
    assert store.finish(ident, "unrecognized", "PrivateCustomError", "unknown")
    body = calls[-1][2]
    assert body == {"p_id":ident, "p_status":"unrecognized","p_error_type":"unknown","p_category":"unknown"}
    assert "PrivateCustomError" not in json.dumps(body)

@pytest.mark.parametrize("state",["recognized","unrecognized","failed","rejected"])
def test_all_outcomes_can_be_recorded(state):
    calls = []
    store = HistoryStore(config(), transport=lambda *args: calls.append(args))
    ident = store.begin("anything", "c")
    assert store.finish(ident, state, None, "unknown")
    assert calls[-1][2]["p_status"] == state

def test_caps_log_and_marks_truncation():
    calls = []
    store = HistoryStore(config(), transport=lambda *args: calls.append(args))
    assert store.begin("a"*100001, "python")
    assert len(calls[0][2]["p_log"]) == 100000
    assert calls[0][2]["p_truncated"] is True

def test_redaction_expansion_is_bounded_and_marked():
    calls = []
    store = HistoryStore(config(), transport=lambda *args: calls.append(args))
    assert store.begin("error at /a\n"*8000, "python")
    assert len(calls[0][2]["p_log"]) <= 100000
    assert calls[0][2]["p_truncated"] is True

def test_invalid_inputs_never_contact_database():
    calls = []
    store = HistoryStore(config(), transport=lambda *args: calls.append(args))
    assert store.begin(" ", "python") is None
    assert store.begin("x", "javascript") is None
    assert not store.finish("not-a-uuid","failed", None, "unknown")
    assert not store.finish(None,"failed", None, "unknown")
    assert not store.finish("949d26c4-928a-443e-8961-05c742eec810","arbitrary", None, "unknown")
    assert not calls

def test_transport_failure_does_not_leak_or_raise(capsys):
    def broken(*args):
        raise TimeoutError("SECRET-KEY raw-log")
    store = HistoryStore(config(), transport=broken)
    assert store.begin("anything", "python") is None
    assert not store.finish("949d26c4-928a-443e-8961-05c742eec810","failed", None, "unknown")
    captured = capsys.readouterr()
    assert not captured.out and not captured.err

def test_http_transport_does_not_follow_redirects_or_read_response(monkeypatch):
    from src import error_history
    calls = []
    class Response:
        status = 204
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): raise AssertionError("Must not read provider text")
    class Opener:
        def open(self, request, timeout):
            calls.append((request,timeout))
            return Response()
    def builder(handler):
        assert handler.redirect_request(None,None,302,"",{}, "https://evil.example") is None
        return Opener()
    monkeypatch.setattr(error_history, "build_opener", builder)
    assert HistoryStore(config()).begin("NameError: x", "python")
    request, timeout = calls[0]
    assert request.get_method() == "POST"
    assert request.full_url == URL + "/rest/v1/rpc/archive_error"
    assert json.loads(request.data)["p_log"] == "NameError: x"
    assert timeout == 3

def test_http_error_is_safe_and_not_reported_as_saved(monkeypatch):
    from src import error_history
    class Opener:
        def open(self, *args, **kwargs):
            from urllib.error import HTTPError
            raise HTTPError(URL, 403, "SECRET response", {}, None)
    monkeypatch.setattr(error_history, "build_opener", lambda handler: Opener())
    assert HistoryStore(config()).begin("NameError: x", "python") is None

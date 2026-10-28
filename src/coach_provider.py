"""One optional HTTPS request; bounded selection, no arbitrary model prose."""
from dataclasses import dataclass
import hmac
import json
from threading import Lock
import time
import urllib.error
import urllib.request

from src.learning_coach import CoachContext, Question, standard_question, validate_choice


ENDPOINT = "https://api.openai.com/v1/responses"
MODEL = "gpt-5.4-mini-2026-03-17"
MAX_RESPONSE = 65_536
INSTRUCTIONS = (
    "Choose exactly one supplied learning question appropriate to the learner goal and evidence. "
    "Use only a supplied question ID and that question's basis_id. These are static analysis candidates, "
    "not confirmed runtime causes. Do not generate prose, code, diagnoses or tool calls. "
    "Prefer a concrete check over revealing an answer; do not raise the supplied confidence."
)


@dataclass(frozen=True, repr=False)
class CoachConfig:
    enabled: bool = False
    api_key: str = ""
    access_code: str = ""

    @property
    def ready(self) -> bool:
        return (self.enabled and isinstance(self.api_key, str) and bool(self.api_key.strip())
                and isinstance(self.access_code, str) and 16 <= len(self.access_code) <= 256)

    @classmethod
    def from_mapping(cls, values):
        return cls(values.get("AI_TUTOR_ENABLED") in (True, "true"),
                   values.get("OPENAI_API_KEY", ""), values.get("AI_TUTOR_ACCESS_CODE", ""))


@dataclass(frozen=True)
class CoachOutcome:
    status: str
    question: Question


def build_request(context: CoachContext) -> dict:
    return {"model": MODEL, "store": False, "max_output_tokens": 256,
            "reasoning": {"effort": "none"}, "instructions": INSTRUCTIONS,
            "input": json.dumps(context.to_dict(), ensure_ascii=False, sort_keys=True),
            "text": {"format": {"type": "json_schema", "name": "next_step_choice", "strict": True,
                "schema": {"type": "object", "properties": {
                    "question_id": {"type": "string", "enum": [q.id for q in context.candidates]},
                    "basis_ids": {"type": "array", "items": {"type": "string", "enum": [e.id for e in context.evidence]},
                                  "minItems": 1, "maxItems": 1}},
                    "required": ["question_id", "basis_ids"], "additionalProperties": False}}}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the authorization header to a redirected destination.
        raise urllib.error.HTTPError(ENDPOINT, code, "Redirect refused", headers, fp)


def http_transport(body: dict, api_key: str) -> dict:
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 16_384:
        raise ValueError("Request too large")
    request = urllib.request.Request(ENDPOINT, data=encoded, method="POST",
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=10) as reply:
        raw = reply.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Response too large")
    return json.loads(raw)


def _extract_choice(reply):
    if type(reply) is not dict or reply.get("status") != "completed":
        raise ValueError("Incomplete response")
    # Permit only one assistant message with one output text part. Refusals and
    # tools are not rendered; a reasoning item is not expected with effort=none.
    output = reply.get("output")
    if type(output) is not list or len(output) != 1:
        raise ValueError("Unexpected output")
    message = output[0]
    if message.get("type") != "message" or message.get("role") != "assistant":
        raise ValueError("Unexpected message")
    content = message.get("content")
    if type(content) is not list or len(content) != 1 or content[0].get("type") != "output_text":
        raise ValueError("Refused or invalid output")
    text = content[0].get("text")
    if not isinstance(text, str) or len(text) > 2048:
        raise ValueError("Invalid output size")
    return json.loads(text)


class CoachService:
    """Process-wide locked trial quotas; not a persistent or billing-level cap."""
    def __init__(self, config: CoachConfig, *, transport=None, clock=time.monotonic,
                 session_limit=3, total_limit=30):
        self.config = config
        self._transport = transport or http_transport
        self._clock = clock
        self._lock = Lock()
        self._started = clock()
        self._sessions = {}
        self._total = 0
        self._busy = False
        self._session_limit, self._total_limit = session_limit, total_limit

    def choose(self, context: CoachContext, *, consent: bool, access_code: str, session_id: str) -> CoachOutcome:
        fallback = standard_question(context)
        def result(status): return CoachOutcome(status, fallback)
        if not self.config.ready:
            return result("disabled")
        if consent is not True:
            return result("consent_required")
        if (not isinstance(access_code, str) or len(access_code) > 256
                or not hmac.compare_digest(access_code.encode(), self.config.access_code.encode())):
            return result("access_required")
        if not isinstance(session_id, str) or not 1 <= len(session_id) <= 128:
            return result("limited")
        with self._lock:
            if self._clock() - self._started >= 86_400:
                self._started, self._total, self._sessions = self._clock(), 0, {}
            if (self._busy or self._total >= self._total_limit
                    or self._sessions.get(session_id, 0) >= self._session_limit):
                return result("limited")
            self._busy = True
            self._total += 1
            self._sessions[session_id] = self._sessions.get(session_id, 0) + 1
        try:
            body = build_request(context)
            reply = self._transport(body, self.config.api_key)
            return CoachOutcome("ai", validate_choice(context, _extract_choice(reply)))
        except Exception:
            # Do not log/return provider exceptions, responses or input values.
            return result("unavailable")
        finally:
            with self._lock:
                self._busy = False

"""Write-only private error archive. Never executes code or logs request bodies."""
import base64
import json
import re
from dataclasses import dataclass, field
from urllib.request import Request, HTTPRedirectHandler, build_opener
from uuid import UUID, uuid4

from src.explanations import CATEGORIES, CATEGORY_LABELS

MAX_LOG_CHARS = 100_000
TIMEOUT = 3
_ERROR_TYPES = set(CATEGORIES) | {"CompilationError", "LinkerError", "SegmentationFault"}
_STATES = {"recognized", "unrecognized", "failed", "rejected"}
_MASK = "[伏せ字]"
_PATTERNS = [
    # Remove whole PEM blocks, including newlines.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"(?i)\bauthorization\s*:\s*(?:bearer|basic)\s+\S+"),
    re.compile(r"""(?ix)["']?\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret(?:[_-]?key)?|password|passwd|token)["']?\s*[:=]\s*(?:"[^"\n]*(?:"|$)|'[^'\n]*(?:'|$)|[^\s,;]+)"""),
    re.compile(r"(?i)\bhttps?://[^\s<>\"']+"),
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    # Absolute Windows, UNC, and POSIX paths. Keep traceback line numbers outside quotes.
    re.compile(r"""(?i)"(?:[a-z]:[\\/]|\\\\|/)[^"\r\n]*(?:"|$)|'(?:[a-z]:[\\/]|\\\\|/)[^'\r\n]*(?:'|$)"""),
    re.compile(r"""(?i)(?:[a-z]:[\\/]|\\\\)[^\r\n"']+"""),
    re.compile(r"""(?<![\w:])/(?:[^\s"'<>:,;/]+/)*[^\s"'<>:,;]*"""),
]


def redact_log(text: str) -> tuple[str, int]:
    """Best-effort redaction, not a guarantee of anonymity for arbitrary prose."""
    text = text[:MAX_LOG_CHARS]
    total = 0
    for pattern in _PATTERNS:
        text, count = pattern.subn(_MASK, text)
        total += count
    return text, total


@dataclass(frozen=True)
class HistoryConfig:
    url: str
    secret_key: str = field(repr=False)

    @classmethod
    def from_mapping(cls, values):
        enabled = values.get("enabled", False)
        if enabled is False or enabled in ("false", ""):
            return None
        if enabled is not True:
            raise ValueError("履歴保存の設定を確認してください。")
        url, key = values.get("url", ""), values.get("secret_key", "")
        if type(url) is not str or not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", url):
            raise ValueError("履歴保存の接続先を確認してください。")
        if type(key) is not str or not key or key != key.strip() or re.search(r"\s", key):
            raise ValueError("履歴保存の認証設定を確認してください。")
        valid = bool(re.fullmatch(r"sb_secret_[A-Za-z0-9_-]{20,}", key))
        if not valid:
            try:
                parts = key.split(".")
                claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
                valid = len(parts) == 3 and claims.get("role") == "service_role"
            except (ValueError, IndexError, TypeError, AttributeError):
                valid = False
        if not valid:
            raise ValueError("履歴保存の認証設定を確認してください。")
        return cls(url, key)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(url, headers, payload, timeout):
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
    with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        if response.status not in (200, 201, 204):
            raise OSError("履歴保存に失敗しました。")
        # Do not read, return, or log provider response text.


class HistoryStore:
    def __init__(self, config: HistoryConfig, *, transport=None):
        self.config = config
        self._transport = transport or _post

    def _call(self, method, payload):
        try:
            headers = {"apikey": self.config.secret_key, "Content-Type": "application/json",
                       "Prefer": "return=minimal"}
            if not self.config.secret_key.startswith("sb_secret_"):
                headers["Authorization"] = "Bearer " + self.config.secret_key
            self._transport(self.config.url + "/rest/v1/rpc/" + method, headers, payload, TIMEOUT)
            return True
        except Exception:
            # Exceptions can contain the log, key, URL or provider response.
            return False

    def begin(self, log: str, language: str) -> str | None:
        if type(log) is not str or not log.strip() or language not in {"python", "c", "cpp"}:
            return None
        text, count = redact_log(log)
        truncated = len(log) > MAX_LOG_CHARS or len(text) > MAX_LOG_CHARS
        text = text[:MAX_LOG_CHARS]
        ident = str(uuid4())
        saved = self._call("archive_error", {"p_id": ident, "p_language": language,
            "p_log": text, "p_redactions": count, "p_truncated": truncated})
        return ident if saved else None

    def finish(self, ident, status, error_type=None, category="unknown") -> bool:
        try:
            valid_id = type(ident) is str and UUID(ident).version == 4 and str(UUID(ident)) == ident
        except (ValueError, AttributeError):
            valid_id = False
        if not valid_id or status not in _STATES:
            return False
        name = error_type if error_type in _ERROR_TYPES else "unknown"
        category = category if category in CATEGORY_LABELS and name != "unknown" else "unknown"
        return self._call("complete_error", {"p_id": ident, "p_status": status,
            "p_error_type": name, "p_category": category})

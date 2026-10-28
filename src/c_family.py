"""GCC/Clang and MSVC diagnostics for C and C++; never compiles input code."""

import re

from src.models import ParsedError, TraceFrame


_LEVEL = r"fatal error|error|warning|note|致命的エラー|エラー|警告|注記"
_GCC = re.compile(r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*(?P<level>" + _LEVEL + r"):\s*(?P<message>.*)$")
_MSVC = re.compile(r"^(?P<file>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s*(?P<level>" + _LEVEL + r")\s+(?P<code>C[0-9]{4}|LNK[0-9]{4}):\s*(?P<message>.*)$")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MSVC_CATEGORIES = {
    "C2065": ("CompilationError", "variable"),
    "C2143": ("CompilationError", "syntax"), "C2059": ("CompilationError", "syntax"),
    "C1083": ("CompilationError", "module"),
    "C2440": ("CompilationError", "type"), "C2664": ("CompilationError", "type"),
    "C2660": ("CompilationError", "type"),
    "LNK2001": ("LinkerError", "linker"), "LNK2019": ("LinkerError", "linker"),
    "LNK1120": ("LinkerError", "linker"),
}


def _line_number(value: str | None) -> int | None:
    if not value or len(value) > 9:
        return None
    number = int(value)
    return number if number > 0 else None


def _classify(message: str, code: str | None = None) -> tuple[str, str, str | None]:
    lower = message.lower()
    if code in MSVC_CATEGORIES:
        name, category = MSVC_CATEGORIES[code]
        # Keep named targets when the existing English message supports them.
        _, _, target = _classify(message)
        return name, category, target
    if "undefined reference to" in lower or "undefined symbol" in lower or "unresolved external symbol" in lower:
        target_match = re.search(r"(?:undefined reference to|unresolved external symbol)\s+[`'‘\"]([^`'’\"]+)", message, re.I)
        return "LinkerError", "linker", target_match[1] if target_match else None
    if "no such file or directory" in lower or "file not found" in lower:
        header = re.search(r"[<\"']([^>\"']+)[>\"']", message)
        return "CompilationError", "module", header[1] if header else None
    if "not declared in this scope" in lower or "undeclared identifier" in lower or "use of undeclared identifier" in lower or "unknown type name" in lower:
        name = re.search(r"[‘'\"]([^’'\"]+)[’'\"]", message)
        return "CompilationError", "variable", name[1] if name else None
    if "cannot convert" in lower or "invalid conversion" in lower or "no matching function" in lower or "no matching member function" in lower or "cannot bind" in lower:
        return "CompilationError", "type", None
    if "expected" in lower:
        return "CompilationError", "syntax", None
    return "CompilationError", "compile", None


def parse_c_family_diagnostic(log: str, *, language: str = "cpp") -> ParsedError:
    """Extract one actionable compiler diagnostic or a common runtime failure."""
    language = "c" if language.lower() == "c" else "cpp"
    if not log.strip():
        return ParsedError(language=language, warnings=("コンパイラのエラー出力を貼り付けてください。",))

    lines = _ANSI.sub("", log).replace("\r\n", "\n").splitlines()
    for parser in (_GCC, _MSVC):
        for raw in lines:
            match = parser.fullmatch(raw.strip())
            if not match or match["level"] not in {"error", "fatal error", "エラー", "致命的エラー"}:
                continue
            message = match["message"].strip()
            code = match.groupdict().get("code")
            error_type, category, target = _classify(message, code)
            line = _line_number(match["line"])
            file = match["file"].strip()
            frame = (TraceFrame(file, line, source=None),) if line else ()
            warnings = () if line else ("診断の行番号を読み取れませんでした。ログ全体を確認してください。",)
            return ParsedError(language, error_type, message, file, line, target,
                               category, frame, "complete" if line else "partial", warnings, code)

    text = "\n".join(lines)
    native_linker = next((re.search(r"(?:fatal error|error|エラー)\s+(LNK[0-9]{4}):\s*(.*)$", line) for line in lines
                          if re.search(r"(?:fatal error|error|エラー)\s+LNK[0-9]{4}:", line)), None)
    if native_linker:
        _, _, target = _classify(native_linker[2])
        return ParsedError(language=language, error_type="LinkerError", message=native_linker[2],
                           target=target, category="linker", status="partial", diagnostic_code=native_linker[1],
                           warnings=("リンク時の診断です。関連するソースとビルド設定を確認してください。",))
    if re.search(r"\bsegmentation fault\b|\baccess violation\b", text, re.I):
        return ParsedError(language, "SegmentationFault", "Segmentation fault / access violation",
                           category="runtime", status="partial",
                           warnings=("実行時の不正なメモリアクセスを示す可能性があります。ログだけでは原因の行やポインターを特定できません。",))
    linker = next((line.strip() for line in lines if re.search(
        r"undefined reference to|undefined symbol|unresolved external symbol|symbol\(s\) not found",
        line, re.I)), None)
    if linker:
        error_type, category, target = _classify(linker)
        return ParsedError(language, error_type, linker, target=target, category=category, status="partial",
                           warnings=("リンク時の診断です。関連するソースとビルド設定を確認してください。",))
    return ParsedError(language=language, warnings=("C/C++のコンパイラ診断を特定できませんでした。GCC/ClangまたはMSVCのエラー行を貼り付けてください。",))

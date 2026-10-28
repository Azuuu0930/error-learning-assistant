"""Python tracebackを文字列として解析する。入力コードは実行しない。"""

import re

from src.models import ParsedError, TraceFrame


SUPPORTED_ERRORS = (
    "SyntaxError", "IndentationError", "NameError", "TypeError", "ValueError",
    "IndexError", "KeyError", "AttributeError", "ModuleNotFoundError", "ImportError",
    "FileNotFoundError", "ZeroDivisionError",
)

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_FRAME = re.compile(
    r'^\s*File ["\'](?P<file>.+?)["\'], line (?P<line>\d+)'
    r'(?:, in (?P<function>.*))?\s*$'
)
_EXCEPTION = re.compile(
    r"^(?P<type>(?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)(?::\s?(?P<message>.*))?$"
)
_SEPARATORS = (
    "During handling of the above exception",
    "The above exception was the direct cause",
    "Traceback (most recent call last):",
)


def _exception(line: str) -> re.Match | None:
    # インデントされたソースコードを例外の最終行と誤認しない。
    if line != line.lstrip():
        return None
    match = _EXCEPTION.fullmatch(line.rstrip())
    if not match:
        return None
    name = match["type"].rsplit(".", 1)[-1]
    if name in {"Traceback", "File", "Error", "Warning", "INFO", "DEBUG", "ERROR"}:
        return None
    # 独自例外も扱うが、任意の文章や辞書キーは例外と見なさない。
    if name in SUPPORTED_ERRORS or name.endswith(("Error", "Exception", "Warning")):
        return match
    if name in {"KeyboardInterrupt", "SystemExit", "StopIteration", "GeneratorExit"}:
        return match
    if name[0].isupper() and any(c.islower() for c in name) and match["message"] is not None:
        return match
    return None


def _target(error_type: str, message: str) -> str | None:
    patterns = {
        "NameError": r"(?:name|local variable) ['\"]([^'\"]+)['\"]",
        "AttributeError": r"has no attribute ['\"]([^'\"]+)['\"]",
        "ModuleNotFoundError": r"No module named ['\"]([^'\"]+)['\"]",
        "ImportError": r"cannot import name ['\"]([^'\"]+)['\"]",
        "FileNotFoundError": r": ['\"](.+)['\"]$",
        "TypeError": r"unsupported operand type\(s\) for ([^:]+):",
        "ValueError": r"invalid literal for .+?: ['\"](.*)['\"]$",
    }
    if error_type == "KeyError":
        return message.strip().strip("'\"") or None
    pattern = patterns.get(error_type)
    match = re.search(pattern, message) if pattern else None
    return match[1] if match else None


def parse_python_traceback(log: str) -> ParsedError:
    """最終例外と、その例外に属する最後のフレームを抽出する。

    連鎖した例外では最後の例外を主結果にする。未知の形式・途中のログは
    status/warningsで返し、取得できない値を推測で補わない。
    """
    if not log.strip():
        return ParsedError(warnings=("エラーログが空です。エラー履歴と最後のエラー行を貼り付けてください。",))
    lines = _ANSI.sub("", log).replace("\r\n", "\n").splitlines()
    candidates = [(i, match) for i, line in enumerate(lines) if (match := _exception(line))]
    if candidates:
        end, final = candidates[-1]
        start = candidates[-2][0] + 1 if len(candidates) > 1 else 0
    else:
        end, final, start = len(lines), None, 0
    # 最終のtraceback区間だけを対象にして、別の例外の行番号を流用しない。
    for i in range(start, end):
        if lines[i].startswith(_SEPARATORS):
            start = i + 1
    frames = []
    for i in range(start, end):
        match = _FRAME.fullmatch(lines[i])
        if not match:
            continue
        # 壊れた巨大な数値などでもint変換例外を起こさない。
        raw_line = match["line"]
        if len(raw_line) > 9 or int(raw_line) < 1:
            continue
        source = None
        if i + 1 < end:
            next_line = lines[i + 1]
            if next_line.startswith(("    ", "\t")) and not _FRAME.fullmatch(next_line):
                source = next_line.strip() or None
        frames.append(TraceFrame(match["file"], int(raw_line), match["function"], source))
    last_frame = frames[-1] if frames else None
    warnings = []
    if len(candidates) > 1:
        warnings.append("複数の例外を検出しました。最後の例外を表示しています。原因の連鎖は元のログも確認してください。")
    if final:
        error_type = final["type"]
        message = final["message"] or ""
        # エラーメッセージが複数行の場合も保持する（末尾の空行は除く）。
        continuation = "\n".join(lines[end + 1:]).strip()
        if continuation:
            message = "\n".join(part for part in (message, continuation) if part)
        if not last_frame:
            warnings.append("ファイル名と行番号を取得できませんでした。エラー履歴全体を貼ると場所も確認できます。")
        if not message:
            warnings.append("エラーメッセージがありません。最後のエラー行が途中で切れていないか確認してください。")
        status = "complete" if last_frame and message else "partial"
    else:
        error_type, message = None, ""
        status = "partial" if frames else "unrecognized"
        warnings.append("エラー種類を特定できませんでした。最後の「エラー種類: メッセージ」の行も貼り付けてください。")
    return ParsedError(
        error_type=error_type, message=message,
        file=last_frame.file if last_frame else None,
        line=last_frame.line if last_frame else None,
        target=_target(error_type.rsplit(".", 1)[-1], message) if error_type else None,
        frames=tuple(frames), status=status, warnings=tuple(warnings),
    )

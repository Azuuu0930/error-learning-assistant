"""入力 → ログ解析 → 分類 → 教育向け説明 → ヒント、をまとめる。"""

from dataclasses import replace

from src.code_analysis import analyze_code
from src.c_family import parse_c_family_diagnostic
from src.explanations import CATEGORIES, ExplanationProvider, RuleBasedExplanationProvider, explain_syntax_context
from src.hints import generate_hints
from src.models import AnalysisResult, CodeLine
from src.parser import parse_python_traceback


def analyze_error(log: str, source_code: str = "", *, language: str = "python",
                  provider: ExplanationProvider | None = None) -> AnalysisResult:
    language = language.lower()
    if language in {"c", "cpp", "c++"}:
        language = "c" if language == "c" else "cpp"
        parsed = parse_c_family_diagnostic(log, language=language)
    else:
        language = "python"
        parsed = parse_python_traceback(log)
    name = (parsed.error_type or "").rsplit(".", 1)[-1]
    error = replace(parsed, category=CATEGORIES.get(name, parsed.category))
    explanation = (provider or RuleBasedExplanationProvider()).explain(error)
    if provider is None and language == "python":
        explanation = explain_syntax_context(error, source_code, explanation)
    code_analysis = analyze_code(source_code, error) if source_code.strip() and language == "python" else None
    syntax_issue = code_analysis.syntax_error if code_analysis else None
    context = ()
    notes = []
    if source_code.strip():
        lines = source_code.splitlines()
        if error.line and 1 <= error.line <= len(lines):
            start = max(1, error.line - 2)
            stop = min(len(lines), error.line + 2)
            context = tuple(CodeLine(i, lines[i - 1], i == error.line) for i in range(start, stop + 1))
            notes.append("貼り付けたコードの1行目を、ファイルの1行目として表示しています。最終フレームのファイルと一致するか確認してください。")
        elif error.line:
            if syntax_issue:
                notes.append(f"ログの {error.line} 行目は入力コード（{len(lines)}行）の範囲外です。コード断片やノートブックでは行番号が異なることがあります。入力コード内の場所は「コードから分かったこと」に別に表示します。")
            else:
                notes.append(f"ログの {error.line} 行目は、貼り付けたコード（{len(lines)}行）の範囲外です。該当ファイル全体を貼り付けてください。")
        else:
            if syntax_issue:
                notes.append("ログには行番号がありませんが、入力コードの構文上の問題と場所は「コードから分かったこと」で確認できます。")
            else:
                notes.append("行番号が取得できないため、コードの該当行を表示できません。エラー履歴全体を貼り付けてください。")
    if len({frame.file for frame in error.frames}) > 1:
        notes.append("複数のファイルが含まれています。最後のフレームはライブラリ内の場合もあります。元のログで呼び出し元も確認してください。")
    if provider is None and name == "IncompleteInputError" and code_analysis and code_analysis.syntax_error:
        issue = code_analysis.syntax_error
        explanation = replace(explanation,
                              cause="貼り付けたコードの構文解析では、" + issue.explanation.summary + issue.explanation.cause
                                    + " 元ログと同じコードの状態かは、この解析だけでは断定できません。",
                              checkpoints=issue.explanation.checkpoints)
    return AnalysisResult(error, explanation, generate_hints(error, explanation, code_analysis),
                          context, tuple(notes), code_analysis)

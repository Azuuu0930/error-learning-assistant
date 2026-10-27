"""答えを先に見せず、場所 → 注目点 → 確認行動の順に案内する。"""

from src.models import CodeAnalysis, Explanation, ParsedError


def generate_hints(error: ParsedError, explanation: Explanation,
                   code_analysis: CodeAnalysis | None = None) -> tuple[str, str, str]:
    if code_analysis and code_analysis.status == "parsed":
        context_hints = _code_hints(error, code_analysis)
        if context_hints:
            return context_hints
    if error.line:
        first = f"{error.file or '該当ファイル'} の {error.line} 行目付近を確認してください。文法エラーでは直前の行も見てみましょう。"
    else:
        first = "ログの末尾を見てください。最後の File と line に、調べるファイルと行番号があります。"
    if error.target:
        second = f"メッセージに出てくる「{error.target}」に注目してください。コードのどこで使っていますか？"
    elif error.error_type:
        second = f"最後の行の「{error.error_type}」と、その後ろのメッセージを読み、失敗した操作を探してみてください。"
    else:
        second = "「エラー種類: メッセージ」の行はありますか？ ログが途中で切れていないか確認してください。"
    third = explanation.checkpoints[0]
    return first, second, third


def _code_hints(error: ParsedError, analysis: CodeAnalysis) -> tuple[str, str, str] | None:
    name = (error.error_type or "").rsplit(".", 1)[-1]
    new_kinds = {
        'TypeError': {'incompatible_operation', 'invalid_index_type', 'unhashable_key', 'call_arguments'},
        'AttributeError': {'missing_attribute'}, 'KeyError': {'missing_key'},
        'ZeroDivisionError': {'zero_division'}, 'ValueError': {'invalid_conversion'},
        'AssertionError': {'assertion_failure'}, 'StopIteration': {'empty_iterator'},
        'RuntimeError': {'iteration_mutation'},
    }.get(name, set())
    candidates = [f for f in analysis.findings if f.kind in new_kinds and (not error.line or f.line == error.line)]
    if len(candidates) == 1:
        finding = candidates[0]
        second = ('関数の定義と、呼び出す側の位置引数・キーワード引数を比べてください。'
                  if finding.kind == 'call_arguments' else '関係する値の型・内容と、その操作で使える値を調べてください。')
        return ('エラー行の式や呼び出しを確認してください。', second,
                'コード内の候補：' + finding.message)
    kinds = {
        "NameError": ("similar_name", "use_before_definition", "undefined_name", "possibly_unbound"),
        "UnboundLocalError": ("use_before_definition", "possibly_unbound", "undefined_name"),
        "ModuleNotFoundError": ("import_match",), "ImportError": ("import_match",),
        "AttributeError": ("attribute_access",), "IndexError": ("index_out_of_range",),
    }.get(name, ())
    for kind in kinds:
        finding = next((item for item in analysis.findings if item.kind == kind
                        and (not error.line or item.line == error.line)
                        and (not error.target or name == "IndexError" or item.target == error.target)), None)
        if not finding:
            continue
        if kind == "similar_name":
            return ("エラー行で使っている変数名を確認してください。",
                    "似た名前の変数がコード内にないか探し、つづりを比べてみてください。",
                    f"「{finding.target}」と「{'、'.join(finding.related_names)}」を比較してください。タイプミスの候補ですが、意図した名前は自分で確認しましょう。")
        if kind == "use_before_definition":
            return ("エラー行で使っている変数名を確認してください。",
                    "値を代入する行と使う行は、どちらが先にありますか？",
                    f"「{finding.target}」の使用と定義の順序を確認してください。この参照までに値を与えていますか？")
        if kind in {"undefined_name", "possibly_unbound"}:
            return ("エラー行で使っている変数名を確認してください。",
                    "そのスコープで使える名前の定義や代入を探してみてください。",
                    f"「{finding.target}」に値を与える処理が、この参照より前にあるか確認してください。")
        if kind == "import_match":
            return ("エラー行付近のimport文を確認してください。",
                    "ログで読み込めなかった名前と、import文で指定した名前を照らし合わせてみてください。",
                    f"{finding.line}行目の「{finding.evidence}」と、ログの「{finding.target}」を比較してください。環境や名前を確認しましょう。")
        if kind == "attribute_access":
            return ("エラー行のドットの前後を確認してください。",
                    "ドットの左側の値が、右側の機能を持っているか調べてみてください。",
                    f"{finding.line}行目の「{finding.evidence}」に注目してください。属性があるかは実行時の型や値の確認が必要です。")
        if kind == "index_out_of_range":
            return ("エラー行で、角括弧 [] に書いた位置番号を確認してください。",
                    "リストの要素数と、0から数える位置番号の範囲を比べてみてください。",
                    f"「{finding.target}」は要素数{finding.related_names[0]}に対し位置{finding.related_names[1]}を指定しています。負の位置にも取り出せる範囲があります。")
    return None

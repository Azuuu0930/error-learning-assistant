"""主要エラーの分類と、学習用の説明。LLM/APIキーは必要ない。"""

import keyword
import re
from dataclasses import replace
from typing import Protocol

from src.models import Explanation, ParsedError


CATEGORIES = {
    "SyntaxError": "syntax", "IndentationError": "indentation",
    "NameError": "variable", "TypeError": "type", "ValueError": "value",
    "IndexError": "index", "KeyError": "key", "AttributeError": "attribute",
    "ModuleNotFoundError": "module", "ImportError": "import",
    "FileNotFoundError": "file", "ZeroDivisionError": "arithmetic",
    "UnboundLocalError": "variable", "RecursionError": "recursion",
    "StopIteration": "iteration", "AssertionError": "assertion",
    "RuntimeError": "runtime", "UnicodeDecodeError": "encoding",
}
CATEGORY_LABELS = {
    "syntax": "文法", "indentation": "字下げ", "variable": "変数・名前",
    "type": "データの種類", "value": "値の内容", "index": "リストなどの位置",
    "key": "辞書のキー", "attribute": "属性・メソッド", "module": "モジュール",
    "import": "読み込み", "file": "ファイル", "arithmetic": "計算", "unknown": "未分類",
    "recursion": "再帰", "iteration": "反復", "assertion": "条件の確認",
    "runtime": "実行時の操作", "encoding": "文字コード",
    "compile": "コンパイル", "linker": "リンク",
}


class ExplanationProvider(Protocol):
    """将来、構造化情報を受け取るLLM実装に差し替えるための境界。"""

    def explain(self, error: ParsedError) -> Explanation: ...


def _make(summary: str, cause: str, points: tuple[str, ...], tip: str,
          fix: str | None = None) -> Explanation:
    return Explanation(summary, cause, points, tip, fix)


def _explain_c_family(error: ParsedError) -> Explanation:
    target = f"「{error.target}」" if error.target else "該当箇所"
    if error.error_type == "LinkerError":
        return _make(
            "コンパイル後のリンク処理で、必要な関数やシンボルを見つけられませんでした。",
            f"{target}の定義がビルド対象に含まれていない、宣言と定義の名前が違う、または必要なライブラリがリンクされていない可能性があります。",
            ("宣言だけでなく、その関数を定義したソースファイルもビルドしているか確認してください。",
             "関数名・引数・名前空間が宣言側と定義側で一致するか確認してください。",
             "外部ライブラリを使う場合、リンク設定に追加されているか確認してください。"),
            "undefined reference / unresolved external は、ソースの文法ではなくリンク段階の診断です。",
            "int add(int a, int b) { return a + b; }\nint main() { return add(2, 3); }",
        )
    if error.error_type == "SegmentationFault":
        return _make(
            "実行中に、プログラムが許可されていないメモリへアクセスした可能性があります。",
            "無効なポインター、配列の範囲外、解放後のメモリ参照などが候補ですが、このログだけでは原因を特定できません。",
            ("停止したときのスタックトレースやデバッガの行番号を確認してください。",
             "ポインターが初期化済みで、有効なオブジェクトを指しているか調べてください。",
             "配列や文字列の添字が有効範囲内か確認してください。"),
            "Segmentation fault は実行時の失敗です。コンパイラのエラー行とは別に、デバッガで停止位置を調べます。",
        )
    if error.category == "module":
        return _make(
            "指定したヘッダーファイルをコンパイラが見つけられませんでした。",
            f"{target}の名前や綴りが違う、開発環境にヘッダーがない、または検索パスが設定されていない可能性があります。",
            ("include行の山括弧・引用符とヘッダー名を確認してください。",
             "そのヘッダーを提供するコンパイラやライブラリがインストールされているか確認してください。",
             "独自ヘッダーの場合は、コンパイラのinclude検索パスを確認してください。"),
            "fatal error / file not found は、ビルド環境がinclude先を開けないことを示します。",
            "#include <iostream>\nint main() { std::cout << \"Hello\"; }",
        )
    if error.category == "variable":
        return _make(
            f"コードで使った名前{target}を、この場所でコンパイラが見つけられませんでした。",
            "宣言より前に使っている、名前の綴りが違う、またはその変数が見える範囲の外にある可能性があります。",
            ("診断に表示された名前の綴りと大文字・小文字を確認してください。",
             "使う前に変数や関数を宣言しているか確認してください。",
             "宣言がブロックや関数の内側にあり、利用箇所から見えなくなっていないか確認してください。"),
            "was not declared / undeclared identifier は、その位置から名前を解決できないという診断です。",
            "#include <iostream>\nint main() { int total = 0; std::cout << total; }",
        )
    if error.category == "type":
        return _make(
            "指定した演算や関数呼び出しに、受け取れない型の値が渡された可能性があります。",
            "C/C++では暗黙変換が許されない場合や、関数の宣言と渡した引数が合わない場合にコンパイルエラーになります。",
            ("診断に出ている変換元と変換先の型を確認してください。",
             "関数の宣言が求める引数の数と型を確認してください。",
             "必要な変換を安全に行えるか、値の範囲も含めて確認してください。"),
            "cannot convert / no matching function は、値の型や呼び出し方が候補と一致しないことを示します。",
            "int main() { int count = 3; double ratio = static_cast<double>(count); return ratio > 0; }",
        )
    return _make(
        "コンパイラがコードを受け付けず、実行ファイルを作れませんでした。",
        "文法、型、宣言などの問題が考えられます。表示された診断メッセージだけで原因を絞れない場合があります。",
        ("最初に出た error 行と、そのファイル名・行番号を確認してください。",
         "示された行だけでなく、直前の行の括弧・セミコロン・型も確認してください。",
         "エラーが複数ある場合は、先頭の診断を直してからもう一度ビルドしてください。"),
        "警告や後続エラーより、最初の error 診断が原因を探す手がかりになります。",
        "int main() { return 0; }",
    )


class RuleBasedExplanationProvider:
    def explain(self, error: ParsedError) -> Explanation:
        name = (error.error_type or "").rsplit(".", 1)[-1]
        target = error.target
        message = error.message
        if error.language in {"c", "cpp"}:
            return _explain_c_family(error)
        if name == 'UnboundLocalError':
            return _make(
                '関数のローカル変数を、値が代入される前に参照しました。',
                '関数内に代入がある名前は、global/nonlocalの指定がなければローカル変数として扱われます。外側の同名変数を読むつもりでも、代入前の参照になる可能性があります。',
                ('関数内で、その名前に代入する行と読む行の順序を確認してください。',
                 '分岐によって代入されない経路がないか確認してください。',
                 '外側の値を使うなら、引数で渡して戻り値を受け取る設計も検討してください。'),
                'local variable は関数内の変数です。単にグローバル変数が無いとは限りません。',
                'def increase(value):\n    return value + 1\n\ncount = 10\ncount = increase(count)',
            )
        if name == 'RecursionError':
            return _make(
                '関数を呼び出す深さがPythonの上限を超えました。',
                '再帰が終了条件に到達せず続いている可能性があります。終了する処理でも、必要な呼び出しの深さが大きすぎる場合があります。',
                ('終了条件と、それに近づくよう引数を変えているか確認してください。',
                 '直接の自分自身だけでなく、複数の関数が互いを呼んでいないか確認してください。',
                 '上限を安易に増やす前に、ループで表現できないか検討してください。'),
                'maximum recursion depth は再帰の呼び出し深さの上限です。無限再帰だと断定する情報ではありません。',
                'def countdown(number):\n    if number <= 0:\n        return\n    countdown(number - 1)\n\ncountdown(3)',
            )
        if name == 'StopIteration':
            return _make(
                'イテレータから取り出せる次の要素がありませんでした。',
                '空のイテレータや、最後まで読み終えたイテレータに next を呼んでいる可能性があります。',
                ('イテレータを作った元のデータが空でないか確認してください。',
                 '先に別の処理で要素を取り出していないか確認してください。',
                 '終端を許すならnext(iterator, 初期値)やfor文で扱う方法があります。'),
                'nextはイテレータを一つ進めます。StopIterationは終端を知らせる標準の仕組みです。',
                'iterator = iter([])\nvalue = next(iterator, None)\nprint(value)',
            )
        if name == 'AssertionError':
            return _make(
                'assert で確認した条件が False になりました。',
                'assertの右側で期待した条件を、実際の値が満たしていない可能性があります。',
                ('assertの条件を左右に分け、使っている値を確認してください。',
                 '境界値と、条件に達するまでの値の変更を確認してください。',
                 '利用者の入力チェックには、assertだけに頼らずif文などで案内してください。'),
                'assertの後ろが確認条件、カンマの後ろは失敗時の補足メッセージです。',
                'age = 15\nif age < 18:\n    print("18歳以上を想定しています")',
            )
        if name == 'RuntimeError':
            lower = message.lower()
            if 'changed size during iteration' in lower:
                subject = 'set（集合）' if 'set' in lower else '辞書' if 'dictionary' in lower else 'コレクション'
                cause = f'{subject}を走査中に要素数を変更したため、同じ反復を続けられませんでした。削除や追加をループと分ける必要がある可能性があります。'
            else:
                cause = '実行中の状態や操作の順序が、処理の前提に合わなかった可能性があります。RuntimeErrorには複数の原因があるため、後ろのメッセージを確認してください。'
            return _make(
                '実行中の状態では、その処理を続けられませんでした。', cause,
                ('元のメッセージが示す操作と、その直前の状態を確認してください。',
                 '反復中に辞書やsetの要素を追加・削除していないか確認してください。',
                 'ライブラリの状態が関係する場合は、その操作の前提条件を確認してください。'),
                'RuntimeErrorという種類だけでは原因は一つに決まりません。メッセージが調査の手がかりです。',
                'data = {"a": 1, "b": 2}\nfor key in list(data):\n    del data[key]',
            )
        if name == 'UnicodeDecodeError':
            match = re.match(r"['\"]([^'\"]+)['\"] codec", message)
            encoding = match[1] if match else '指定した文字コード'
            label = 'UTF-8' if encoding.lower().replace('_', '-') == 'utf-8' else encoding
            return _make(
                'バイト列を文字列へ読み替える処理に失敗しました。',
                f'{label}として不正なバイト列が含まれる、または元の文字コードと指定が違う可能性があります。ファイル破損や途中で切れたデータでも起こり得ます。',
                ('データを作った側の文字コードを確認してください。',
                 'decodeやopenに指定したencodingが一致しているか確認してください。',
                 'errors="ignore"で消す前に、読み飛ばしてよい内容か確認してください。'),
                'decodeはバイト列を文字に変換します。位置とcodec名が確認の手がかりです。',
                'data = "こんにちは".encode("utf-8")\nprint(data.decode("utf-8"))',
            )
        if name == "NameError":
            label = f"「{target}」という名前" if target else "指定された名前"
            # 名前だけを例に利用する。ログ由来の任意のコードを埋め込まない。
            variable = target if target and target.isidentifier() and not keyword.iskeyword(target) else "user_name"
            return _make(
                f"Pythonが{label}を使おうとしましたが、その場所で見つけられませんでした。",
                "変数が使用前に作られていない、スペルが違う、または使える範囲の外にある可能性があります。",
                ("その名前を使う前に値を代入しているか確認してください。",
                 "定義した名前と、大文字・小文字を含めてスペルが一致するか確認してください。",
                 "関数の中で作った変数を、関数の外から使っていないか確認してください。"),
                "最後の行の name の後ろが、Pythonが見つけられなかった名前です。",
                f'{variable} = "Taro"\nprint({variable})',
            )
        if name == "SyntaxError":
            return _make(
                "Pythonがコードの書き方を読み取れず、実行を始められませんでした。",
                "コロン・括弧・引用符などの不足や、文法に合わない書き方が考えられます。",
                ("表示された行だけでなく、直前の行も確認してください。",
                 "if / for / def などの末尾に : があるか確認してください。",
                 "括弧と引用符が閉じているか、ログの ^ が指す位置も確認してください。"),
                "^ はPythonが文法の問題に気づいた位置です。原因が前の行にあることもあります。",
                'age = 20\nif age >= 18:\n    print("成人です")',
            )
        if name == "IndentationError":
            return _make(
                "Pythonが、行の先頭の空白から処理のまとまりを判断できませんでした。",
                "字下げが必要な場所に空白がない、または同じまとまりの字下げが揃っていない可能性があります。",
                ("if / for / def の次の行を字下げしているか確認してください。",
                 "同じまとまりの行は、空白の数を揃えてください。",
                 "タブとスペースを混ぜていないか、エディタの空白表示で確認してください。"),
                "expected an indented block は「この後に字下げされた処理が必要」という意味です。",
                'if True:\n    print("字下げを揃えます")',
            )
        if name == "TypeError":
            points = ("関係する値を type(値) で調べ、文字列・数値などの種類を確認してください。",
                      "その操作が、その種類のデータで使えるか確認してください。",
                      "input() の結果は文字列です。数値として使う場合は変換できる内容か確認してください。")
            cause = "操作が受け取れるデータの種類や、関数の呼び出し方が合っていない可能性があります。"
            fix = 'age_text = "20"\nage = int(age_text)\nprint(age + 1)'
            if "not callable" in message:
                cause = "関数のように () で呼び出した値が、実際には数値や文字列などかもしれません。"
                points = ("() の直前にある名前の値と type() を確認してください。",
                          "print / list / str などの名前に別の値を代入していないか確認してください。",
                          "値を表示したい場合は print(値) を使ってください。")
                fix = "count = 3\nprint(count)"
            elif "required positional argument" in message:
                cause = "関数を動かすために必要な値（引数）が、呼び出し時に足りない可能性があります。"
                points = ("def の括弧内にある引数を確認してください。",
                          "呼び出しの括弧内に、必要な値を渡しているか確認してください。",
                          "省略できる引数には初期値があるか確認してください。")
                fix = 'def greet(name):\n    return f"Hello, {name}"\n\nprint(greet("Taro"))'
            elif "not subscriptable" in message:
                cause = "[] で取り出そうとした値が、リストや文字列などの取り出せるデータではない可能性があります。"
                fix = 'names = ["Taro", "Hanako"]\nprint(names[0])'
            return _make("Pythonが、そのデータや呼び出し方では指定された操作をできないと言っています。",
                         cause, points,
                         "メッセージ中の str は文字列、int は整数です。型名や演算子に注目してください。", fix)
        if name == "ValueError":
            return _make(
                "データの種類は受け取れましたが、その内容では処理を進められませんでした。",
                "例えば int() に「abc」を渡すと、整数として読めないため失敗します。メッセージで対象の処理を確認してください。",
                ("変換・処理しようとした元の値を確認してください。",
                 "空文字や数値ではない文字が混じっていないか確認してください。",
                 "想定外の入力を受け付ける場合は、失敗したときの案内も用意してください。"),
                "invalid literal は、変換先の形式で読み取れない内容が含まれる、という意味です。",
                'text = "20"\ntry:\n    age = int(text)\nexcept ValueError:\n    print("整数を入力してください")\nelse:\n    print(age)',
            )
        if name == "IndexError":
            return _make(
                "リストや文字列などから、存在しない位置の要素を取り出そうとしました。",
                "位置は0から数えます。3個のリストの位置は0・1・2で、3は範囲外です。",
                ("len(対象) で要素の数を確認してください。",
                 "正の位置は 0 以上 len(対象) 未満か確認してください。負の位置にも範囲があります。",
                 "空のリストになっていないか、ループが最後を越えていないか確認してください。"),
                "out of range は、指定した位置が取り出せる範囲の外、という意味です。",
                'names = ["Taro", "Hanako"]\nindex = 1\nif 0 <= index < len(names):\n    print(names[index])',
            )
        if name == "KeyError":
            label = f"「{target}」というキー" if target else "指定したキー"
            return _make(
                f"辞書から{label}の値を取り出そうとしましたが、そのキーがありませんでした。",
                "辞書は番号ではなく名前（キー）で値を探します。キーの不足やスペル違いが考えられます。",
                ("辞書の keys() を表示して、存在するキーを確認してください。",
                 "キーの大文字・小文字や、文字列と数値の違いを確認してください。",
                 "キーがない場合を許す設計なら、in で確認してから取り出してください。"),
                "KeyError の後ろにある値が、見つからなかったキーです。",
                'user = {"name": "Taro"}\nif "age" in user:\n    print(user["age"])\nelse:\n    print("年齢は登録されていません")',
            )
        if name == "AttributeError":
            label = f"「{target}」という属性・メソッド" if target else "指定された属性・メソッド"
            return _make(
                f"そのデータには、{label}がありませんでした。",
                "データの種類に合わない機能を呼んでいる、スペルが違う、または値が None の可能性があります。",
                ("ドットの左側にある値を type() で確認してください。",
                 "その種類のデータに、指定した機能があるか確認してください。",
                 "名前のスペルや、関数が None を返していないか確認してください。"),
                "has no attribute の後ろに、存在しない機能の名前が書かれています。",
                'names = ["Taro"]\nnames.append("Hanako")\nprint(names)',
            )
        if name == "ModuleNotFoundError":
            label = f"「{target}」というモジュール" if target else "指定されたモジュール"
            return _make(
                f"import で{label}を読み込もうとしましたが、見つかりませんでした。",
                "名前のスペル違い、未インストール、または実行するPython環境の違いが考えられます。",
                ("import に書いたモジュール名が正しいか確認してください。",
                 "配布名とimport名は違う場合があります。公式のインストール方法を確認してください。",
                 "実行中のPythonと同じ環境に入っているか、python -m pip show 配布名 で確認してください。"),
                "No module named の後ろが、Pythonが探した名前です。",
                'import math\nprint(math.sqrt(9))',
            )
        if name == "ImportError":
            return _make(
                "モジュールから、指定された名前や機能を読み込めませんでした。",
                "読み込みたい名前が存在しない、バージョンが違う、またはファイル同士が互いを読み込んでいる可能性があります。",
                ("from ... import ... の右側の名前が存在するか確認してください。",
                 "使用しているライブラリのバージョンと公式ドキュメントを確認してください。",
                 "自作ファイル名がライブラリ名と同じでないか、互いにimportしていないか確認してください。"),
                "cannot import name の後ろに、読み込めなかった名前が書かれています。",
                'from math import sqrt\nprint(sqrt(9))',
            )
        if name == "FileNotFoundError":
            return _make(
                "開こうとしたファイル、またはその途中のフォルダが見つかりませんでした。",
                "ファイル名やパスが違う、または実行時の作業フォルダが想定と違う可能性があります。",
                ("ファイル名・拡張子・大文字と小文字を確認してください。",
                 "Path.cwd() で現在の作業フォルダを確認してください。相対パスはそこから探します。",
                 "ファイルが実際にあるか、必要なフォルダも含めて確認してください。"),
                "メッセージ末尾のパスが、Pythonが見つけられなかったファイルです。",
                'from pathlib import Path\n\npath = Path("data.txt")\nif path.is_file():\n    print(path.read_text(encoding="utf-8"))\nelse:\n    print(f"ファイルを確認してください: {path.resolve()}")',
            )
        if name == "ZeroDivisionError":
            return _make(
                "数を0で割ろうとしたため、計算を続けられませんでした。",
                "割り算 / や //、余りを求める % の右側の値が0になっている可能性があります。",
                ("割る数（演算子の右側）が0か確認してください。",
                 "計算途中で0になっていないか、元の値も確認してください。",
                 "0の入力を許す場合は、計算前に分岐して案内してください。"),
                "division by zero は0での割り算、modulo by zero は0での余りの計算です。",
                'total = 10\ncount = 0\nif count != 0:\n    print(total / count)\nelse:\n    print("件数が0なので平均を計算できません")',
            )
        if not error.error_type:
            return _make(
                "ログからエラーの種類を読み取れませんでした。",
                "ログが途中で切れている、またはPythonの標準的な形式と異なる可能性があります。",
                ("Traceback から最後のエラー行までコピーしてください。",
                 "最後に「エラー種類: メッセージ」があるか確認してください。",
                 "Pythonで発生したログか確認してください。"),
                "まず最後のエラー行、次に直前の File と line を読みます。",
            )
        return _make(
            f"「{error.error_type}」を検出しました。この種類の専用説明はまだありません。",
            "原因は断定できません。元のメッセージと、発生した操作を照らし合わせてください。",
            ("最後の行のエラー種類とメッセージを確認してください。",
             "表示されたファイル・行番号の操作を確認してください。",
             "独自の例外なら、その例外を送出する箇所や公式資料を確認してください。"),
            "未知のエラーでも、末尾のメッセージと最後のフレームが調査の出発点になります。",
        )


def explain_syntax_context(error: ParsedError, code: str, explanation: Explanation) -> Explanation:
    """CPythonメッセージと周辺行で候補を具体化。コードの実行や修復はしない。"""
    if (error.error_type or '').rsplit('.', 1)[-1] not in {'SyntaxError', 'IndentationError'}:
        return explanation
    message = error.message.lower()
    lines = code.splitlines()
    line = lines[error.line - 1].strip() if error.line and 0 < error.line <= len(lines) else ''
    if not line:
        # 行番号が無い短い入力でも、制御文の候補だけ拾う。
        line = next((text.strip() for text in lines if re.match(r'\s*(?:if|elif|while|for|def|class)\b', text)), '')
    if "expected ':'" in message:
        head = re.match(r'(if|elif|while|for|def|class|try|except|else|finally|with)\b', line)
        label = f'{head[1]} 文の構文エラーです。' if head else '文の末尾にコロンが必要な構文です。'
        return replace(explanation, summary=label, cause='文末のコロン : が不足している可能性があります。該当行と直前の行を確認してください。')
    if ('meant' in message and "'=='" in message) or (re.match(r'(?:if|elif|while)\b', line) and re.search(r'(?<![=!<>:])=(?!=)', line)):
        return replace(explanation, summary='条件式で = による代入を使っている可能性があります。',
                       cause='比較したい場合は == の可能性があります。代入式 := を意図した場合などもあるため、意図を確認してください。')
    if 'never closed' in message:
        return replace(explanation, summary='括弧が閉じられていない可能性があります。', cause='丸括弧・角括弧・波括弧の対応を、表示された行から後ろまで確認してください。')
    if 'unterminated string' in message or 'eol while scanning string' in message:
        return replace(explanation, summary='文字列リテラルが閉じられていない可能性があります。', cause='引用符の種類・対応と、途中の改行やエスケープを確認してください。')
    if 'unexpected indent' in message:
        return replace(explanation, cause='不要な追加インデントがある可能性があります。同じブロック内の空白の数を比較してください。')
    return explanation

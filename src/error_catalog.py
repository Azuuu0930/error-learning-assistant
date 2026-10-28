"""Local, searchable teaching examples. Selecting an example never executes it."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ErrorExample:
    error_type: str
    keywords: str
    error_log: str
    code: str

    @property
    def search_label(self) -> str:
        return f"{self.error_type} · {self.keywords}"


_KEYWORDS = {
    "NameError": "変数・名前・未定義", "SyntaxError": "文法・コロン・括弧",
    "IndentationError": "字下げ・インデント", "TypeError": "型・文字列・数値・引数",
    "ValueError": "値・変換", "IndexError": "リスト・範囲・位置",
    "KeyError": "辞書・キー", "AttributeError": "属性・メソッド",
    "ModuleNotFoundError": "モジュール・インストール", "ImportError": "読み込み・モジュール",
    "FileNotFoundError": "ファイル・パス", "ZeroDivisionError": "計算・ゼロ・割り算",
}
_SAMPLES = json.loads((Path(__file__).resolve().parents[1] / "examples" / "sample_errors.json").read_text(encoding="utf-8"))
_EXTRA = (
    ErrorExample("UnboundLocalError", "変数・ローカル・代入前",
                 'Traceback (most recent call last):\n  File "local.py", line 3, in increase\n    count += 1\nUnboundLocalError: cannot access local variable \'count\' where it is not associated with a value',
                 "count = 0\ndef increase():\n    count += 1\nincrease()"),
    ErrorExample("RecursionError", "再帰・終了条件・呼び出し",
                 'Traceback (most recent call last):\n  File "recursion.py", line 2, in countdown\n    return countdown(number)\nRecursionError: maximum recursion depth exceeded',
                 "def countdown(number):\n    return countdown(number)\ncountdown(3)"),
    ErrorExample("StopIteration", "反復・イテレータ・next・空",
                 'Traceback (most recent call last):\n  File "iteration.py", line 2, in <module>\n    value = next(iterator)\nStopIteration',
                 "iterator = iter([])\nvalue = next(iterator)"),
    ErrorExample("AssertionError", "条件・検証・assert",
                 'Traceback (most recent call last):\n  File "assertion.py", line 2, in <module>\n    assert age >= 18\nAssertionError',
                 "age = 15\nassert age >= 18"),
    ErrorExample("RuntimeError", "実行時・辞書・集合・サイズ変更",
                 'Traceback (most recent call last):\n  File "runtime.py", line 2, in <module>\n    for key in data:\nRuntimeError: dictionary changed size during iteration',
                 'data = {"a": 1, "b": 2}\nfor key in data:\n    del data[key]'),
    ErrorExample("UnicodeDecodeError", "文字コード・文字化け・デコード",
                 'Traceback (most recent call last):\n  File "encoding.py", line 2, in <module>\n    text = raw.decode("utf-8")\nUnicodeDecodeError: \'utf-8\' codec can\'t decode byte 0xff in position 0: invalid start byte',
                 'raw = bytes([255])\ntext = raw.decode("utf-8")'),
)

ERROR_CATALOG = tuple(ErrorExample(item["error_type"], _KEYWORDS[item["error_type"]], item["error_log"], item["code"])
                      for item in _SAMPLES) + _EXTRA
CATALOG_BY_TYPE = {entry.error_type: entry for entry in ERROR_CATALOG}

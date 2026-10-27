# Baseline re-scored with v2 adapter evaluation

Evaluation Dataset: 42 cases

Error Type Accuracy: 100.00% (37/37)
Error/No-Error Accuracy (code only): 38.10% (16/42)
Error/No-Error Accuracy (runtime log + code): 100.00% (42/42)
False Positive Rate: 0.00% (0/5)
AST Diagnosis Accuracy (valid syntax, all requested facts): 27.78% (10/36)
AST Expectation Recall (individual facts): 33.33% (15/45)
Combined Diagnosis Accuracy (log explanations + AST): 42.86% (18/42)
Incorrect Claim Rate (cases with prohibited claims): 0.00% (0/14)
Coverage: 42/42
Strict PASS: 28.57% (12/42)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| beginner | 33.33% (7/21) | 100.00% (21/21) | 42.86% (9/21) | 33.33% (5/15) | 21/21 |
| intermediate | 25.00% (1/4) | 100.00% (4/4) | 25.00% (1/4) | 25.00% (1/4) | 4/4 |
| rare | 0.00% (0/9) | 100.00% (9/9) | 0.00% (0/9) | 0.00% (0/9) | 9/9 |
| adversarial | 50.00% (4/8) | 100.00% (3/3) | 75.00% (6/8) | 50.00% (4/8) | 8/8 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| PY-003 | 文字列と整数の加算 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: str と int の不正な加算 (mixed_addition) |
| PY-004 | inputの戻り値を整数として使用 | コードだけの警告: expected=True, actual=False |
| PY-006 | 辞書に存在しないキー | コードだけの警告: expected=True, actual=False |
| PY-007 | ゼロ除算 | コードだけの警告: expected=True, actual=False |
| PY-008 | 存在しないメソッド | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: str に apend 属性がない (missing_attribute) |
| PY-009 | 存在しないモジュール | コードだけの警告: expected=True, actual=False |
| PY-010 | 存在しない名前をimport | コードだけの警告: expected=True, actual=False |
| PY-011 | 存在しないファイルを開く | コードだけの警告: expected=True, actual=False |
| PY-012 | int変換失敗 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: hello を整数に変換できない (invalid_integer) |
| PY-013 | if文のコロン忘れ | 期待した診断が欠落: if 文の構文エラー (if_syntax) |
| PY-017 | 代入演算子と比較演算子の混同 | 期待した診断が欠落: 条件式で = を使用 (assignment_in_condition) |
| PY-020 | Noneにメソッドを呼び出す | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: result が None (none_binding)<br>期待した診断が欠落: NoneType に upper がない (missing_attribute) |
| PY-021 | 関数の引数不足 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: add は2引数必要 (required_argument_count)<br>期待した診断が欠落: 1引数しか渡していない (supplied_argument_count) |
| PY-022 | 関数へ引数を渡しすぎる | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: hello の定義より多い位置引数 (too_many_arguments) |
| PY-023 | 存在しないキーワード引数 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: hello に username 引数は定義されていない (unknown_keyword) |
| PY-024 | リストと整数の大小比較 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: list と int の大小比較 (mixed_comparison) |
| PY-025 | 無限再帰 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 再帰が終了条件なしで続く可能性 (unbounded_recursion) |
| PY-026 | 空イテレータへのnext | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 空のイテレータに next を呼んでいる (empty_iterator) |
| PY-027 | assert失敗 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: assert 条件が False (false_assertion) |
| PY-028 | 辞書を反復中に変更 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 辞書を走査中にサイズ変更 (dict_iteration_mutation) |
| PY-029 | setを反復中に変更 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: set を走査中にサイズ変更 (set_iteration_mutation) |
| PY-030 | Unicodeデコード失敗 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: UTF-8 として不正なバイト列 (invalid_utf8) |
| PY-031 | bytesとstrの加算 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: bytes と str の混在 (mixed_bytes_string) |
| PY-032 | リスト添字にfloat | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: リストの添字が float (float_index) |
| PY-033 | hash化できないリストを辞書キーに使用 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: list は辞書キーとして使えない (unhashable_list_key) |
| PY-034 | 自作クラスの存在しない属性 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: User に age 属性が定義されていない可能性 (missing_attribute)<br>期待した診断が欠落: name 属性は存在 (present_attribute) |
| PY-036 | builtinsを未定義扱いしない | 期待した診断が欠落: print と len は builtins (builtin_resolution) |
| PY-039 | 分岐次第で未定義になる変数 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: result は一部の経路でしか定義されない (conditional_binding) |
| PY-040 | 空ループ後の未定義変数 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: ループが一度も実行されないと result が未定義 (empty_loop_binding) |
| PY-042 | 例外処理済みのZeroDivisionError | 期待した診断が欠落: ZeroDivisionError は except で処理される (handled_exception) |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| AST解析の問題 | 23 |
| 型推論不足 | 8 |
| 静的解析の限界 | 3 |
| ログparser／説明の問題 | 2 |
| 未対応エラー | 6 |
| 評価器側の限界 | 1 |
| control flow解析不足 | 3 |

Snapshot unchanged: True
Runtime/dataset agreement: 100.00% (42/42)
Unmapped expectations: 0; unmapped prohibited claims: 0

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

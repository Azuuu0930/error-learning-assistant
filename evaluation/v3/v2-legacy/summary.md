# v2-legacy evaluation

Evaluation Dataset: 42 cases

Error Type Accuracy: 100.00% (37/37)
Error/No-Error Accuracy (code only): 76.19% (32/42)
Error/No-Error Accuracy (runtime log + code): 100.00% (42/42)
False Positive Rate: 0.00% (0/5)
AST Diagnosis Accuracy (valid syntax, all requested facts): 66.67% (24/36)
AST Expectation Recall (individual facts): 71.11% (32/45)
Combined Diagnosis Accuracy (log explanations + AST): 88.10% (37/42)
Incorrect Claim Rate (cases with prohibited claims): 0.00% (0/14)
Coverage: 42/42
Strict PASS: 66.67% (28/42)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| beginner | 80.95% (17/21) | 100.00% (21/21) | 85.71% (18/21) | 86.67% (13/15) | 21/21 |
| intermediate | 75.00% (3/4) | 100.00% (4/4) | 75.00% (3/4) | 75.00% (3/4) | 4/4 |
| rare | 22.22% (2/9) | 100.00% (9/9) | 33.33% (3/9) | 22.22% (2/9) | 9/9 |
| adversarial | 75.00% (6/8) | 100.00% (3/3) | 100.00% (8/8) | 75.00% (6/8) | 8/8 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| PY-009 | 存在しないモジュール | コードだけの警告: expected=True, actual=False |
| PY-010 | 存在しない名前をimport | コードだけの警告: expected=True, actual=False |
| PY-011 | 存在しないファイルを開く | コードだけの警告: expected=True, actual=False |
| PY-022 | 関数へ引数を渡しすぎる | 期待した診断が欠落: hello の定義より多い位置引数 (too_many_arguments) |
| PY-025 | 無限再帰 | コードだけの警告: expected=True, actual=False |
| PY-026 | 空イテレータへのnext | コードだけの警告: expected=True, actual=False |
| PY-027 | assert失敗 | コードだけの警告: expected=True, actual=False |
| PY-028 | 辞書を反復中に変更 | コードだけの警告: expected=True, actual=False |
| PY-029 | setを反復中に変更 | コードだけの警告: expected=True, actual=False |
| PY-030 | Unicodeデコード失敗 | コードだけの警告: expected=True, actual=False |
| PY-031 | bytesとstrの加算 | 期待した診断が欠落: bytes と str の混在 (mixed_bytes_string) |
| PY-034 | 自作クラスの存在しない属性 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: User に age 属性が定義されていない可能性 (missing_attribute)<br>期待した診断が欠落: name 属性は存在 (present_attribute) |
| PY-036 | builtinsを未定義扱いしない | 期待した診断が欠落: print と len は builtins (builtin_resolution) |
| PY-042 | 例外処理済みのZeroDivisionError | 期待した診断が欠落: ZeroDivisionError は except で処理される (handled_exception) |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| 静的解析の限界 | 3 |
| AST解析の問題 | 8 |
| 型推論不足 | 2 |
| 評価器側の限界 | 1 |
| control flow解析不足 | 1 |

Snapshot unchanged: False
Runtime/dataset agreement: 100.00% (42/42)
Unmapped expectations: 0; unmapped prohibited claims: 0

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

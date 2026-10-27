# v3-structured evaluation

Evaluation Dataset: 42 cases

Error Type Accuracy: 100.00% (37/37)
Error/No-Error Accuracy (code only): 88.10% (37/42)
Error/No-Error Accuracy (runtime log + code): 100.00% (42/42)
False Positive Rate: 0.00% (0/5)
AST Diagnosis Accuracy (valid syntax, all requested facts): 91.67% (33/36)
AST Expectation Recall (individual facts): 93.33% (42/45)
Combined Diagnosis Accuracy (log explanations + AST): 100.00% (42/42)
Incorrect Claim Rate (cases with prohibited claims): 0.00% (0/14)
Coverage: 42/42
Strict PASS: 88.10% (37/42)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| beginner | 85.71% (18/21) | 100.00% (21/21) | 85.71% (18/21) | 93.33% (14/15) | 21/21 |
| intermediate | 100.00% (4/4) | 100.00% (4/4) | 100.00% (4/4) | 100.00% (4/4) | 4/4 |
| rare | 77.78% (7/9) | 100.00% (9/9) | 77.78% (7/9) | 77.78% (7/9) | 9/9 |
| adversarial | 100.00% (8/8) | 100.00% (3/3) | 100.00% (8/8) | 100.00% (8/8) | 8/8 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| PY-009 | 存在しないモジュール | コードだけの警告: expected=True, actual=False |
| PY-010 | 存在しない名前をimport | コードだけの警告: expected=True, actual=False |
| PY-011 | 存在しないファイルを開く | コードだけの警告: expected=True, actual=False |
| PY-025 | 無限再帰 | コードだけの警告: expected=True, actual=False |
| PY-030 | Unicodeデコード失敗 | コードだけの警告: expected=True, actual=False |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| 静的解析の限界 | 3 |
| AST解析の問題 | 2 |

Snapshot unchanged: False
Runtime/dataset agreement: 100.00% (42/42)
Unmapped expectations: 0; unmapped prohibited claims: 0

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

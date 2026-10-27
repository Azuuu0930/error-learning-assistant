# old-holdout-v2 evaluation

Evaluation Dataset: 20 cases

Error Type Accuracy: 100.00% (10/10)
Error/No-Error Accuracy (code only): 100.00% (20/20)
Error/No-Error Accuracy (runtime log + code): 100.00% (20/20)
False Positive Rate: 0.00% (0/10)
AST Diagnosis Accuracy (valid syntax, all requested facts): 90.00% (9/10)
AST Expectation Recall (individual facts): 90.00% (9/10)
Combined Diagnosis Accuracy (log explanations + AST): 90.91% (10/11)
Incorrect Claim Rate (cases with prohibited claims): 0.00% (0/5)
Coverage: 20/20
Strict PASS: 95.00% (19/20)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| intermediate | 95.00% (19/20) | 100.00% (10/10) | 100.00% (20/20) | 90.00% (9/10) | 20/20 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| H-15 | 例外型タプルでTypeErrorを処理 | 期待した診断が欠落: TypeError は except で処理 (handled_exception) |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| control flow解析不足 | 1 |

Snapshot unchanged: False
Runtime/dataset agreement: 100.00% (20/20)
Unmapped expectations: 0; unmapped prohibited claims: 0

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

# normal-v2 evaluation

Evaluation Dataset: 30 cases

Error Type Accuracy: N/A (0 cases)
Error/No-Error Accuracy (code only): 96.67% (29/30)
Error/No-Error Accuracy (runtime log + code): 96.67% (29/30)
False Positive Rate: 3.33% (1/30)
AST Diagnosis Accuracy (valid syntax, all requested facts): N/A (0 cases)
AST Expectation Recall (individual facts): N/A (0 cases)
Combined Diagnosis Accuracy (log explanations + AST): N/A (0 cases)
Incorrect Claim Rate (cases with prohibited claims): N/A (0 cases)
Coverage: 30/30
Strict PASS: 96.67% (29/30)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| adversarial | 96.67% (29/30) | N/A (0 cases) | 96.67% (29/30) | N/A (0 cases) | 30/30 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| N-09 | 公式例：tryを含む入力ループ | コードだけの警告: expected=False, actual=True<br>ログ併用のError/No-error判定が期待と異なる |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| 誤警告／ログparserの問題 | 1 |
| 誤警告 | 1 |

Snapshot unchanged: False
Runtime/dataset agreement: 100.00% (30/30)
Unmapped expectations: 0; unmapped prohibited claims: 0

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

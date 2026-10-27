# Post-freeze structural holdout original baseline evaluation

Evaluation Dataset: 20 cases

Error Type Accuracy: 100.00% (10/10)
Error/No-Error Accuracy (code only): 55.00% (11/20)
Error/No-Error Accuracy (runtime log + code): 100.00% (20/20)
False Positive Rate: 0.00% (0/10)
AST Diagnosis Accuracy (valid syntax, all requested facts): 10.00% (1/10)
AST Expectation Recall (individual facts): 10.00% (1/10)
Combined Diagnosis Accuracy (log explanations + AST): 36.36% (4/11)
Incorrect Claim Rate (cases with prohibited claims): 0.00% (0/5)
Coverage: 20/20
Strict PASS: 50.00% (10/20)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| intermediate | 50.00% (10/20) | 100.00% (10/10) | 55.00% (11/20) | 10.00% (1/10) | 20/20 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| H-01 | 必須keyword-only引数の省略 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 1引数必要 (required_argument_count) |
| H-02 | 位置引数とkeywordによる同一引数の重複 | コードだけの警告: expected=True, actual=False |
| H-03 | boolキー辞書で別のboolキーを参照 | コードだけの警告: expected=True, actual=False |
| H-04 | 負の位置変数でタプルを参照 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 範囲外 (out_of_range) |
| H-05 | 直接呼び出す関数内部のNone属性参照 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: marker が None (none_binding) |
| H-06 | 両分岐で異なる文字列を代入した後の加算 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 不正な加算 (mixed_addition) |
| H-07 | 関数内の小数添字 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: 添字がfloat (float_index) |
| H-08 | Falseを法とした剰余演算 | コードだけの警告: expected=True, actual=False |
| H-09 | 二つの条件分岐を越えた未束縛候補 | コードだけの警告: expected=True, actual=False<br>期待した診断が欠落: token は一部の経路で未定義 (conditional_binding) |
| H-15 | 例外型タプルでTypeErrorを処理 | 期待した診断が欠落: TypeError は except で処理 (handled_exception) |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| AST解析の問題 | 9 |
| 型推論不足 | 3 |
| control flow解析不足 | 2 |

Snapshot unchanged: True
Runtime/dataset agreement: 100.00% (20/20)
Unmapped expectations: 0; unmapped prohibited claims: 0

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

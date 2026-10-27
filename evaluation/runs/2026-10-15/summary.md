# Baseline evaluation

Evaluation Dataset: 42 cases

Error Type Accuracy: 0.00% (0/37)
Error/No-Error Accuracy (code only): 0.00% (0/42)
Error/No-Error Accuracy (runtime log + code): 0.00% (0/42)
False Positive Rate: 0.00% (0/5)
AST Diagnosis Accuracy (valid syntax, all requested facts): 0.00% (0/42)
AST Expectation Recall (individual facts): 0.00% (0/53)
Combined Diagnosis Accuracy (log explanations + AST): 0.00% (0/42)
Incorrect Claim Rate (cases with prohibited claims): 0.00% (0/14)
Coverage: 0/42
Strict PASS: 0.00% (0/42)

Error Type Accuracyは実測ログから例外名を抽出する能力。コードだけから例外名を予測した値ではありません。
ASTの分母は構文が有効でshould_detectを持つ全ケース。現在未対応の型・制御フロー・珍しいエラーも除外していません。
PASSはログ・静的警告・すべての診断期待・禁止断定を満たす厳しい複合条件。正常でも明示的な説明が不足するとFAILになります。
禁止断定の自動規則は完全な意味理解ではありません。目視監査はaudit.mdに別記します。

| Difficulty | Strict PASS | Error type | Code only | AST diagnosis | Coverage |
|---|---:|---:|---:|---:|---:|
| beginner | 0.00% (0/21) | 0.00% (0/21) | 0.00% (0/21) | 0.00% (0/21) | 0/21 |
| intermediate | 0.00% (0/4) | 0.00% (0/4) | 0.00% (0/4) | 0.00% (0/4) | 0/4 |
| rare | 0.00% (0/9) | 0.00% (0/9) | 0.00% (0/9) | 0.00% (0/9) | 0/9 |
| adversarial | 0.00% (0/8) | 0.00% (0/3) | 0.00% (0/8) | 0.00% (0/8) | 0/8 |

## FAIL cases

| ID | Title | Failure reasons |
|---|---|---|
| PY-001 | 変数名のタイプミス | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-ab49486l' |
| PY-002 | 定義前に変数を使用 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-ut1g6g9c' |
| PY-003 | 文字列と整数の加算 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-og2v3rvi' |
| PY-004 | inputの戻り値を整数として使用 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-hj2dex7o' |
| PY-005 | リストの範囲外アクセス | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-eg0v9mr_' |
| PY-006 | 辞書に存在しないキー | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-erq_fcwz' |
| PY-007 | ゼロ除算 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-u_opokfq' |
| PY-008 | 存在しないメソッド | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-oizxvr9_' |
| PY-009 | 存在しないモジュール | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-oge70ctk' |
| PY-010 | 存在しない名前をimport | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-8jekyetw' |
| PY-011 | 存在しないファイルを開く | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-sj4str0y' |
| PY-012 | int変換失敗 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-ydvem4u7' |
| PY-013 | if文のコロン忘れ | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-_p8km2oc' |
| PY-014 | 閉じ括弧忘れ | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-tc_uc6zl' |
| PY-015 | インデント忘れ | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-3ql6xzsl' |
| PY-016 | 予期しない深いインデント | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-5iktp4st' |
| PY-017 | 代入演算子と比較演算子の混同 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-vh0g77k7' |
| PY-018 | 文字列の閉じ忘れ | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-k0lr0b4f' |
| PY-019 | ローカル変数の参照前代入 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-mqm95_h6' |
| PY-020 | Noneにメソッドを呼び出す | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-23n5ecr8' |
| PY-021 | 関数の引数不足 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-6fiws1o0' |
| PY-022 | 関数へ引数を渡しすぎる | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-tiwq95o3' |
| PY-023 | 存在しないキーワード引数 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-v9z_hv4z' |
| PY-024 | リストと整数の大小比較 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-rx86ba41' |
| PY-025 | 無限再帰 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-ag9a7cz4' |
| PY-026 | 空イテレータへのnext | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-148m0m0w' |
| PY-027 | assert失敗 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-3topwffy' |
| PY-028 | 辞書を反復中に変更 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-07h4dzrn' |
| PY-029 | setを反復中に変更 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-j3l0f6th' |
| PY-030 | Unicodeデコード失敗 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-y9bw8zh2' |
| PY-031 | bytesとstrの加算 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-8i3bjwzb' |
| PY-032 | リスト添字にfloat | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-0r835o85' |
| PY-033 | hash化できないリストを辞書キーに使用 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-8zepbai1' |
| PY-034 | 自作クラスの存在しない属性 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-3mct0as8' |
| PY-035 | 似た変数名が複数存在 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-pt2_caz0' |
| PY-036 | builtinsを未定義扱いしない | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-_2galrnu' |
| PY-037 | import済みモジュールを未定義扱いしない | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-44t6sxms' |
| PY-038 | from import済み名称を未定義扱いしない | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-6de6sz2g' |
| PY-039 | 分岐次第で未定義になる変数 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-ohx7ss1r' |
| PY-040 | 空ループ後の未定義変数 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-iintd40n' |
| PY-041 | 関数スコープとグローバルの同名変数 | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-4jv44rrg' |
| PY-042 | 例外処理済みのZeroDivisionError | Evaluator crash: [WinError 5] アクセスが拒否されました。: '<local-path>}\\AC\\Temp\\python-error-eval-z_50case' |

## Failure classification (overlapping)

| Category | Cases |
|---|---:|
| 評価器側の限界 | 42 |

Snapshot unchanged: True
Runtime/dataset agreement: 0.00% (0/42)
Unmapped expectations: 53; unmapped prohibited claims: 17

このスコアは本データセット・Python環境・入力fixtureでの実測です。将来の入力への保証ではありません。

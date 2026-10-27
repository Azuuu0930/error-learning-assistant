# 診断改善の実測比較

入力データ、分母、意味照合関数を固定して測定しました。旧Versionも同じ評価器で再実行し、元の指標・難易度別結果と完全一致することを確認しています。

## 42ケース

| 指標 | Before | After |
|---|---:|---:|
| Error Type Accuracy | 100.00% (37/37) | 100.00% (37/37) |
| Error/No-Error（コードのみ） | 38.10% (16/42) | 76.19% (32/42) |
| Error/No-Error（ログ＋コード） | 100.00% (42/42) | 100.00% (42/42) |
| False Positive Rate | 0.00% (0/5) | 0.00% (0/5) |
| AST Diagnosis Accuracy | 27.78% (10/36) | 66.67% (24/36) |
| ログ説明＋AST診断達成率 | 42.86% (18/42) | 88.10% (37/42) |
| Incorrect Claim Rate | 0.00% (0/14) | 0.00% (0/14) |
| Coverage | 100.00% (42/42) | 100.00% (42/42) |
| Strict PASS | 28.57% (12/42) | 66.67% (28/42) |

コードだけの警告は解析APIの代理指標です。UIは引き続きエラーログ必須です。ASTの分母36は構文が有効で診断期待を持つケース、Combinedの分母42は全ケースです。

| 難易度 | Before Strict PASS | After Strict PASS |
|---|---:|---:|
| beginner | 7/21 | 17/21 |
| intermediate | 1/4 | 3/4 |
| rare | 0/9 | 2/9 |
| adversarial | 4/8 | 6/8 |

## ケースの変化

- Strict improved: 16件 — PY-003, PY-004, PY-006, PY-007, PY-008, PY-012, PY-013, PY-017, PY-020, PY-021, PY-023, PY-024, PY-032, PY-033, PY-039, PY-040
- Strict regressed: 0件 — なし
- Strict unchanged: 26件 — PY-001, PY-002, PY-005, PY-009, PY-010, PY-011, PY-014, PY-015, PY-016, PY-018, PY-019, PY-022, PY-025, PY-026, PY-027, PY-028, PY-029, PY-030, PY-031, PY-034, PY-035, PY-036, PY-037, PY-038, PY-041, PY-042

Strict PASSの変化がないケースにも部分的な改善があります。下記は例外判定・警告判定・AST期待一致数・Combined期待一致数・禁止断定数を軸にした比較です。

- 診断 improved: 24件 — PY-003, PY-004, PY-006, PY-007, PY-008, PY-012, PY-013, PY-017, PY-020, PY-021, PY-022, PY-023, PY-024, PY-025, PY-026, PY-027, PY-028, PY-029, PY-030, PY-031, PY-032, PY-033, PY-039, PY-040
- 診断 regressed: 0件 — なし
- 診断 mixed: 0件 — なし
- 診断 unchanged: 18件 — PY-001, PY-002, PY-005, PY-009, PY-010, PY-011, PY-014, PY-015, PY-016, PY-018, PY-019, PY-034, PY-035, PY-036, PY-037, PY-038, PY-041, PY-042

## 改善後もStrict FAILとなるケース

| ID | タイトル | 失敗理由 |
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
| PY-034 | 自作クラスの存在しない属性 | コードだけの警告: expected=True, actual=False / 期待した診断が欠落: User に age 属性が定義されていない可能性 (missing_attribute) / 期待した診断が欠落: name 属性は存在 (present_attribute) |
| PY-036 | builtinsを未定義扱いしない | 期待した診断が欠落: print と len は builtins (builtin_resolution) |
| PY-042 | 例外処理済みのZeroDivisionError | 期待した診断が欠落: ZeroDivisionError は except で処理される (handled_exception) |

## 実装固定後の新規holdout 20ケース

実装固定: `2026-10-15T07:24:39.062743+00:00`。holdout作成: `2026-10-15T07:45:33.017454+00:00`。
エラー10件・正常10件を新規作成しました。両分岐の同型合流、keyword-only、引数重複、負のタプル添字、boolのキー・添字、関数を経由した変更、入れ子の例外処理、generator式などを含みます。
開発時のテストには使用せず、評価後のアプリ・採点関数・期待値の修正は行っていません。作者が作る小規模な確認セットであり、外部の盲検評価ではありません。

| 指標 | Before | After |
|---|---:|---:|
| Error Type Accuracy | 100.00% (10/10) | 100.00% (10/10) |
| Error/No-Error（コードのみ） | 55.00% (11/20) | 100.00% (20/20) |
| Error/No-Error（ログ＋コード） | 100.00% (20/20) | 100.00% (20/20) |
| False Positive Rate | 0.00% (0/10) | 0.00% (0/10) |
| AST Diagnosis Accuracy | 10.00% (1/10) | 90.00% (9/10) |
| ログ説明＋AST診断達成率 | 36.36% (4/11) | 90.91% (10/11) |
| Incorrect Claim Rate | 0.00% (0/5) | 0.00% (0/5) |
| Coverage | 100.00% (20/20) | 100.00% (20/20) |
| Strict PASS | 50.00% (10/20) | 95.00% (19/20) |

ASTは構文有効かつshould_detectを持つ10件、Combinedは構文エラーを含む11件が分母です。残り9件も警告判定・Strict PASS・Coverageの分母に含めます。引数重複の専用意味分類が既存評価器にないH-02は、警告判定のみで評価しています。

H-15は例外処理を示す実際のnoteがありますが、固定規則の英語識別子境界が日本語との隣接を拾えずFAILです。採点を上書きしていません。正常10件はすべて無警告です。

## 再現性・保存物

- 361 pytest成功（アプリ319、評価器42）。元のアプリ208テストの6ファイルはバイト単位で未変更。新規119実行例（アプリ111、評価器8）。
- 元の評価器34件は旧Version前提の4箇所を更新。変更前は同梱の旧Versionに保存。意味照合関数は同一で、新しい診断kindの警告分類だけを拡張。
- 42件の原本JSONは未変更。元の結果はresults.json、再測定はbaseline-rescored/とafter/、holdoutはholdout/before/とholdout/after/に保存。
- 固定後の初回42件実行ではPY-035のコード実行プロセスが5秒でtimeoutし、例外種類36/37・Strict PASS27/42となった。アプリは42/42応答。after-transient-timeout/に全結果を保存し、同じコード・5秒設定で全42件を再実行。最終実行は42/42の実行結果を再現。過渡的timeoutの原因自体は未特定。
- comparison.json / comparison.csvは全62件のBefore/After・変化区分・失敗理由を保存。評価時のソースhashと固定manifestも保存。
- 禁止断定の機械照合は日本語規則であり完全ではない。after/claim_review_packet.mdとholdout/after/claim_review_packet.mdを全文監査用に保存。

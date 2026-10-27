# V3：診断の根拠と学習体験の改善

旧版は前回納品したv2です。元の42件・期待・分母・Strict PASS条件を維持し、従来採点と構造化採点を区別しました。

## 構造化採点で同じ42件を比較

| 指標 | Before | After |
|---|---:|---:|
| Error Type Accuracy | 100.00% (37/37) | 100.00% (37/37) |
| Error/No-Error（コードのみ） | 76.19% (32/42) | 88.10% (37/42) |
| Error/No-Error（ログ＋コード） | 100.00% (42/42) | 100.00% (42/42) |
| False Positive Rate | 0.00% (0/5) | 0.00% (0/5) |
| AST Diagnosis Accuracy | 66.67% (24/36) | 91.67% (33/36) |
| ログ説明＋AST診断達成率 | 88.10% (37/42) | 100.00% (42/42) |
| Incorrect Claim Rate | 0.00% (0/14) | 0.00% (0/14) |
| Coverage | 100.00% (42/42) | 100.00% (42/42) |
| Strict PASS | 66.67% (28/42) | 88.10% (37/42) |

構造化採点はアプリのdetails/factsを使います。旧版も同じ新採点器で測定しています。元コードやtracebackの文章を新しい診断として加点せず、対象・型・引数数が一致しない根拠は拒否します。

## 従来採点をそのまま再現した場合

| 指標 | Before | After |
|---|---:|---:|
| Error Type Accuracy | 100.00% (37/37) | 100.00% (37/37) |
| Error/No-Error（コードのみ） | 76.19% (32/42) | 78.57% (33/42) |
| Error/No-Error（ログ＋コード） | 100.00% (42/42) | 100.00% (42/42) |
| False Positive Rate | 0.00% (0/5) | 0.00% (0/5) |
| AST Diagnosis Accuracy | 66.67% (24/36) | 69.44% (25/36) |
| ログ説明＋AST診断達成率 | 88.10% (37/42) | 88.10% (37/42) |
| Incorrect Claim Rate | 0.00% (0/14) | 0.00% (0/14) |
| Coverage | 100.00% (42/42) | 100.00% (42/42) |
| Strict PASS | 66.67% (28/42) | 66.67% (28/42) |

従来のscoring.pyはバイト単位で未変更です。この完全再現モードでは新しいwarning kindも認識しません。
新採点との差は、診断内容の追加に加え、既にある内容を新しい根拠形式で確実に拾える効果と新kindの認識を含みます。新採点の増加分をすべて新しい原因推論の成果とは説明しません。

## 難易度別Strict PASS（構造化採点）

| 難易度 | v2 | v3 |
|---|---:|---:|
| beginner | 17/21 | 18/21 |
| intermediate | 3/4 | 4/4 |
| rare | 2/9 | 7/9 |
| adversarial | 6/8 | 8/8 |

## ケースの変化（構造化採点）

- Strict improved: 9件 — PY-022, PY-026, PY-027, PY-028, PY-029, PY-031, PY-034, PY-036, PY-042
- Strict regressed: 0件 — なし
- Strict unchanged: 33件 — PY-001, PY-002, PY-003, PY-004, PY-005, PY-006, PY-007, PY-008, PY-009, PY-010, PY-011, PY-012, PY-013, PY-014, PY-015, PY-016, PY-017, PY-018, PY-019, PY-020, PY-021, PY-023, PY-024, PY-025, PY-030, PY-032, PY-033, PY-035, PY-037, PY-038, PY-039, PY-040, PY-041
- 診断 improved: 9件 — PY-022, PY-026, PY-027, PY-028, PY-029, PY-031, PY-034, PY-036, PY-042
- 診断 regressed: 0件 — なし
- 診断 mixed: 0件 — なし
- 診断 unchanged: 33件 — PY-001, PY-002, PY-003, PY-004, PY-005, PY-006, PY-007, PY-008, PY-009, PY-010, PY-011, PY-012, PY-013, PY-014, PY-015, PY-016, PY-017, PY-018, PY-019, PY-020, PY-021, PY-023, PY-024, PY-025, PY-030, PY-032, PY-033, PY-035, PY-037, PY-038, PY-039, PY-040, PY-041

## 残るFAIL

| ID | タイトル | 失敗理由 |
|---|---|---|
| PY-009 | 存在しないモジュール | コードだけの警告: expected=True, actual=False |
| PY-010 | 存在しない名前をimport | コードだけの警告: expected=True, actual=False |
| PY-011 | 存在しないファイルを開く | コードだけの警告: expected=True, actual=False |
| PY-025 | 無限再帰 | コードだけの警告: expected=True, actual=False |
| PY-030 | Unicodeデコード失敗 | コードだけの警告: expected=True, actual=False |

import先・ファイルの実在（3件）は環境依存で断定しません。再帰の非停止・UTF-8復号（2件）はコードのみの警告を未実装です。ログ説明では全診断期待を満たしています。

## 既存holdout20件の再確認

| 指標 | Before | After |
|---|---:|---:|
| Error Type Accuracy | 100.00% (10/10) | 100.00% (10/10) |
| Error/No-Error（コードのみ） | 100.00% (20/20) | 100.00% (20/20) |
| Error/No-Error（ログ＋コード） | 100.00% (20/20) | 100.00% (20/20) |
| False Positive Rate | 0.00% (0/10) | 0.00% (0/10) |
| AST Diagnosis Accuracy | 90.00% (9/10) | 100.00% (10/10) |
| ログ説明＋AST診断達成率 | 90.91% (10/11) | 100.00% (11/11) |
| Incorrect Claim Rate | 0.00% (0/5) | 0.00% (0/5) |
| Coverage | 100.00% (20/20) | 100.00% (20/20) |
| Strict PASS | 95.00% (19/20) | 100.00% (20/20) |

この20件は前回から既知の回帰セットです。今回新たな未知データとしては扱いません。

## 実装固定後の新しい正常コード30件

| 指標 | Before | After |
|---|---:|---:|
| Error Type Accuracy | N/A (0/0) | N/A (0/0) |
| Error/No-Error（コードのみ） | 96.67% (29/30) | 96.67% (29/30) |
| Error/No-Error（ログ＋コード） | 96.67% (29/30) | 96.67% (29/30) |
| False Positive Rate | 3.33% (1/30) | 3.33% (1/30) |
| AST Diagnosis Accuracy | N/A (0/0) | N/A (0/0) |
| ログ説明＋AST診断達成率 | N/A (0/0) | N/A (0/0) |
| Incorrect Claim Rate | N/A (0/0) | N/A (0/0) |
| Coverage | 100.00% (30/30) | 100.00% (30/30) |
| Strict PASS | 96.67% (29/30) | 96.67% (29/30) |

公式Pythonチュートリアルから実行可能な形へ改変した10件と、新規作成20件。出典URLと変更内容はnormal-corpus.jsonに各件記録しました。外部の盲検ベンチマークではありません。
全件が正常終了することを同じ分離実行・固定stdin20・5秒timeoutで確認しました。警告有無を測る目的でshould_detectを付けていないため、AST診断とCombined診断は0/0=N/Aです。
N-09（tryの中でinput/intし、成功時だけbreakするwhile True）の後のxに、両版ともpossibly_unboundを出します。ループを抜ける経路と代入の関係を十分に理解できない既存のcontrol-flowの制限です。誤警告1/30を隠さず保存し、固定後の評価をアプリ修正には使っていません。

## テスト・レビュー・固定

- 496 passed in 20.69s。アプリ422、評価器74。前回361件を維持し、今回135件（診断99、UI4、採点32）を追加。元のアプリテストはバイト単位で未変更。
- 独立レビューの15プローブを通過。異なる型・対象への誤加点を3件のRED→GREENテストで修正。残るP1/P2指摘なし。
- 実装固定: 2026-10-27T02:49:18.349202+00:00。正常コード作成: 2026-10-27T02:51:59.693313+00:00。34個の固定ファイルを照合し、評価後のアプリ・採点変更なし。
- 前回v2のlegacy全指標を今回の評価器で完全再現。全実行のJSON/CSV・console.log・hashを保存。クラッシュ・timeout・実行拒否は分母から除外しない。
- ここでのError/No-ErrorはAPIの警告代理指標。UIは引き続きログ入力必須であり、正常性を証明する機能ではない。

## 出典

- [Python公式：Data Structures](https://docs.python.org/3.12/tutorial/datastructures.html)
- [Python公式：More Control Flow Tools](https://docs.python.org/3.12/tutorial/controlflow.html)
- [Python公式：Errors and Exceptions](https://docs.python.org/3.12/tutorial/errors.html)

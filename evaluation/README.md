# ベースライン・改善Versionの評価方法

現在の42ケースv3評価結果は `v3/REPORT.md`、固定記録と各ケースのJSON/CSVは `v3/` に保存しています。再計算は `python evaluation/v3/report.py` で行います。v3の正常コード評価用コーパスは `v3/normal-corpus.json` です。

新しい構造化採点器は `evaluation/structured_scoring.py` で、再実行時は `python evaluation/evaluate.py --scoring structured ...` を明示します。既定のlegacy採点は過去の再現用です。従来比較と採点定義の詳細は下記に記載したv2手順です。

旧AST MVPを20ファイルのSHA-256で固定したベースラインを保存しています。
元の結果は `results.json` / `summary.md` / `REPORT.md`、ソース・元208+34テストは同梱の兄弟フォルダ `../error-learning-assistant-baseline` にあります。
改善後の結果は `after/`、同じ評価器での旧Version再測定は `baseline-rescored/`、比較は [COMPARISON.md](COMPARISON.md) です。
旧Versionの指標と難易度別結果は元の結果と完全一致しました。
通常の実行はベースラインのhashが違うと拒否し、改善Versionを測る場合だけ `--allow-version-change` を明示します。どちらも実行の前後でソースが変わっていないか照合します。

## 実行

プロジェクトのルートから実行します。アプリと評価器の追加依存関係はありません。標準ライブラリのみで測定できます。

```powershell
python evaluation/evaluate.py --execute-reviewed --allow-version-change --output evaluation/new-after
python evaluation/evaluate.py --execute-reviewed --project ../error-learning-assistant-baseline --output evaluation/new-before
python evaluation/evaluate.py --execute-reviewed --allow-version-change --dataset evaluation/holdout/dataset.json --output evaluation/new-holdout
python -m pytest tests evaluation/tests -q
python evaluation/compare.py
```

この環境で利用したPythonは `../../work/.venv/Scripts/python.exe`、Python 3.12.14です。実行コードは内容を確認済みの教育用スニペットに限定してください。`--execute-reviewed` はその確認を明示するオプションです。承認待ちの処理やアプリ側のコード実行機能を追加するものではありません。

## データセット

添付JSONの42ケースをそのまま複製して使います。JSONLは指定場所に見つからなかったため、JSONの各caseから損失なく生成しました。JSON/JSONLの両形式を読み込めます。

- expected.execution: error 37件、no_error 5件。
- beginner 21件、intermediate 4件、rare 9件、adversarial 8件。
- should_detect: 53項目。構文が有効な36件には45項目。
- should_not_claim: 14ケースに17項目。
- should_warnは、この原本ではanalysis_expectationsではなくexpected内にあります。両方の形式を受け付け、矛盾があれば拒否します。
- primary_categoryとpreferred_confidenceは、この原本にはありません。期待値を作って採点していません。

## 実行ログの取得と安全性

各caseは一時フォルダ内の独立したPythonプロセスで実行します。`-I -S -X utf8` を使用し、ユーザーsite/PYTHONPATHやsite-packagesを利用せず、環境変数も必要なWindows項目だけ渡します。stdinは全ケース共通の `20` を16行渡します。input()のケースをEOFErrorに変えないための固定fixtureです。

実行は既定5秒、アプリ解析は別プロセスで既定10秒。CPUで回り続けるコードはkillし、次のcaseに進みます。stdout/stderrはファイルへ流し、出力の上限を監視します。ネットワーク・プロセス起動・動的コード生成・特殊属性・任意モジュールのimportは事前ポリシーで拒否します。存在するimport対象はmathのみ許可し、存在しない単純なモジュール名は通常のModuleNotFoundErrorを取得できます。openは一時フォルダ内の単純なファイル名の読取のみ許可します。

subprocess、タイムアウト、ASTの許可リストは完全なOSセキュリティsandboxではありません。Windowsで厳密なメモリ上限も設けていません。未確認の悪意あるコードを安全に実行する用途には対応しません。今回の42件は内容を確認して実行し、全件が期待する実行結果と一致しました。アプリは引き続き入力コードを実行しません。

アプリへの入力は、未変更のcodeと実測stderrだけです。expected.exception_typeから偽ログを生成しません。実行結果とexpectedの一致は、アプリparserとは独立にCPythonの末尾の例外行と終了コードで検証します。一時ファイルのパスはログ中で `<evaluation>/snippet.py` に置換して保存します。

## 指標の定義

| 指標 | 判定 | 分母 |
|---|---|---|
| Error Type Accuracy | 実測stderrをanalyze_error()へ渡し、返った例外名がexpectedと一致 | エラーの37ケース。実行の再現失敗・クラッシュも不正解 |
| Error/No-Error (code only) | analyze_code(code)の問題finding、または具体的なSyntaxErrorの解析不可通知を警告として集計 | 全42ケース |
| Error/No-Error (runtime log + code) | parserの例外名またはASTの問題findingがあるか | 全42ケース |
| False Positive Rate | no_errorでコードだけの警告が出たケース | 正常5ケース。解析失敗数も別記 |
| AST Diagnosis Accuracy | CodeAnalysisの実際のfindings・定義/使用スコープ・import情報から、should_detectをすべて満たしたか | 構文有効で期待を持つ36ケース |
| AST Expectation Recall | ASTで個々のshould_detectを満たしたか | 同じ36ケースの45項目 |
| Combined Diagnosis Accuracy | ASTの事実に、説明・確認ポイント・3段階のヒントを加えて、すべてのshould_detectを満たしたか | 全42ケース |
| Incorrect Claim Rate | should_not_claimへの違反が1つ以上あるケース | 指定のある14ケース。17項目を照合 |
| Coverage | analyze_error()とanalyze_code()が正常に戻ったか | 全42ケース。AST unavailableはクラッシュに数えない |
| Strict PASS | 実行再現、例外名、静的/ログ警告、全診断期待、禁止断定をすべて満たしたか | 全42ケース |

現行UIはエラーログ必須です。正常コードの空ログ入力や、コードだけの事前警告はUI操作でなく解析API・AST部品から測っています。Error/No-Errorは警告有無の代理指標であり、現在のアプリが正常動作を証明したり、明示的な「No Error」を出したりする能力ではありません。ログ併用の100%は、実際に発生した例外を読む能力です。

ASTの36ケースには、現在未対応の型・制御フロー・珍しいエラーも含めます。範囲を現在の得意機能だけに絞りません。除外する構文エラー6件も、全件のCoverage・警告判定・Combined Diagnosisと個別結果に残します。

構造化されたimport情報・scope情報がAPIにあれば事実として評価します。これらすべてが現在のUIに文章で表示されているわけではありません。ASTスコアをUIの説明品質と同一視しないでください。

## 意味的な採点

scoring.pyで、期待文を「未定義」「類似候補」「参照順序」「import」「型付きの属性不足」「範囲外」「引数」「制御フロー」などの一般的な概念へ変換します。case ID、タイトル、コード全体の一致を採点に使いません。各判定は概念名と、実際の返却値の根拠をresults.jsonに残します。

- 未定義・類似名はkind/target/related_names、参照順序はfindingとdefinitionの行・scopeを比較します。
- importはmodule/imported_name/bound_nameが期待対象を含むか確認します。
- 範囲外アクセスは対象、要素数、位置の構造化結果を比較します。
- 型付き属性不足は、その型と属性について「ない」と説明している必要があります。attribute_accessの場所だけでは加点しません。
- 一般的な候補列挙、未使用の修正例、元のログやコードがあるだけでは、特定の原因診断として加点しません。
- builtinsを正しく無警告にすることと、builtinsとして解決したと明示することを別に評価します。
- 定義一覧に名前があることを「すべての実行経路で必ず定義済み」と解釈しません。

未対応の期待文はunmappedにして、不正解と評価器側の制限に記録します。今回の42件では検出53項目・禁止17項目のunmappedは0です。これは日本語の規則照合であり、任意の言い換え・複雑な否定の完全な意味理解ではありません。禁止断定の全文監査資料は旧版がclaim_review_packet.md、改善後がafter/claim_review_packet.mdです。固定規則が日本語と英語名の境界や言い換えを拾えないケースも、目視でPASSに上書きしていません。

新規34テストでは、ID/タイトルの変更でスコアが変わらないこと、期待の未知形式、属性の場所を型推論へ過大評価しないこと、異なるscopeの定義を結び付けないこと、引数の数の一致、断定と候補の区別、正常名への誤警告、実行/解析タイムアウト、出力上限、危険な呼び出しの拒否、JSONL入力、クラッシュ時の分母を確認します。

改善時に元34件のうち4箇所の旧Version前提を更新しました。元のテストは旧Version側に保存し、採点関数を旧版とAST比較するテスト等8件を追加しています。
意味照合関数・分母・PASS条件は変更せず、新しい8種類の問題findingをACTIONABLEへ加えました。
正常に返った説明文に合わせて正規表現を広げる変更はしていません。

## holdoutの手順

アプリと評価器の実装・テストを361件成功させ、implementation_freeze.jsonにhashと時刻を保存してから、holdout/dataset.jsonの20件を作成しました。
エラー10件・正常10件で、単なる変数名置換ではなく構造を変更しています。新規コードは内容を確認し、同じ分離実行ポリシー・stdin・timeoutで測定しました。
holdout評価後にアプリ、採点関数、期待値を調整していません。holdout/before/とholdout/after/に両Versionの結果があります。
should_detectのある11件（AST有効10件）の診断達成率と、全20件の警告・Strict PASSを区別してください。holdoutは作者による小規模な確認セットで、外部の盲検評価ではありません。

## 保存ファイル

- results.json: メタデータ、Python環境、アプリ/評価器ハッシュ、全指標、難易度別結果、全caseの実測ログ・返却値・根拠・失敗理由。
- results.csv: Excelで開けるUTF-8 BOM形式。ID・タイトル・期待/実際の例外・警告・PASS/FAIL・診断件数・失敗理由。
- summary.md: 実測値だけを使ったREADME用サマリーとFAIL一覧。再実行で生成。
- REPORT.md: 現状の失敗分析、改善案TOP5。
- audit.md / claim_review_packet.md: 禁止断定と評価上の制限の監査。
- baseline_manifest.json: 未変更アプリ20ファイルと元JSONのSHA-256。
- implementation_freeze.json: 改善実装・採点・テストのholdout作成前の固定記録。
- comparison.json / comparison.csv / COMPARISON.md: 全62件のBefore/Afterと変化区分。
- IMPROVEMENTS.md: 実装の範囲、残る失敗の再分類、改善候補TOP5。
- after-transient-timeout/: 固定後に1件のコード実行プロセスが5秒timeoutした測定。実装・設定を変えず全42件を再実行した結果はafter/に保存。

診断のprecision、ヒント品質や信頼度の校正はこの測定では評価していません。データセットのrecommended_metricsのうち、定義と正解ラベルが不足するものを実測値として捏造していません。将来の改善は未知の変数名、型、分岐、import、入力値でも成立する一般規則として実装し、独立した追加データで検証する必要があります。

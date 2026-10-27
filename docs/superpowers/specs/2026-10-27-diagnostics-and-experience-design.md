# 診断の根拠と学習画面の改善

## 目的・合意
ユーザーは前回の改善候補の実装と、animation・skeleton・autocompleteを用いた視覚と操作感の改善を依頼した。色味は「お任せ（濃紺＋青緑）」を選択。既存Python/Streamlitを継続し、具体的な配置・動き・実装方式は担当者が決める。

## 選択した方式
既存Streamlitにデザイン層を追加する。React等への全面移行は既存テストと学習フローの再実装が必要で、今回の改善目的には過大。別の静的デモだけを作る方式では実際の診断機能とつながらないため採用しない。

## 診断の範囲
- findingへJSON化可能なdetails、CodeAnalysisへ情報用factsを追加する。従来のkind/message/notesは維持。
- 明白なassert False、既知の空イテレータへのnext、直線的な辞書/集合のサイズ変更を補助診断。catch・短絡・breakで誤警告しないことを優先。
- 副作用がないと確認できる小さな関数の引数/戻り値と、継承・decorator・動的属性のない単純クラスの属性を限定して扱う。不明な場合は従来の保守的な解析へ戻る。
- 従来採点関数は保存。新しい構造化採点を別モジュールにし、両方式を保存してBefore/Afterを比較する。
- 元42件と既存holdoutに加え、実装固定後に新しい正常コード評価を行う。外部公開例の出典・改変を明記する。

## 画面
- wideの2列ワークスペース：左にログ/任意コード/モード/実行、右に結果または空状態。狭い画面は1列へ。
- 濃紺の面、青緑アクセント、読みやすい余白・コントラスト。小さな色付きラベル、概要カード、コード欄、段階ヒントの階層を統一。
- 18種類の例外カタログを英語名/日本語で検索できるネイティブcombobox。選択で例を入力し、自動実行はしない。既存12サンプルと旧widget keyは維持する。
- 解析中は実際の処理期間だけskeleton/shimmerと状態説明を表示し、完了/失敗時に除去。表示のための待ち時間を追加しない。
- heroの控えめな光、カードの出現、hover/focus、結果とヒントの移行、進行表示にanimationを使う。動きを減らす設定とprefers-reduced-motionを尊重。
- ヒント3まで詳細や修正例を先出ししない。ユーザー入力HTMLはescapeする。キーボード操作・ラベル・focusを保つ。

## 非目標・制約
コードを実行する機能、クラウド送信、ログ保存、認証、全面的な型推論、完全CFGは追加しない。前回のZIP・ベースラインは変更しない。入力上限10万文字、AST上限2万ノード、信頼度の方針を維持する。

## インターフェース
CodeFinding.details: dict（JSON primitiveのみ）。CodeFact(kind, line, subject, details)。CodeAnalysis.facts: tuple[CodeFact,...]。
detailsは exception_type, receiver_type, attribute, operator, left_type, right_type, argument_issue, required_count, supplied_count, maximum_positional, defined_attributes, class_name 等、診断に必要な情報だけ。
factsは builtin_reference（subject=名前）、handled_exception（subject=例外名）、defined_attribute（subject=属性名、details.class_name）等の非警告情報。

## 検証
既存361実行ケース、新規の警告/無警告テスト、構造化採点の捏造防止テスト、検索/入力失効/例外時のloading解除のAppTest。実ブラウザでdesktop/mobile、検索候補、段階ヒント、loading、reduced motionを確認。前回実装はerror-learning-assistant-v2に元ZIPから保存済み。

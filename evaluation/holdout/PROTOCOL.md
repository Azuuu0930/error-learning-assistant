# 固定後に作成した20ケース

実装固定時刻・hashは ../implementation_freeze.json、作成時刻はdataset.jsonに保存しています。
実装と採点を固定してから、エラー10件・正常10件を初めて記述しました。
各ケースのstructural_rationaleに、単純な変数名置換と異なる構造を記録しています。
開発時のpytestや修正に使用していません。評価結果を見てアプリ、採点関数、期待値を修正していません。

同じevaluate.py、実行ポリシー、5秒のコード実行timeout、10秒の解析timeout、固定stdinで、旧Versionと改善Versionを比較しました。
before/とafter/のresults.json・results.csvに期待・実測・PASS/FAIL・理由を保存しています。

should_detectを持つのは11件、そのうちAST生成可能な10件がAST診断指標の分母です。
should_detectのない9件も、警告判定・Strict PASS・Coverageではすべて分母に含めています。
H-02の引数重複は既存評価器に専用の意味分類がないため、警告の有無を測定します。
H-15のcatch済みTypeErrorは情報noteとして返りますが、英語名と日本語が隣接する境界を固定規則が照合できずFAILです。
結果を上書きせず19/20として報告しています。

作者が作成する小規模な構造確認セットで、外部の盲検評価や未知のPython全般の代表標本ではありません。

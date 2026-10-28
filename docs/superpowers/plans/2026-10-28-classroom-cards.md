# Classroom Cards Implementation Plan

> For agentic workers: use superpowers:executing-plans. Root is the only code editor; reviews are read-only.

**Goal:** 学生の任意相談カード保存から先生の言語別集計までを、小さな一連の機能として実装する。
**Architecture:** src/classroom.pyに厳密なカード処理、src/classroom_ui.pyに画面を置く。既存解析へ役割切替とダウンロードを追加し、限定されたC/C++の誤案内を修正する。
**Tech Stack:** 既存Python 3.12 / Streamlit 1.65 / pytest、標準ライブラリ。依存追加なし。
**Spec:** ../specs/2026-10-28-classroom-cards-design.md（ユーザー承認済み）

## Global Constraints
- 既存589件のテスト、既存キー、Python用サンプルを維持する。
- 1ファイル16KiB、100ファイル、合計1MiB。schema_version=1。
- コード・ログ本文・パス・名前・自由記述・時刻をカードに含めない。自動収集・DB・AI送信なし。
- 解決は自己申告、集計は相談件数で人数ではない。学習概念は候補。
- コード編集はrootのみ。設計の承認には同範囲の実装・テスト・公開版確認を含むものとして進め、実装方法の再承認は求めない。

## Review Focus
- 秘密の独自例外名、ネストしたJSON、boolとint、重複JSONキー、非UTF8、不正語彙の拒否。
- 異なる内容で同じIDの衝突を順序によらず除外し、再描画で加算しない。
- 役割・入力・モードを変更した時のカードID、公開内容、ヒントの先出し、未計測の修正例閲覧。
- Cの修正例、未知ログの説明、MSVC日本語表記、既存PythonサンプルとC専用サンプルの区別。
- カード読込・絞込・消去・集計CSVを実画面で検証。アップロード単体はAppTestに加え実ブラウザで確認する。

### Task 1: カードの生成・検証・集計
Files: src/classroom.py、tests/test_classroom.py。
Interfaces: build_card(result, *, card_id, environment='unknown', learning_status='unanswered', hint_step=0, fix_viewed=None) -> dict。
encode_card(card)->bytes、decode_card(data:bytes)->dict、load_cards(payloads:Sequence[bytes])->CardBatch。
summarize(cards, *, language='all', phase='all')->dict、summary_csv(summary)->bytes、card_preview(card)->dict。
- [ ] RED: ラウンドトリップ、許可項目だけの生成、秘密の除外、Python/C別語彙、未知→unknown、全サイズ上限と破損データ、完全一致重複・衝突の順序不変、集計・CSVの候補と自己申告をテスト。
- [ ] GREEN: 列挙値と関連項目の照合を一か所で行い、入力本文を例外に混ぜない。
- [ ] 検証: pytest tests/test_classroom.py -q。成功出力を記録してコミット。

### Task 2: C/C++の誤案内・表示根拠
Files: src/models.py、src/c_family.py、src/explanations.py、src/hints.py、tests/test_classroom_languages.py。
Interfaces: ParsedError末尾にdiagnostic_code: str|Noneを追加。既知MSVCコードのみの安全な補助分類。
- [ ] RED: 正常・警告・未知の失敗断定なし、C/C++別修正例、日本語MSVC、native code保持、段階別ヒントをテスト。
- [ ] GREEN: コンパイル・リンク・実行を保守的に区別。C++例をCへ返さない。
- [ ] 検証: pytest tests/test_classroom.py tests/test_classroom_languages.py tests/test_c_family.py -q。成功後コミット。

### Task 3: 学生・先生の画面
Files: src/classroom_ui.py、src/language_examples.py、app.py、assets/workspace.css、tests/test_classroom_ui.py。
Interfaces: render_student_card(result, mode, hint_step, fix_viewed) / render_teacher_workspace()。役割キーworkspace_role。
- [ ] RED: 学生初期表示、先生に秘密が表示されない、カード生成・再解析のID更新、状態変更のID維持、ヒント0で回答が漏れない、言語別サンプル・色付け、教師の空表示/読込/フィルタ/消去をAppTestで検証。
- [ ] GREEN: 学生の既存画面へ任意のカード保存を追加。教師はファイル読込と再描画に依存しない純粋集計。
- [ ] 既存sample_choiceはPython用として保持。C/C++選択時は同言語の別サンプルを主表示し、旧Pythonサンプルは「Pythonに切替」の説明付きにする（既存テストとの互換）。
- [ ] 検証: 新規画面テスト、既存AppTest、全pytestを実行。成功後コミット。

### Task 4: 公開・資料・独立レビュー
Files: README.md、VERIFICATION.md、docs/hackathonの最新状態と利用手順。
- [ ] READMEを実機能に合わせ、実ユーザー効果未検証は維持。旧評価・形式確認結果は履歴として保存。
- [ ] 全pytest tests evaluation/tests -q、git diff --check、秘密の除外とカード上限を再確認。
- [ ] 読み取り専用レビューを依頼。重要指摘だけをRED→GREENで修正し、必要な全件検証を実施。
- [ ] mainへfast-forward、GitHubへpush。Cloudの更新モジュール混在は運営側でRebootし、公開版の学生/先生を確認。
- [ ] 実際のカード読込・絞込をブラウザで確認し、スクリーンショットを保存。件数・限界・公開URLを報告。

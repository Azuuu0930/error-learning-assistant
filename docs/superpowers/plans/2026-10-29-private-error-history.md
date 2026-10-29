# Private Error History Implementation Plan

> For agentic workers: superpowers:executing-plans。コード編集はrootのみ、最後に読み取り専用レビュー。

**Goal:** 解析の成否を問わず、匿名化補助付きログを非公開DBへ保存する。
**Architecture:** src/error_history.pyにマスク・設定検証・書込専用RPC通信。src/history_ui.pyに設定と通知。app.pyの解析前後だけで呼ぶ。supabase/migrationsに非公開schemaと書込関数。
**Tech Stack:** Python標準ライブラリ、既存Streamlit、Supabase/PostgreSQL。依存追加なし。
**Spec:** ../specs/2026-10-29-private-error-history-design.md

## Global Constraints
- 既存680テスト維持。ログ上限100000文字。ソースコード・利用者ID・IPをDBへ送らない。
- 自由なDB読み取りを公開アプリに追加しない。未設定・通信失敗で解析を止めない。
- ユーザーが細部を任せて実装を指定したため実装方法の再承認は求めない。外部サービスの契約・新規資格情報は本人操作。

## Review Focus
- traceback中のパス、URLの秘密、引用符つき秘密値、長いログも送信前マスク。
- pending保存後にアプリ解析例外。失敗状態を残し、本文を例外表示しない。
- 通信先のuserinfo・path・query・redirectへの秘密流出を拒否。
- SQL関数のデフォルトPUBLIC実行権限、テーブル・schemaのAPI公開、結果更新引数の不正。
- 無関係な再描画で保存しないこと、機能無効時に保存中と案内しないこと。

### Task 1: 書込専用の保存境界
Files: src/error_history.py、supabase/migrations/202610290001_error_history.sql、tests/test_error_history.py。
Interfaces: HistoryConfig.from_mapping(mapping)、redact_log(text)->(text,count)、HistoryStore.begin(log,language)->id、finish(id,status,error_type,category)->bool。通信は注入可能。
- [x] RED: マスク、設定とURL拒否、型と長さ、秘密・コード非送信、送信前pending、結果更新と通信失敗をテスト。
- [x] GREEN: 標準urllibでRPC POST、redirectなし、timeout3秒。SQLは書込/更新だけ。
- [x] 検証・コミット。

### Task 2: 解析前後の統合
Files: src/history_ui.py、app.py、README.md、docs/hackathon/ERROR_HISTORY_SETUP.md、tests/test_history_ui.py。
Interfaces: load_history_store()->HistoryStore|None、render_history_notice()、run_recorded_analysis(log,source,language,analyzer)->result。
- [x] RED: 設定なし、未知ログ、解析例外、長過ぎる入力、ヒントや再描画で重複なし、保存失敗時の解析継続をAppTestで確認。
- [x] GREEN: 固定された保存案内と安全な通知を表示。本文を運営者以外に返さない。
- [x] 全pytest tests evaluation/tests -q。資料の保存方針を正確に更新してコミット。

### Task 3: 非公開DB・公開版検証
- [x] 読み取り専用の独立レビュー、重要指摘をRED→GREENで修正。
- [x] Supabase SQL適用、一般キーの読取/実行拒否、書込と結果保存を模擬データで検証。
- [x] Streamlit Secrets設定、公開更新、公開ブラウザーと管理画面で確認。実施した確認だけを記録。

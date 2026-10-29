# 非公開エラー履歴の運営手順

## 保存するもの

「解析する」で送信された非空のエラー文を、改善のため保存します。解析前にpendingで記録し、
認識できた/判別できず/解析失敗/入力上限による拒否を結果として更新します。
「認識できた」はログ形式の判別であり、回答の正しさや解決の実証ではありません。
途中の入力や過去セッションを自動回収する仕組みはありません。

記録ID、受信日時、言語、伏せ字済みログ、伏せ字の置換件数、切り詰め有無、解析状態、許可された分類だけを保存します。
IP・cookie・利用者ID・端末情報・氏名欄・コード欄は収集しません。
ログに引用されているコードの一部はログの一部として残る場合があります。
絶対パス・メール・URL・代表的な秘密値は自動でマスクしますが、自由文中の氏名などを完全に匿名化する保証はありません。
保存期間の自動制限・自動削除は今回追加していません。運営者が必要性と削除方針を管理してください。
10万文字を超えるログは先頭10万文字を伏せ字処理し、truncated=true、解析結果はrejectedで保存します。

## 保存先と権限

Supabaseの専用プロジェクトを使用します。現在の作成先はWest EU（Ireland）、eu-west-1です。
本文の保存先は error_archive.entries。公開APIへschemaを追加しないでください。
RLS有効、PUBLIC/anon/authenticated/service_roleのテーブル権限とschema利用権限を剥奪しています。
書込専用のarchive_error/complete_error関数だけservice_roleに許可します。
関数は本文や一覧を返さず、固定search_pathと許可値の検査を使います。
プロジェクト所有者の管理画面以外に閲覧機能を作りません。先生の画面や相談カードに本文は出ません。
これはアプリの閲覧権限の説明です。クラウド事業者・プロジェクト管理者の取扱い方針や権限は別に適用されます。
組織へ他のメンバーを招待すると管理権限が広がる可能性があるため、当面は所有者のみとします。
Codexへの自動送信もなく、所有者が許可した作業時だけ管理画面を操作します。

## 初回設定

1. 所有者がSupabaseプロジェクトを作成。「Automatically expose new tables」はOFF、RLSは有効にします。
2. SQL Editorで supabase/migrations/202610290001_error_history.sql を適用します。既存データの削除は含みません。
3. Supabaseのサーバー用secret key（sb_secret_...）またはlegacy service_roleを用意します。publishable/anonキーでは書けません。
4. Streamlit Community CloudのSettings → Secretsに次を追加します。既存の任意AI設定を上書きしないでください。

~~~toml
[error_history]
enabled = true
url = "https://YOUR_PROJECT_REF.supabase.co"
secret_key = "YOUR_SERVER_ONLY_SECRET"
~~~

接続先は20文字のproject refを持つ公式HTTPSホストだけを受け付けます。末尾スラッシュ・path・query・userinfoは指定しません。
秘密鍵を公開リポジトリ、スクリーンショット、チャット、エラー文へ貼り付けないでください。
設定変更後はアプリを再起動します。未設定時は保存無効、設定不正時も保存せず、入力前の案内に状態を表示します。
3秒timeout、redirect拒否。保存障害でも解析は継続しますが、未保存を成功と表示しません。
更新だけ失敗した記録はpendingで残ります。通信障害時まで全件保存を保証するものではありません。
ローカルファイル・共有GitHub・別の保存先へ迂回して保存しません。

## 後から見る

Supabase管理画面のSQL Editorへ所有者としてログインし、次を実行します。

~~~sql
select id, received_at, language, analysis_status, error_type, category,
       redaction_count, truncated, log_redacted
from error_archive.entries
order by received_at desc, id desc
limit 100;
~~~

Table Editorでerror_archive schemaを選んでも確認できます。一般のアプリには管理者の入口・隠しURLも作っていません。
現在の所有者アカウントには、本文と状態を表示するクエリをSQL Editorのプライベート領域に保存しました。
日本語の表示項目で内容を確認できます。新しい記録を取得するときはRunを押します。
情報を共有する際は伏せ字漏れを人が確認してください。サンプル検証を実際の利用者の実績と混ぜないでください。
不要な記録は所有者がIDを確認して削除します。削除は取り消せない場合があるため、Codexは指示なしに実行しません。

## 公開前の確認

- anon/publishableキーでテーブルの読取と書込関数実行が拒否されること。
- secret keyでもテーブル直接読取が拒否され、関数による書込/更新だけ可能なこと。
- 模擬ログでマスク後の本文と判別不能の保存を確認すること。
- Streamlit再起動後にもDBに残ること。利用者への案内が「保存なし」のままになっていないこと。
- 実際に試した範囲だけVERIFICATION.mdへ記録すること。

2026-10-29に、書込と状態更新4種、一般キーの実行拒否、非公開schemaの読取拒否、公開版からの未知ログの保存と伏せ字を確認しました。
サーバー用認証は、実動作を確認できたlegacy service_role方式を使用しています。

将来のクラス別閲覧は、認証・所属・クラス権限・利用者への説明を別に実装します。
現在の匿名履歴を勝手に先生全員へ公開したり、以前の本文へ後からクラスを推測して付けたりしません。

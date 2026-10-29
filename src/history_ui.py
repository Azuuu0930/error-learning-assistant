"""Private history integration; no reading API and no administrator UI here."""
from dataclasses import dataclass
import streamlit as st
from src.error_history import HistoryConfig, HistoryStore


@dataclass(frozen=True)
class HistoryConnection:
    store: HistoryStore | None
    state: str


@dataclass(frozen=True)
class HistoryAttempt:
    store: HistoryStore | None
    ident: str | None = None


@st.cache_resource(show_spinner=False)
def get_history_connection() -> HistoryConnection:
    try:
        values = st.secrets.get("error_history", {})
    except FileNotFoundError:
        values = {}
    except Exception:
        return HistoryConnection(None, "misconfigured")
    try:
        config = HistoryConfig.from_mapping(values)
    except Exception:
        return HistoryConnection(None, "misconfigured")
    return HistoryConnection(HistoryStore(config), "ready") if config else HistoryConnection(None, "disabled")


def render_history_notice():
    state = get_history_connection().state
    if state == "ready":
        st.info("「解析する」で送信したエラー文は、解析できたかに関係なく、改善のためSupabaseへ非公開で保存します。"
                "名前やIPは追加収集せず、コード欄の本文は保存しません。閲覧は現在、運営者の管理画面だけに限定し、"
                "先生・他の利用者には公開しません。本文中のパス・メール・代表的な秘密値は自動で伏せますが、"
                "完全な匿名化は保証できません。個人情報や秘密は入力しないでください。保存期間は運営者が管理します。")
    elif state == "misconfigured":
        st.warning("履歴保存の準備が整っていないため、エラー文は保存していません。解析はそのまま利用できます。")
    else:
        st.info("現在、エラー文の履歴は保存していません。ログとコードはこのセッションの解析に使用します。")


def begin_history(log, language) -> HistoryAttempt:
    store = get_history_connection().store
    ident = store.begin(log, language) if store else None
    if store and ident is None:
        st.warning("エラー文を保存できませんでした。解析は続けます。")
    return HistoryAttempt(store, ident)


def finish_history(attempt: HistoryAttempt, status, result=None):
    if not attempt.ident:
        return
    error = result.error if result else None
    if status == "result":
        status = ("unrecognized" if error.status == "unrecognized" or
                  error.category == "unknown" or error.error_type is None else "recognized")
    if attempt.store.finish(attempt.ident, status, error.error_type if error else None,
                            error.category if error else "unknown"):
        st.caption("エラー文を伏せ字処理して非公開で記録しました。個人の特定や、解決できたかの確認を行う記録ではありません。")
    else:
        st.warning("エラー文は保存しましたが、解析状態を更新できませんでした。管理画面では「処理中」として残ります。")

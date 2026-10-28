"""Optional post-hint coaching; network calls only on a consented button action."""
import hashlib
import json
import os
import uuid

import streamlit as st

from src.coach_provider import CoachConfig, CoachOutcome, CoachService, ENDPOINT, MODEL, build_request
from src.learning_coach import GOALS, build_context, standard_question


def clear_coach_state(state=None):
    state = st.session_state if state is None else state
    for key in list(state):
        if key.startswith("coach_") and key != "coach_session_id":
            del state[key]


def _clear_choice():
    for key in ("coach_outcome", "coach_consent", "coach_access"):
        st.session_state.pop(key, None)


@st.cache_resource(show_spinner=False)
def get_coach_service():
    # Never print, enumerate, cache as function arguments, or show secrets.
    values = {}
    for key in ("AI_TUTOR_ENABLED", "OPENAI_API_KEY", "AI_TUTOR_ACCESS_CODE"):
        value = os.environ.get(key)
        if value is None:
            try:
                value = st.secrets.get(key, "")
            except Exception:
                value = ""
        values[key] = value
    return CoachService(CoachConfig.from_mapping(values))


def _basis(result, question):
    if question.basis_id == "log":
        st.caption("根拠：入力ログの例外種類・行番号。実行結果をこちらで確かめたものではありません。")
        return
    index = int(question.basis_id.removeprefix("finding_"))
    finding = result.code_analysis.findings[index]
    labels = {"high": "高", "medium": "中", "low": "低"}
    st.caption(f"参照した候補：{finding.line}行目・信頼度 {labels[finding.confidence]}。原因の確定ではありません。")
    st.text(finding.message)


def render_coach(result, mode: str, hint_step: int):
    if mode != "通常モード" and hint_step < 3:
        return
    # Bind to the original input too: two different programs can produce the
    # same anonymized payload but must never share consent or displayed output.
    revision = hashlib.sha256(json.dumps([
        st.session_state.get("error_log", ""), st.session_state.get("source_code", ""), mode, hint_step
    ], ensure_ascii=False).encode()).hexdigest()
    if st.session_state.get("coach_revision") != revision:
        clear_coach_state()
        st.session_state.coach_revision = revision
    st.session_state.setdefault("coach_session_id", uuid.uuid4().hex)
    with st.expander("次の一歩を考える", expanded=False):
        st.caption("ヒントを読んでも迷ったら、考えるための問いを一つ選びましょう。修正例を自動で開くことはありません。")
        goal = st.selectbox("今、どこで止まっていますか？", list(GOALS), index=2,
                            format_func=GOALS.get, key="coach_goal", on_change=_clear_choice)
        context = build_context(result, goal)
        if st.button("標準ガイドを見る", key="coach_standard"):
            st.session_state.coach_outcome = CoachOutcome("standard", standard_question(context))
        st.caption("標準ガイドは外部の人工知能へ送信せずに利用できます。")
        with st.expander("人工知能に問いを選んでもらう（任意）"):
            st.caption("人工知能は、エラーの種類・診断候補・選んだ目的から、用意された問いを一つ選びます。新しい診断や修正コードは生成しません。")
            st.caption(f"送信先：OpenAIのAPI（{ENDPOINT}）／利用モデル：{MODEL}")
            st.caption("コード・ログ本文・変数名・ファイル名・値は送りません。送信内容は下で確認できます。人工知能による問い選びの有用性は検証中です。")
            with st.expander("送信内容を確認する"):
                st.json(build_request(context))
                st.caption("ここに表示したデータが送信本文です。認証用の運営APIキーは別途暗号化された通信のヘッダーに付与されます。")
            st.markdown("送信先での保存・取扱いは[OpenAIのデータ方針](https://developers.openai.com/api/docs/guides/your-data)をご確認ください。データを保持しない設定で送りますが、提供元での保持がないことを保証するものではありません。")
            service = get_coach_service()
            if not service.config.ready:
                st.info("人工知能による問い選びは現在準備中です。上の標準ガイドはそのまま使えます。")
            else:
                st.caption("試用中の機能です。運営から案内された試用コードを使用してください。")
                code = st.text_input("試用コード", type="password", max_chars=256, key="coach_access")
                consent = st.checkbox("送信内容を確認し、OpenAIへの送信に同意する", key="coach_consent")
                if st.button("人工知能に確認の問いを選んでもらう", key="coach_request", disabled=not consent or not code):
                    with st.spinner("次に考える問いを選んでいます…"):
                        st.session_state.coach_outcome = service.choose(
                            context, consent=consent, access_code=code,
                            session_id=st.session_state.coach_session_id)
        outcome = st.session_state.get("coach_outcome")
        if outcome:
            if outcome.status == "ai":
                st.caption("人工知能が選んだ確認の問い")
            else:
                messages = {"access_required": "試用コードを確認できませんでした。標準ガイドを表示します。",
                            "limited": "試用の利用上限に達したか、別の処理中です。標準ガイドを表示します。"}
                if outcome.status not in {"standard", "disabled"}:
                    st.info(messages.get(outcome.status, "人工知能を利用できなかったため、標準ガイドを表示します。"))
                st.caption("標準ガイド（外部の人工知能を使用していません）")
            st.text(outcome.question.text)
            _basis(result, outcome.question)

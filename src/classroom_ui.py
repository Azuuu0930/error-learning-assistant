"""学生の任意保存と先生の持ち込み集計。共有DB・自動送信は使わない。"""
from uuid import uuid4
import pandas as pd
import streamlit as st
from src.classroom import (LANGUAGES, ENVIRONMENTS, LEARNING_STATUSES, PHASES, CONCEPTS,
    MAX_FILES, MAX_BATCH_BYTES, build_card, encode_card, card_preview, load_cards, summarize, summary_csv)


def clear_student_card():
    for key in ("consultation_card", "card_id", "card_learning_status", "card_environment",
                "card_hint_max", "card_fix_seen"):
        st.session_state.pop(key, None)


def switch_workspace():
    keys = ("error_log", "source_code", "source_language", "display_mode",
            "card_learning_status", "card_environment", "language_example")
    if st.session_state.workspace_role == "先生":
        st.session_state.student_draft = {k: st.session_state[k] for k in keys if k in st.session_state}
    else:
        for key, value in st.session_state.get("student_draft", {}).items():
            st.session_state[key] = value


def render_student_card(result, mode, hint_step, fix_viewed):
    st.session_state.setdefault("card_id", str(uuid4()))
    # Display mode may reset the visible hint; the consultation keeps this analysis's history.
    st.session_state.card_hint_max = max(st.session_state.get("card_hint_max", 0), hint_step)
    if mode == "ヒントモード":
        st.session_state.card_fix_seen = st.session_state.get("card_fix_seen", False) or fix_viewed
    with st.expander("先生に相談する（任意）"):
        st.caption("困っている種類と、どこまで試したかをまとめます。保存するかどうかは自分で選べます。")
        status = st.selectbox("今の状態", list(LEARNING_STATUSES), format_func=LEARNING_STATUSES.get, key="card_learning_status")
        allowed = [k for k in ENVIRONMENTS if not (
            result.error.language == "python" and k in {"gcc", "clang", "msvc"} or
            result.error.language != "python" and k == "python")]
        environment = st.selectbox("実行環境（分かる範囲）", allowed, format_func=ENVIRONMENTS.get, key="card_environment")
        card = build_card(result, card_id=st.session_state.card_id, environment=environment,
                          learning_status=status, hint_step=st.session_state.card_hint_max,
                          fix_viewed=st.session_state.get("card_fix_seen", False) if mode == "ヒントモード" else None)
        st.session_state.consultation_card = card
        st.info("コード・ログ本文・名前・ファイル名は含みません。カードだけではコードの具体的な問題までは伝わりません。")
        with st.expander("保存する内容を確認"):
            st.json(card_preview(card))
        st.download_button("相談カードを保存", data=encode_card(card), file_name=f"相談カード-{card['card_id']}.json",
                           mime="application/json", key="download_card", on_click="ignore", use_container_width=True)
        st.caption("先生へ自動送信しません。授業の案内に従ってファイルを渡してください。解決は自己申告です。")


def _clear_teacher():
    st.session_state.pop("teacher_batch", None)
    st.session_state.teacher_files_epoch = st.session_state.get("teacher_files_epoch", 0) + 1
    for key in ("teacher_language", "teacher_phase"):
        st.session_state.pop(key, None)


def _read_uploads(uploads):
    if len(uploads) > MAX_FILES or sum(u.size for u in uploads) > MAX_BATCH_BYTES:
        raise ValueError("一度に読めるのは100ファイル、合計1MiBまでです。")
    return load_cards([u.getvalue() for u in uploads])


def _table(counts, heading, labels=None):
    labels = labels or {}
    return pd.DataFrame([{heading: labels.get(k, k), "相談件数": v}
                         for k, v in sorted(counts.items(), key=lambda item: (-item[1], item[0]))],
                        columns=[heading, "相談件数"])


def render_teacher_workspace():
    st.markdown('<section class="teacher-hero"><span class="eyebrow">先生のワークスペース</span><h1>授業の次の一手を、<br><span>見つける。</span></h1><p>受け取った相談カードで、復習や声かけの候補を整理します。</p><div class="hero-chips"><span>アカウント登録なし</span><span>コード本文を集めない</span><span>Python・C・C++</span></div></section>', unsafe_allow_html=True)
    st.subheader("先生の授業サポート")
    st.caption("① 学生からカードを受け取る　→　② まとめて読み込む　→　③ 復習の候補を確認する")
    with st.container(border=True, key="teacher_upload"):
        st.write("**相談カードを読み込む**")
        st.caption("学生が保存したJSONを選んでください。1枚16KiB、100枚・合計1MiBまで。授業の許可に従って利用してください。")
        uploads = st.file_uploader("相談カード（JSON）", type=["json"], accept_multiple_files=True, max_upload_size=1,
                                   key=f"teacher_files_{st.session_state.get('teacher_files_epoch', 0)}")
        if st.button("カードを読み込む", key="load_teacher_cards", type="primary", disabled=not uploads):
            st.session_state.pop("teacher_batch", None)
            try:
                with st.spinner("相談カードの内容を確認しています…"):
                    st.session_state.teacher_batch = _read_uploads(uploads)
            except ValueError as exc:
                st.warning(str(exc))
        st.caption("ファイルは解析のためアプリサーバーへ届きます。入力履歴の永続保存・他の先生との共有・外部AI送信は行いません。ホスティング先の方針も適用されます。")
    batch = st.session_state.get("teacher_batch")
    if batch is None:
        st.info("まだカードを読み込んでいません。学生は解析結果の「先生に相談する」から保存できます。")
        st.caption("成績・人数・学習効果を測る画面ではありません。読み込んだ相談の件数を確認します。")
        return
    st.button("読み込んだカードを消去", key="clear_teacher_cards", on_click=_clear_teacher)
    if batch.invalid:
        st.warning(f"読み取れなかったカード：{batch.invalid}枚。正しいカードだけを集計します。")
        with st.expander("読込エラーを確認"):
            for error in batch.errors:
                st.text(error)
    if batch.duplicates:
        st.info(f"同じ内容の重複カード{batch.duplicates}枚を除外しました。")
    if batch.conflicts:
        st.warning(f"同じIDで内容が異なる相談{batch.conflicts}件をすべて除外しました。最新版だけを選び直してください。")
    if not batch.cards:
        st.info("集計できるカードがありません。内容や版を確認して読み込み直してください。")
        return
    with st.container(border=True, key="teacher_filters"):
        left, right = st.columns(2)
        with left:
            language = st.selectbox("言語で絞り込む", ["all", *LANGUAGES],
                                    format_func=lambda k: "すべての言語" if k == "all" else LANGUAGES[k], key="teacher_language")
        with right:
            phase = st.selectbox("発生段階で絞り込む", ["all", *PHASES],
                                 format_func=lambda k: "すべての段階" if k == "all" else PHASES[k], key="teacher_phase")
    summary = summarize(batch.cards, language=language, phase=phase)
    a, b, c = st.columns(3)
    a.metric("相談カード", summary["total"])
    b.metric("まだ困っている", summary["stuck"])
    c.metric("ヒント3まで閲覧", summary["hint3"])
    st.caption(f"状態未回答：{summary['unanswered']}件 ／ 修正例の閲覧が未計測：{summary['fix_unmeasured']}件。通常モードの開閉は測定していません。")
    st.info("件数は学生の人数ではありません。同じ学生の別相談も含みます。解決は自己申告、学習概念は復習の候補であり、理解不足の確定ではありません。")
    if not summary["total"]:
        st.info("この絞り込みに該当する相談はありません。")
        return
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("復習を考える候補")
        concepts = _table(summary["by_concept"], "学習概念の候補", CONCEPTS)
        if not concepts.empty:
            st.bar_chart(concepts, x="学習概念の候補", y="相談件数", horizontal=True, color="#59DDC3")
        else:
            st.caption("このログから学習概念の候補を絞れませんでした。")
        st.caption("一つの相談に複数候補があるため、候補の合計と相談件数は一致しない場合があります。")
        st.dataframe(concepts, hide_index=True, use_container_width=True)
    with right:
        st.subheader("エラーの種類・診断コード")
        st.dataframe(_table(summary["by_error"], "種類・診断コード"), hide_index=True, use_container_width=True)
        st.subheader("学生の状態（自己申告）")
        st.dataframe(_table(summary["by_status"], "今の状態", LEARNING_STATUSES), hide_index=True, use_container_width=True)
    with st.expander("言語と発生段階の内訳"):
        st.dataframe(_table(summary["by_language"], "言語", LANGUAGES), hide_index=True)
        st.dataframe(_table(summary["by_phase"], "発生段階", PHASES), hide_index=True)
    st.download_button("この集計をCSVで保存", data=summary_csv(summary), file_name="相談カードの集計.csv",
                       mime="text/csv", key="download_teacher_summary", on_click="ignore")
    st.caption("カードは外部で編集できるため、本人や実行結果を認証した記録ではありません。授業の状況と合わせて判断してください。")

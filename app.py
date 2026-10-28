"""Streamlit UI。ログ解析と教育ロジックはsrcに分離する。"""

import json
from pathlib import Path

import streamlit as st

from src.analyzer import analyze_error
from src.code_analysis import CONFIDENCE_LABELS
from src.explanations import CATEGORY_LABELS
from src.error_catalog import CATALOG_BY_TYPE, ERROR_CATALOG
from src import ui
from src.view import render_code_context


APP_DIR = Path(__file__).resolve().parent
MAX_INPUT_CHARS = 100_000


def invalidate_result() -> None:
    st.session_state.pop("analysis", None)
    st.session_state.hint_step = 0
    st.session_state.show_fix = False


def reset_hints() -> None:
    st.session_state.hint_step = 0
    st.session_state.show_fix = False


@st.cache_data
def load_samples() -> list[dict]:
    path = APP_DIR / "examples" / "sample_errors.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def load_selected_sample() -> None:
    sample = next((item for item in load_samples() if item["title"] == st.session_state.sample_choice), None)
    if sample:
        st.session_state.error_log = sample["error_log"]
        st.session_state.source_code = sample["code"]
        invalidate_result()


def load_catalog_example() -> None:
    example = CATALOG_BY_TYPE.get(st.session_state.error_search)
    if example:
        st.session_state.error_log = example.error_log
        st.session_state.source_code = example.code
        invalidate_result()


def render_fix(result) -> None:
    if result.explanation.fix_example:
        st.caption(result.explanation.fix_note)
        st.code(result.explanation.fix_example, language="python")
    else:
        st.info("このエラーの修正例はまだ用意していません。ヒントと元のメッセージをもとに調べてみてください。")


def render_code_analysis(analysis, reveal: bool) -> None:
    if analysis is None:
        return
    st.subheader("コードから分かったこと")
    if analysis.status == "unavailable":
        for note in analysis.notes:
            st.info(note)
        return
    if not reveal:
        st.caption("コードの補助解析ができました。ヒントを3つ確認すると、信頼度付きの詳しい結果を表示します。")
        return
    st.caption("信頼度 高：コードから確認できる事実 / 中：可能性が高い候補 / 低：追加確認が必要な候補。静的解析は実行時の状態や意図を完全には判断できません。")
    for finding in analysis.findings:
        st.text(f"• ［信頼度：{CONFIDENCE_LABELS[finding.confidence]}・{finding.line}行目］{finding.message}")
    if not analysis.findings:
        st.info("この解析で指摘できる候補は見つかりませんでした。エラーがないことや正常動作を保証する結果ではありません。")
    for note in analysis.notes:
        st.caption(note)
    with st.expander("コード内の定義名・使用名を確認"):
        st.text("定義名：" + ("、".join(analysis.defined_names) or "なし"))
        st.text("使用名：" + ("、".join(analysis.used_names) or "なし"))
        st.caption("定義名にはimport名・関数名・引数も含みます。候補の判定は一覧の単純比較ではなく、スコープごとに行っています。")


def render_result(result, mode: str) -> None:
    error = result.error
    ui.section_kicker("02", "ANALYSIS")
    st.subheader("解析結果")
    ui.result_badges(CATEGORY_LABELS[error.category], result.code_analysis is not None)
    st.subheader(error.error_type or "エラー種類を取得できませんでした")
    st.caption(f"使用言語：Python（入力対象） · カテゴリ：{CATEGORY_LABELS[error.category]}")
    location = f"{error.file} · {error.line}行目" if error.file and error.line else "場所は取得できませんでした"
    st.write("**エラー箇所**")
    st.text(location)
    if error.message:
        st.caption("元のエラーメッセージ")
        st.code(error.message, language=None, wrap_lines=True)
    for warning in error.warnings:
        st.warning(warning)
    for note in result.notes:
        st.caption(note)
    if result.code_context:
        st.write("**該当行と前後のコード**（▶がエラー行）")
        st.markdown(render_code_context(result.code_context), unsafe_allow_html=True)

    render_code_analysis(result.code_analysis, mode == "通常モード" or st.session_state.hint_step == 3)

    if mode == "通常モード":
        st.subheader("初心者向けの説明")
        st.text(result.explanation.summary)
        st.write("**考えられる原因**")
        st.text(result.explanation.cause)
        st.write("**確認するポイント**")
        for i, checkpoint in enumerate(result.explanation.checkpoints, 1):
            st.text(f"{i}. {checkpoint}")
        st.info(result.explanation.reading_tip)
        with st.expander("修正例を見る"):
            render_fix(result)
    else:
        st.subheader("一歩ずつ考える")
        step = st.session_state.hint_step
        st.caption(f"ヒント {step} / 3")
        ui.render_hint_progress(step)
        if step < 3:
            label = "ヒント1を見る" if step == 0 else f"ヒント{step + 1}を見る"
            if st.button(label, key="next_hint"):
                st.session_state.hint_step += 1
                st.rerun()
        for i, hint in enumerate(result.hints[:st.session_state.hint_step], 1):
            with st.container(key=f"learning_hint_{i}"):
                ui.hint_heading(i)
                st.text(hint)
        if st.session_state.hint_step == 3:
            if st.button("修正例を見る", key="reveal_fix"):
                st.session_state.show_fix = True
            if st.session_state.show_fix:
                render_fix(result)

    with st.expander("ログの読み方と構造化データ"):
        st.write("① 最後の行でエラー種類とメッセージを読む。② 直前の File と line で場所を読む。③ 対象の名前や操作をコードで探す。")
        st.json(error.to_dict())


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">&gt;_ TRACE / LEARN</div><div class="sidebar-eyebrow">LEARNING WORKSPACE</div>', unsafe_allow_html=True)
        st.subheader("サンプルで試す")
        st.caption("よくあるエラーから、読み解く練習を。")
        samples = load_samples()
        st.selectbox("エラーを選択", ["選択してください"] + [item["title"] for item in samples], key="sample_choice")
        st.button("サンプルを入力", key="load_sample", on_click=load_selected_sample,
                  disabled=st.session_state.sample_choice == "選択してください", use_container_width=True)
        st.markdown('<div class="sidebar-path"><div><b>1</b>ログとコードを用意する</div><div><b>2</b>エラーの場所を読み解く</div><div><b>3</b>ヒントから考えてみる</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="privacy-note"><b>入力の取り扱い</b>公開版ではログとコードをこのアプリのサーバーへ送り、解析します。外部LLMには送信せず、入力コードの実行や履歴の保存も行いません。個人情報やAPIキーは取り除いてから入力してください。</div>', unsafe_allow_html=True)
        st.toggle("動きを減らす", key="reduce_motion", help="このセッションの装飾アニメーションを停止します。OSの「視差効果を減らす」設定にも自動で従います。")
        st.caption("対応言語：Python · 18種類のエラー")


def main() -> None:
    st.set_page_config(page_title="TRACE / LEARN · エラーを読み解く", page_icon="🔎", layout="wide")
    for key, value in {"hint_step": 0, "show_fix": False, "error_log": "", "source_code": "", "reduce_motion": False}.items():
        st.session_state.setdefault(key, value)
    render_sidebar()
    ui.apply_theme(st.session_state.reduce_motion)
    ui.render_hero()

    left, right = st.columns([1, 1.06], gap="large")
    with right:
        with st.container(border=True, key="result_panel"):
            result_area = st.empty()
    with left:
        with st.container(border=True, key="input_panel"):
            ui.section_kicker("01", "INPUT")
            st.subheader("エラーを貼り付ける")
            st.caption("ログだけでも大丈夫。関連コードがあると、もう少し詳しく。")
            st.selectbox("エラーを検索して試す", [entry.error_type for entry in ERROR_CATALOG],
                         index=None, key="error_search", placeholder="名前やキーワードで検索… 例：変数、型、NameError",
                         format_func=lambda name: CATALOG_BY_TYPE[name].search_label,
                         on_change=load_catalog_example,
                         help="18種類のエラーを英語名・日本語で検索できます。選ぶとサンプルを入力します。解析はボタンを押したときに行います。")
            st.text_area("エラーログ", key="error_log", height=205,
                         placeholder='Traceback (most recent call last):\n  File "main.py", line 8, in <module>\n    print(user_name)\nNameError: name \'user_name\' is not defined',
                         help="Tracebackから最後のエラー行まで貼ると、ファイル名と行番号も確認できます。",
                         on_change=invalidate_result)
            with st.expander("ソースコード（任意）", expanded=False):
                st.text_area("関連するPythonコード", key="source_code", height=190,
                             placeholder="# エラーが起きたファイルのコードを1行目から貼り付けます",
                             help="行番号を合わせるため、最終フレームに表示されたファイル全体を1行目から貼り付けてください。",
                             on_change=invalidate_result)
            mode = st.radio("表示モード", ["ヒントモード", "通常モード"], horizontal=True,
                            key="display_mode", on_change=reset_hints)
            st.caption("ヒントモード：3段階で考える。修正例は、最後に自分で開けます。")
            if st.button("解析する", type="primary", key="analyze", use_container_width=True):
                invalidate_result()
                log, source = st.session_state.error_log, st.session_state.source_code
                if not log.strip():
                    st.warning("エラーログを入力してください。検索や左のサンプルからも試せます。")
                elif max(len(log), len(source)) > MAX_INPUT_CHARS:
                    st.warning("入力が長すぎます。ログとコードはそれぞれ10万文字以内にしてください。")
                else:
                    with result_area.container():
                        ui.render_loading()
                    try:
                        st.session_state.analysis = analyze_error(log, source)
                    except Exception:
                        # Keep implementation details and potentially sensitive input out of the UI.
                        st.error("解析を完了できませんでした。入力を確認して、もう一度「解析する」を押してください。")
                    finally:
                        result_area.empty()
            st.caption("ログ・コードは各10万文字まで · 貼り付けたコードは実行しません")

    with result_area.container():
        result = st.session_state.get("analysis")
        if result is None:
            ui.render_empty_state()
        else:
            render_result(result, mode)
    ui.render_footer()


if __name__ == "__main__":
    main()

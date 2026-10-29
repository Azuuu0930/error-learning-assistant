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
from src.coach_ui import clear_coach_state, render_coach
from src.classroom_ui import clear_student_card, switch_workspace, render_student_card, render_teacher_workspace
from src.language_examples import EXAMPLE_LABELS, examples_for
from src.history_ui import render_history_notice, begin_history, finish_history


APP_DIR = Path(__file__).resolve().parent
MAX_INPUT_CHARS = 100_000
ERROR_NAMES_JA = {
    "SyntaxError": "文法エラー", "IncompleteInputError": "入力が未完成のエラー", "IndentationError": "字下げエラー",
    "NameError": "名前が見つからないエラー", "UnboundLocalError": "ローカル変数が未設定のエラー",
    "TypeError": "データ型の使い方エラー", "ValueError": "値の形式エラー",
    "IndexError": "添字の範囲エラー", "KeyError": "キーが見つからないエラー",
    "AttributeError": "属性やメソッドが見つからないエラー",
    "ModuleNotFoundError": "モジュールが見つからないエラー", "ImportError": "読み込みエラー",
    "FileNotFoundError": "ファイルが見つからないエラー", "ZeroDivisionError": "0で割る計算エラー",
    "RecursionError": "再帰の呼び出しが深すぎるエラー", "StopIteration": "繰り返しの終了",
    "AssertionError": "条件確認の失敗", "RuntimeError": "実行時エラー",
    "UnicodeDecodeError": "文字コードの読み取りエラー", "CompilationError": "コンパイルエラー",
    "LinkerError": "リンク時エラー", "SegmentationFault": "不正なメモリアクセス",
}


def localized_error_details(error) -> dict:
    """機械向けの解析結果を、画面用に日本語の項目名で表示する。"""
    language_names = {"python": "Python", "c": "C", "cpp": "C++"}
    statuses = {"complete": "解析完了", "partial": "一部を解析", "unrecognized": "判別できず"}
    frames = [{
        "ファイル": frame.file,
        "行番号": frame.line,
        "関数": frame.function,
        "該当行": frame.source,
    } for frame in error.frames]
    return {
        "言語": language_names.get(error.language, error.language),
        "エラー名": error.error_type,
        "診断コード": getattr(error, "diagnostic_code", None),
        "メッセージ": error.message,
        "ファイル": error.file,
        "行番号": error.line,
        "対象": error.target,
        "分類": CATEGORY_LABELS.get(error.category, "未分類"),
        "解析状況": statuses.get(error.status, error.status),
        "呼び出し履歴": frames,
        "補足": list(error.warnings),
    }


def invalidate_result() -> None:
    clear_coach_state()
    clear_student_card()
    st.session_state.pop("analysis", None)
    st.session_state.hint_step = 0
    st.session_state.show_fix = False


def reset_hints() -> None:
    clear_coach_state()
    st.session_state.hint_step = 0
    st.session_state.show_fix = False


def change_language() -> None:
    invalidate_result()
    st.session_state.pop("language_example", None)


def load_language_example() -> None:
    language = "c" if st.session_state.source_language == "C" else "cpp"
    example = examples_for(language).get(st.session_state.get("language_example"))
    if example:
        st.session_state.error_log, st.session_state.source_code = example
        invalidate_result()


@st.cache_data
def load_samples() -> list[dict]:
    path = APP_DIR / "examples" / "sample_errors.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def load_selected_sample() -> None:
    sample = next((item for item in load_samples() if item["title"] == st.session_state.sample_choice), None)
    if sample:
        st.session_state.source_language = "Python"
        st.session_state.error_log = sample["error_log"]
        st.session_state.source_code = sample["code"]
        invalidate_result()


def load_catalog_example() -> None:
    example = CATALOG_BY_TYPE.get(st.session_state.error_search)
    if example:
        st.session_state.source_language = "Python"
        st.session_state.error_log = example.error_log
        st.session_state.source_code = example.code
        invalidate_result()


def render_fix(result) -> None:
    if result.explanation.fix_example:
        st.caption(result.explanation.fix_note)
        st.code(result.explanation.fix_example, language=result.error.language)
    else:
        st.info("このエラーの修正例はまだ用意していません。ヒントと元のメッセージをもとに調べてみてください。")


def render_code_analysis(analysis, reveal: bool) -> None:
    if analysis is None:
        return
    st.subheader("コードから分かったこと")
    if analysis.status == "unavailable":
        for note in analysis.notes:
            st.info(note)
        # Community Cloudの更新直後には旧形式のセッション結果も残り得る。
        issue = getattr(analysis, "syntax_error", None)
        if issue:
            st.caption("以下は貼り付けたコード自体の構文診断です。元ログのファイル・行番号とは別に確認しています。")
            if issue.source_line:
                st.code(f"{issue.line} | {issue.source_line}", language="python")
            if reveal:
                st.text(issue.explanation.summary)
                st.text(issue.explanation.cause)
            else:
                st.caption("文法の手がかりも、段階式ヒントで確認できます。詳しい説明はヒント3まで進むと表示します。")
            with st.expander("構文解析の詳しい情報"):
                st.code(issue.message, language=None)
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
    ui.section_kicker("02", "解析")
    st.subheader("解析結果")
    ui.result_badges(CATEGORY_LABELS[error.category], result.code_analysis is not None)
    error_name = (error.error_type or "").rsplit(".", 1)[-1]
    fallback_title = "専用の説明がないエラー" if error_name else "エラー種類を特定できませんでした"
    st.subheader(ERROR_NAMES_JA.get(error_name, fallback_title))
    if error_name:
        st.caption(f"エラー名：{error_name}")
    language_label = {"python": "Python", "c": "C", "cpp": "C++"}.get(error.language, "Python")
    st.caption(f"使用言語：{language_label}・分類：{CATEGORY_LABELS.get(error.category, '未分類')}")
    location = f"{error.file}・{error.line}行目" if error.file and error.line else "場所は取得できませんでした"
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

    if error.language == "python":
        render_coach(result, mode, st.session_state.hint_step)

    with st.expander("ログの読み解き方・詳しい情報"):
        if error.language == "python":
            st.write("① 最後の行でエラー名とメッセージを読みます。② 直前のファイル名と行番号で場所を確認します。③ 対象の名前や操作をコードから探します。")
        else:
            st.write("① コンパイル・リンク・実行のどの出力かを確認します。② エラーと警告を区別し、診断のファイル名・行番号を読みます。③ 関係する宣言・定義・ビルド設定を調べます。")
        st.json(localized_error_details(error))
    render_student_card(result, mode, st.session_state.hint_step, st.session_state.show_fix)


def render_python_samples(samples) -> None:
    st.selectbox("エラーを選択", ["選択してください"] + [item["title"] for item in samples], key="sample_choice",
                 on_change=load_selected_sample)
    st.button("サンプルを入力", key="load_sample", on_click=load_selected_sample,
              disabled=st.session_state.sample_choice == "選択してください", use_container_width=True)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">&gt;_ エラー学習</div><div class="sidebar-eyebrow">学習スペース</div>', unsafe_allow_html=True)
        st.subheader("サンプルで試す")
        st.caption("よくあるエラーから、読み解く練習を。")
        samples = load_samples()
        if st.session_state.source_language == "Python":
            render_python_samples(samples)
        else:
            st.selectbox(f"{st.session_state.source_language}の練習用エラー", list(EXAMPLE_LABELS),
                         index=None, format_func=EXAMPLE_LABELS.get, key="language_example",
                         on_change=load_language_example, placeholder="練習する内容を選択…")
            with st.expander("Pythonのサンプルへ切り替える"):
                st.caption("以下はPython用です。選ぶと対象言語もPythonに変わります。")
                render_python_samples(samples)
        st.markdown('<div class="sidebar-path"><div><b>1</b>ログとコードを用意する</div><div><b>2</b>エラーの場所を読み解く</div><div><b>3</b>ヒントから考えてみる</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="privacy-note"><b>入力の取り扱い</b>公開版ではログとコードをこのアプリのサーバーへ送り、解析します。入力コードは実行しません。エラー文の保存状況は入力欄の案内を確認してください。任意の人工知能機能だけ、同意後に種類・行番号などの限定情報をOpenAIへ送ります。コード・ログ本文・名前・値は人工知能へ送りません。個人情報やAPIキーは取り除いてから入力してください。</div>', unsafe_allow_html=True)
        st.toggle("動きを減らす", key="reduce_motion", help="このセッションの装飾アニメーションを停止します。OSの「視差効果を減らす」設定にも自動で従います。")
        st.caption("対応：Pythonの18種類のエラー · C/C++のコンパイラ診断と実行時エラー")


def main() -> None:
    st.set_page_config(page_title="エラー学習｜Python・C・C++のエラー解析", page_icon="🔎", layout="wide")
    for key, value in {"hint_step": 0, "show_fix": False, "error_log": "", "source_code": "", "reduce_motion": False, "source_language": "Python"}.items():
        st.session_state.setdefault(key, value)
    ui.apply_theme(st.session_state.reduce_motion)
    st.radio("使う画面", ["学生", "先生"], horizontal=True, key="workspace_role", on_change=switch_workspace)
    if st.session_state.workspace_role == "先生":
        with st.sidebar:
            st.subheader("先生の使い方")
            st.caption("学生が任意に保存した相談カードを受け取り、この画面で読み込んでください。別の利用者の入力やカードは自動表示されません。")
            st.toggle("動きを減らす", key="reduce_motion")
        render_teacher_workspace()
        ui.render_footer()
        return
    render_sidebar()
    ui.render_hero()

    left, right = st.columns([1, 1.06], gap="large")
    with right:
        with st.container(border=True, key="result_panel"):
            result_area = st.empty()
    with left:
        with st.container(border=True, key="input_panel"):
            ui.section_kicker("01", "入力")
            st.subheader("エラーを貼り付ける")
            st.caption("ログだけでも大丈夫。関連コードがあると、もう少し詳しく。")
            language_label = st.selectbox(
                "対象言語", ["Python", "C", "C++"], key="source_language",
                on_change=change_language,
                help="貼り付けたログとソースコードの言語を選んでください。コードは実行しません。",
            )
            language = {"Python": "python", "C": "c", "C++": "cpp"}[language_label]
            if language == "python":
                st.selectbox("エラーを検索して試す", [entry.error_type for entry in ERROR_CATALOG],
                             index=None, key="error_search", placeholder="種類やキーワードで検索… 例：変数、型、文法",
                             format_func=lambda name: CATALOG_BY_TYPE[name].keywords,
                             on_change=load_catalog_example,
                             help="Pythonの18種類のエラーを英語名・日本語で検索できます。選ぶとサンプルを入力します。")
            render_history_notice()
            st.text_area("エラーログ", key="error_log", height=205,
                         placeholder=('Traceback (most recent call last):\n  File "main.py", line 8, in <module>\n    print(user_name)\nNameError: name \'user_name\' is not defined'
                                     if language == "python" else
                                     "main.c:7:10: error: 'total' undeclared identifier\n    printf(\"%d\", total);" if language == "c" else
                                     "main.cpp:7:10: error: ‘total’ was not declared in this scope\n    std::cout << total;"),
                         help=("エラー履歴全体を貼ると、ファイル名と行番号も確認できます。"
                               if language == "python" else
                               "GCC/ClangまたはMSVCの診断出力を貼ると、ファイル名と行番号を確認できます。"),
                         on_change=invalidate_result)
            with st.expander("ソースコード（任意）", expanded=False):
                st.text_area(f"関連する{language_label}コード", key="source_code", height=190,
                             placeholder=("# エラーが起きたファイルのコードを1行目から貼り付けます"
                                          if language == "python" else
                                          "// エラーが起きたファイルのコードを1行目から貼り付けます"),
                             help="行番号を合わせるため、診断に表示されたファイル全体を1行目から貼り付けてください。",
                             on_change=invalidate_result)
            mode = st.radio("表示モード", ["ヒントモード", "通常モード"], horizontal=True,
                            key="display_mode", on_change=reset_hints)
            st.caption("ヒント表示：3段階で考えます。修正例は最後に自分で開けます。")
            if st.button("解析する", type="primary", key="analyze", use_container_width=True):
                invalidate_result()
                log, source = st.session_state.error_log, st.session_state.source_code
                history_attempt = begin_history(log, language) if log.strip() else None
                if not log.strip():
                    st.warning("エラーログを入力してください。検索や左のサンプルからも試せます。")
                elif max(len(log), len(source)) > MAX_INPUT_CHARS:
                    finish_history(history_attempt, "rejected")
                    st.warning("入力が長すぎます。ログとコードはそれぞれ10万文字以内にしてください。")
                else:
                    with result_area.container():
                        ui.render_loading()
                    try:
                        st.session_state.analysis = analyze_error(log, source, language=language)
                        finish_history(history_attempt, "result", st.session_state.analysis)
                    except Exception:
                        finish_history(history_attempt, "failed")
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

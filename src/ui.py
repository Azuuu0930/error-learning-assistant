"""Presentation layer: local styles and escaped, accessible HTML fragments."""

from html import escape
from pathlib import Path

import streamlit as st


ASSETS = Path(__file__).resolve().parents[1] / "assets"


def apply_theme(reduce_motion: bool) -> None:
    css = (ASSETS / "workspace.css").read_text(encoding="utf-8")
    if reduce_motion:
        css += "\n*, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }"
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown('''<div class="workspace-topbar"><span class="wordmark"><span class="brand-mark">&gt;_</span>TRACE<span class="wordmark-light"> / LEARN</span></span><span class="local-status"><i></i> LEARNING WORKSPACE <span class="topbar-python">Python · C/C++</span></span></div>
<section class="hero"><div class="hero-copy"><div class="eyebrow"><span></span> YOUR NEXT STEP STARTS HERE</div><h1>エラーを、<br><span>理解する力に。</span></h1><p>答えを急がず、ひとつずつ。<br class="mobile-break">エラーログから、次の一歩を見つけよう。</p><div class="hero-chips"><span>Python・C・C++に対応</span><span>3段階のヒントで学ぶ</span></div></div><div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="hero-terminal"><div class="terminal-bar"><i></i><i></i><i></i><span>your_learning.py</span></div><div class="terminal-code"><span class="muted">01</span> <span class="code-purple">try</span>:<br><span class="muted">02</span> &nbsp; understand(error)<br><span class="muted">03</span> <span class="code-purple">except</span> Confusion:<br><span class="muted">04</span> &nbsp; take_next_step<span class="code-teal">()</span></div><div class="terminal-note"><span>✓</span> 小さな「わかった」を、積み重ねる。</div></div><div class="floating-symbol">{ }</div></div></section>''', unsafe_allow_html=True)


def section_kicker(number: str, label: str) -> None:
    st.markdown(f'<div class="section-kicker"><span>{escape(number)}</span>{escape(label)}</div>', unsafe_allow_html=True)


def render_empty_state() -> None:
    st.markdown('''<div class="empty-state"><div class="empty-illustration" aria-hidden="true"><div class="empty-ring"></div><svg viewBox="0 0 100 100" fill="none"><rect x="24" y="18" width="52" height="64" rx="12" stroke="currentColor" stroke-width="1.8"/><path d="M37 36h26M37 46h18M37 56h24" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="68" cy="70" r="15" fill="#142c3d" stroke="#52dbc2" stroke-width="1.8"/><path d="m62 70 4 4 8-8" stroke="#52dbc2" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="spark spark-one">+</span><span class="spark spark-two">·</span></div><span class="eyebrow">READY WHEN YOU ARE</span><h3>最初の一歩は、<br>エラーを読むことから。</h3><p>左にログを貼り付けて「解析する」を押すと、<br>場所と読み方を整理できます。</p><div class="empty-steps"><div><b>01</b><span>ログを貼る</span></div><span class="step-connector">→</span><div><b>02</b><span>場所を知る</span></div><span class="step-connector">→</span><div><b>03</b><span>ヒントで考える</span></div></div><div class="empty-tip"><span>TIP</span> 手元にログがなければ、エラー検索から試せます。</div></div>''', unsafe_allow_html=True)


def render_loading() -> None:
    st.markdown('''<div class="analysis-loading" role="status" aria-live="polite" aria-busy="true" data-loading="true"><div class="section-kicker"><span>02</span> ANALYSIS</div><div class="loading-title"><span class="loading-dot"></span>ログとコードを読み解いています</div><p>エラーの種類・場所・考える手がかりを整理しています。</p><div class="skeleton sk-label"></div><div class="skeleton sk-title"></div><div class="skeleton sk-line"></div><div class="skeleton sk-line short"></div><div class="skeleton sk-code"></div><div class="skeleton sk-line"></div><div class="skeleton sk-line short"></div><span class="loading-footnote">コードの実行は行いません</span></div>''', unsafe_allow_html=True)


def result_badges(category: str, has_code: bool) -> None:
    code_label = "コード補助解析あり" if has_code else "ログを解析"
    st.markdown(f'<div class="result-badges"><span class="badge badge-teal">解析完了</span><span class="badge">{escape(category)}</span><span class="badge">{code_label}</span></div>', unsafe_allow_html=True)


def render_hint_progress(step: int) -> None:
    segments = "".join(f'<span class="{ "complete" if index < step else "" }"></span>' for index in range(3))
    st.markdown(f'<div class="hint-progress" role="progressbar" aria-label="確認したヒント" aria-valuemin="0" aria-valuemax="3" aria-valuenow="{step}">{segments}</div>', unsafe_allow_html=True)


def hint_heading(index: int) -> None:
    st.markdown(f'<div class="hint-heading"><span>0{index}</span>ヒント{index}</div>', unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown('<footer class="workspace-footer"><span>TRACE / LEARN</span><span>エラーは、学びの途中にある。</span><span>READ · THINK · LEARN</span></footer>', unsafe_allow_html=True)

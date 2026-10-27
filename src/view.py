"""コード表示用HTML。入力は必ずエスケープして表示する。"""

from html import escape

from src.models import CodeLine


def render_code_context(lines: tuple[CodeLine, ...]) -> str:
    rows = []
    for line in lines:
        # Keep the standalone renderer's original light fallback; the workspace theme overrides it.
        style = "background:#FFF0C2;border-left:4px solid #BA7900;" if line.is_error else "border-left:4px solid transparent;"
        marker = "▶" if line.is_error else " "
        rows.append(
            f'<div class="trace-code-row{ " trace-code-error" if line.is_error else "" }" style="{style}padding:4px 12px;white-space:pre;">'
            f'<span style="color:#7f9eb4;">{marker} {line.number:>4} | </span>{escape(line.text)}</div>'
        )
    # pre/code配下のdivはStreamlitのMarkdownコード表示で文字列化される。
    # 通常のdivとwhite-space:preで、行ごとのHTML強調を維持する。
    return ('<div class="trace-code-context" role="region" aria-label="該当行と前後のコード" '
            'style="overflow-x:auto;padding:14px 0;border-radius:10px;border:1px solid #294154;background:#0b1727;'
            'color:#d3e2ef;font-size:12px;line-height:1.85;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;">'
            + "".join(rows) + "</div>")

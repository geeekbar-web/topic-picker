"""Render Markdown reports into self-contained, mobile-friendly HTML."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import markdown


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #0f0f14;
  --bg-card: #1a1a23;
  --border: #2a2a3a;
  --text: #e8e8f0;
  --text-dim: #9999aa;
  --accent: #ff4757;
  --accent2: #ff6b81;
  --gold: #ffd700;
  --green: #4ade80;
  --blue: #60a5fa;
  --purple: #c084fc;
  --tag-bg: #2d2d40;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC",
               "Hiragino Sans GB", "Microsoft YaHei", "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  padding: 20px 16px 60px;
  max-width: 920px;
  margin: 0 auto;
}}
.back {{
  display: inline-block; color: var(--text-dim); text-decoration: none;
  font-size: 13px; margin-bottom: 16px;
}}
.back:hover {{ color: var(--accent); }}
h1 {{
  font-size: 28px; margin-bottom: 6px;
  background: linear-gradient(135deg, #ff4757 0%, #ff6b81 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.day-summary {{
  color: var(--text-dim); font-size: 14px; margin-bottom: 28px;
  padding: 10px 14px; background: var(--bg-card); border-radius: 8px;
  border-left: 3px solid var(--accent);
}}
h2 {{
  font-size: 20px; margin: 36px 0 14px; padding-top: 18px;
  border-top: 1px solid var(--border);
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}}
blockquote {{
  background: var(--bg-card);
  border-left: 3px solid var(--accent);
  padding: 10px 14px; margin: 12px 0; border-radius: 0 6px 6px 0;
}}
h2 code, p code {{ background: var(--tag-bg); padding: 2px 6px; border-radius: 4px;
                    font-size: 13px; }}
a {{ color: var(--blue); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
ul, ol {{ margin: 8px 0 8px 24px; }}
li {{ margin: 4px 0; }}
strong {{ color: var(--gold); }}
.section-hook blockquote {{
  background: linear-gradient(135deg, rgba(255,71,87,0.15), rgba(255,107,129,0.05));
  border-left-color: var(--accent); font-style: italic; font-size: 16px;
}}
.section-visual blockquote {{
  border-left-color: var(--purple); color: var(--purple);
  background: rgba(192, 132, 252, 0.08);
}}
.section-cta blockquote {{
  border-left-color: var(--green); color: var(--green);
  background: rgba(74, 222, 128, 0.08); font-weight: 600;
}}
hr {{ border: none; border-top: 1px solid var(--border); margin: 30px 0; }}
footer {{
  margin-top: 50px; padding-top: 20px; border-top: 1px solid var(--border);
  text-align: center; color: var(--text-dim); font-size: 12px;
}}
.report-list {{ list-style: none; padding: 0; }}
.report-list a {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; background: var(--bg-card); border-radius: 8px;
  border: 1px solid var(--border); margin: 6px 0; color: var(--text);
  text-decoration: none;
}}
.report-list a:hover {{ border-color: var(--accent); transform: translateX(4px); }}
.report-list .date {{ font-size: 16px; font-weight: 600; }}
.report-list .weekday {{ color: var(--text-dim); font-size: 13px; }}
</style>
</head>
<body>
{back_link}
{body}
<footer>由 topic-picker 自动生成 · 每天 8:00 (UTC+8) 刷新</footer>
</body>
</html>"""


def render(md_path: Path) -> str:
    md_text = md_path.read_text(encoding="utf-8")
    date = md_path.stem
    html_body = markdown.markdown(
        md_text, extensions=["fenced_code", "tables", "sane_lists"],
    )
    section_classes = {
        "🎯 Hook": "section-hook",
        "📖 背景":  "section-bg",
        "💡 三个角度": "section-angles",
        "🎥 视觉": "section-visual",
        "⏱️ 60 秒": "section-timing",
        "💬 CTA":  "section-cta",
    }
    for label, cls in section_classes.items():
        html_body = html_body.replace(
            f"<h3>{label}", f'<h3 class="{cls}">{label}',
        )
    title = f"选题包 · {date}"
    back_link = '<a class="back" href="./">← 返回所有报告</a>'
    return HTML_TEMPLATE.format(title=title, body=html_body, back_link=back_link)


def render_index(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(out_dir.glob("????-??-??.html"), reverse=True)
    items_html = ""
    for f in files:
        date = f.stem
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]
        except ValueError:
            weekday = ""
        items_html += (
            f'<li><a href="{date}.html">'
            f'<span class="date">{date}</span>'
            f'<span class="weekday">{weekday}</span>'
            f'</a></li>'
        )
    if not items_html:
        items_html = '<li>还没有任何报告,等待第一次自动抓取...</li>'
    body = f"""<h1>🔥 1 分钟短视频选题</h1>
<p class="day-summary">每天 8:00 (UTC+8) 自动更新 · 微博/抖音/知乎/百度/贴吧/B站/GitHub 飙升榜</p>
<h2>📅 历史报告</h2>
<ul class="report-list">{items_html}</ul>"""
    return HTML_TEMPLATE.format(
        title="🔥 短视频选题 Dashboard", body=body, back_link="",
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3.11 html_render.py <input.md> [output.html]")
        print("       python3.11 html_render.py --index <output_dir>")
        sys.exit(1)
    if sys.argv[1] == "--index":
        out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("public")
        out = render_index(out_dir)
        out.write_text(out, encoding="utf-8")
        print(f"[index] -> {out}")
        return
    src = Path(sys.argv[1])
    if len(sys.argv) > 2:
        dst = Path(sys.argv[2])
    else:
        dst = src.with_suffix(".html")
    html = render(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(html, encoding="utf-8")
    print(f"[render] {src} -> {dst}  ({len(html)} chars)")


if __name__ == "__&#8203;main__":
    main()

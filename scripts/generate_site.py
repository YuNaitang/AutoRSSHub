#!/usr/bin/env python3
"""从 articles.json 生成 index.html 和 summary.json"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# ---- 路径 ----
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
TEMPLATE_DIR = ROOT / "templates"
PUBLIC_DIR = ROOT / "public"

LOOKBACK_HOURS = 24

# ---- HTML 模板（内联备选，当模板文件不存在时使用） ----
FALLBACK_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RSS 阅读器</title>
<style>
  :root { --bg: #0d1117; --card: #161b22; --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff; --border: #30363d; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height:1.6; padding:2rem; max-width:800px; margin:0 auto; }
  header { margin-bottom:2rem; padding-bottom:1rem; border-bottom:1px solid var(--border); }
  header h1 { font-size:1.5rem; color:var(--accent); }
  header p { color:var(--muted); font-size:0.875rem; margin-top:0.25rem; }
  article { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:1.25rem; margin-bottom:1rem; }
  article h2 { font-size:1.1rem; margin-bottom:0.25rem; }
  article h2 a { color:var(--accent); text-decoration:none; }
  article h2 a:hover { text-decoration:underline; }
  .meta { font-size:0.8rem; color:var(--muted); margin-bottom:0.75rem; }
  .meta span { margin-right:0.75rem; }
  .summary { font-size:0.9rem; color:var(--text); margin-bottom:0.5rem; }
  .content { font-size:0.85rem; color:var(--muted); max-height:12em; overflow:hidden; position:relative; }
  .content::after { content:''; position:absolute; bottom:0; left:0; right:0; height:3em; background:linear-gradient(transparent, var(--card)); }
  .sources { margin-top:2rem; padding-top:1rem; border-top:1px solid var(--border); font-size:0.75rem; color:var(--muted); }
  .empty { text-align:center; padding:3rem; color:var(--muted); }
  footer { margin-top:3rem; text-align:center; font-size:0.75rem; color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>RSS 阅读器</h1>
  <p>最近 {{ period }} 小时更新 · 共 {{ count }} 篇 · 生成于 {{ generated_at }}</p>
</header>
<main>
{% if articles %}
  {% for a in articles %}
  <article>
    <h2><a href="{{ a.link or '#' }}" target="_blank" rel="noopener">{{ a.title }}</a></h2>
    <div class="meta">
      <span>来源: {{ a.source_name }}</span>
      <span>{{ a.published[:16] if a.published else '' }}</span>
    </div>
    {% if a.summary %}<div class="summary">{{ a.summary[:300] }}</div>{% endif %}
    {% if a.content %}<div class="content">{{ a.content[:600] }}</div>{% endif %}
  </article>
  {% endfor %}
{% else %}
  <div class="empty">暂无最近 {{ period }} 小时的文章</div>
{% endif %}
</main>
<footer>
  <p>自动生成 · 每小时更新 · <a href="summary.json">AI 助理端点</a></p>
</footer>
</body>
</html>"""


def load_articles() -> list:
    if not ARTICLES_FILE.exists():
        return []
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("articles", {}).values())


def source_name(url: str) -> str:
    """从 URL 中提取简短来源名"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return url[:40]


def generate_html(articles: list, template_env=None):
    """生成 index.html"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    recent = [
        a for a in articles
        if datetime.fromisoformat(a["published"]).replace(tzinfo=timezone.utc) >= cutoff
    ]
    recent.sort(key=lambda x: x["published"], reverse=True)

    # 为模板准备数据
    for a in recent:
        a["source_name"] = source_name(a.get("source", ""))

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if template_env:
        tmpl = template_env.get_template("index.html.j2")
        html = tmpl.render(
            articles=recent,
            period=LOOKBACK_HOURS,
            count=len(recent),
            generated_at=generated_at
        )
    else:
        from jinja2 import Template
        tmpl = Template(FALLBACK_TEMPLATE)
        html = tmpl.render(
            articles=recent,
            period=LOOKBACK_HOURS,
            count=len(recent),
            generated_at=generated_at
        )

    # 写入
    index_path = PUBLIC_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] 已生成 {index_path} ({len(recent)} 篇文章)")

    return recent


def generate_summary(articles: list):
    """生成 AI 助理端点 summary.json"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    recent = [
        a for a in articles
        if datetime.fromisoformat(a["published"]).replace(tzinfo=timezone.utc) >= cutoff
    ]
    recent.sort(key=lambda x: x["published"], reverse=True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_hours": LOOKBACK_HOURS,
        "total_articles": len(recent),
        "articles": []
    }

    for a in recent:
        summary["articles"].append({
            "title": a["title"],
            "link": a.get("link", ""),
            "source": a.get("source", ""),
            "published": a.get("published", ""),
            "summary": a.get("summary", "")[:300],
            "content_preview": a.get("content", "")[:500],
        })

    summary_path = PUBLIC_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 已生成 {summary_path}")


def main():
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # 尝试加载 Jinja2 模板
    template_env = None
    if (TEMPLATE_DIR / "index.html.j2").exists():
        template_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    articles = load_articles()
    print(f"[INFO] 已加载 {len(articles)} 篇文章")

    generate_html(articles, template_env)
    generate_summary(articles)
    print("[INFO] 站点生成完成")


if __name__ == "__main__":
    main()
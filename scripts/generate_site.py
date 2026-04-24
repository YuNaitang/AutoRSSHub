#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.opml"
DATA_DIR = ROOT / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
TEMPLATE_DIR = ROOT / "templates"
PUBLIC_DIR = ROOT / "public"

LOOKBACK_HOURS = 24

# 内联备选模板（当 Jinja2 模板文件缺失时使用）
FALLBACK_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RSS 阅读器</title>
<style>
  :root { --bg: #0d1117; --card: #161b22; --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff; --border: #30363d; --sidebar-bg: #0d1117; --sidebar-width: 260px; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height:1.6; display:flex; }
  .sidebar { width:var(--sidebar-width); background:var(--bg); border-right:1px solid var(--border); padding:1.5rem; position:fixed; top:0; left:0; bottom:0; overflow-y:auto; }
  .sidebar h2 { font-size:1.2rem; color:var(--accent); margin-bottom:1rem; }
  .sidebar .tools { margin-bottom:1rem; display:flex; gap:0.5rem; }
  .sidebar .tools button { background:var(--card); border:1px solid var(--border); color:var(--text); padding:0.3rem 0.6rem; font-size:0.75rem; border-radius:4px; cursor:pointer; }
  .sidebar .tools button:hover { background:var(--border); }
  .source-item { display:flex; align-items:center; margin-bottom:0.5rem; font-size:0.85rem; }
  .source-item input[type="checkbox"] { margin-right:0.5rem; }
  .main { margin-left:var(--sidebar-width); padding:2rem; flex:1; max-width:800px; }
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
  .empty { text-align:center; padding:3rem; color:var(--muted); }
  footer { margin-top:3rem; text-align:center; font-size:0.75rem; color:var(--muted); }
  footer a { color:var(--accent); }
  @media (max-width: 768px) {
    body { flex-direction:column; }
    .sidebar { position:relative; width:100%; border-right:none; border-bottom:1px solid var(--border); padding:1rem; }
    .main { margin-left:0; padding:1rem; }
  }
</style>
</head>
<body>
<div class="sidebar">
  <h2>RSS 源</h2>
  <div class="tools">
    <button onclick="selectAll()">全选</button>
    <button onclick="deselectAll()">反选</button>
  </div>
  <div id="source-list"></div>
</div>
<main class="main">
  <header>
    <h1>RSS 阅读器</h1>
    <p>最近 {{ period }} 小时 · 共 <span id="total-count">{{ count }}</span> 篇 · 生成于 {{ generated_at }}</p>
  </header>
  <div id="articles-container">
    {% for a in articles %}
    <article class="feed-article" data-source="{{ a.source_name }}">
      <h2><a href="{{ a.link or '#' }}" target="_blank" rel="noopener">{{ a.title }}</a></h2>
      <div class="meta">
        <span>来源: {{ a.source_name }}</span>
        <span>{{ a.published[:16] if a.published else '' }}</span>
      </div>
      {% if a.summary %}<div class="summary">{{ a.summary[:300] }}</div>{% endif %}
      {% if a.content %}<div class="content">{{ a.content[:600] }}</div>{% endif %}
    </article>
    {% endfor %}
    {% if not articles %}
    <div class="empty" id="empty-msg">暂无最近 {{ period }} 小时的文章</div>
    {% endif %}
  </div>
  <footer>
    <p>自动生成 · 每小时更新 · <a href="summary.json">AI 助理端点</a></p>
  </footer>
</main>
<script>
  // 从 sources.json 加载侧边栏
  fetch('sources.json')
    .then(res => res.json())
    .then(sources => {
      const container = document.getElementById('source-list');
      sources.forEach(s => {
        const div = document.createElement('div');
        div.className = 'source-item';
        div.innerHTML = `<input type="checkbox" id="src-${s.id}" checked onchange="filterArticles()" data-source="${s.name}">
                         <label for="src-${s.id}">${s.name}</label>`;
        container.appendChild(div);
      });
    });

  function filterArticles() {
    const checkboxes = document.querySelectorAll('#source-list input[type="checkbox"]');
    const visibleSources = new Set();
    checkboxes.forEach(cb => { if (cb.checked) visibleSources.add(cb.dataset.source); });

    let visibleCount = 0;
    document.querySelectorAll('.feed-article').forEach(article => {
      const source = article.dataset.source;
      if (visibleSources.has(source)) {
        article.style.display = '';
        visibleCount++;
      } else {
        article.style.display = 'none';
      }
    });
    document.getElementById('total-count').textContent = visibleCount;
    const emptyMsg = document.getElementById('empty-msg');
    if (emptyMsg) {
      emptyMsg.style.display = visibleCount === 0 ? '' : 'none';
    }
  }

  function selectAll() {
    document.querySelectorAll('#source-list input[type="checkbox"]').forEach(cb => cb.checked = true);
    filterArticles();
  }
  function deselectAll() {
    document.querySelectorAll('#source-list input[type="checkbox"]').forEach(cb => cb.checked = false);
    filterArticles();
  }
</script>
</body>
</html>'''


def load_articles() -> list:
    if not ARTICLES_FILE.exists():
        return []
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("articles", {}).values())


def load_sources() -> list[dict]:
    """从 OPML 提取源信息，并分配 id"""
    if not SOURCES_FILE.exists():
        return []
    tree = ET.parse(SOURCES_FILE)
    sources = []
    for i, outline in enumerate(tree.iter("outline")):
        name = outline.get("title") or outline.get("text") or "未命名"
        xml_url = outline.get("xmlUrl") or ""
        sources.append({"id": i, "name": name, "url": xml_url})
    return sources


def generate_sources_json(sources: list):
    """生成 sources.json 供前端加载"""
    with open(PUBLIC_DIR / "sources.json", "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def generate_html(articles: list, sources: list, template_env=None):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    recent = [
        a for a in articles
        if datetime.fromisoformat(a["published"]).replace(tzinfo=timezone.utc) >= cutoff
    ]
    recent.sort(key=lambda x: x["published"], reverse=True)

    # 为模板准备 source_name 字段（显示用名称）
    source_map = {s["url"]: s["name"] for s in sources}
    for a in recent:
        a["source_name"] = source_map.get(a.get("source_url", ""), a.get("source", "未知"))

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

    with open(PUBLIC_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] 已生成 index.html ({len(recent)} 篇文章)")


def generate_summary(articles: list):
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
            "source_url": a.get("source_url", ""),
            "published": a.get("published", ""),
            "summary": a.get("summary", "")[:300],
            "content_preview": a.get("content", "")[:500],
        })
    with open(PUBLIC_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 已生成 summary.json")


def main():
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    sources = load_sources()
    generate_sources_json(sources)

    articles = load_articles()
    print(f"[INFO] 已加载 {len(articles)} 篇文章")

    # 尝试载入 Jinja2 模板
    template_env = None
    if (TEMPLATE_DIR / "index.html.j2").exists():
        template_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    generate_html(articles, sources, template_env)
    generate_summary(articles)
    print("[INFO] 站点生成完成")


if __name__ == "__main__":
    main()
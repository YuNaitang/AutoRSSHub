#!/usr/bin/env python3
"""从 articles.json 生成 index.html、summary.json 和 sources.json（支持嵌套分类）"""

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

# 内联备选模板（当 Jinja2 模板文件缺失时使用）— 此处精简，仅作兜底
FALLBACK_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>RSS 阅读器</title>
<style>
  :root { --bg: #1e1e2e; --card: #313244; --text: #cdd6f4; --muted: #a6adc8; --accent: #89b4fa; --border: #45475a; --sidebar-width:260px; }
  body { font-family: sans-serif; background:var(--bg); color:var(--text); display:flex; }
  .sidebar { width:var(--sidebar-width); background:var(--bg); border-right:1px solid var(--border); padding:1rem; position:fixed; height:100%; overflow-y:auto; }
  .main { margin-left:var(--sidebar-width); padding:2rem; max-width:800px; }
  article { background:var(--card); border:1px solid var(--border); padding:1rem; margin-bottom:1rem; border-radius:8px; }
</style>
</head>
<body>
<div class="sidebar"><h2>源</h2><div id="source-list"></div></div>
<main class="main"><div id="articles-container">{% for a in articles %}<article>{{ a.title }}</article>{% endfor %}</div></main>
<script>
  fetch('sources.json').then(r=>r.json()).then(sources=>{
    function build(nodes, container) {
      nodes.forEach(n => {
        if(n.type==='folder') {
          let details = document.createElement('details');
          details.innerHTML = `<summary>${n.name}</summary>`;
          let inner = document.createElement('div');
          details.appendChild(inner);
          build(n.children, inner);
          container.appendChild(details);
        } else {
          container.innerHTML += `<div><input type="checkbox" checked> ${n.name}</div>`;
        }
      });
    }
    build(sources, document.getElementById('source-list'));
  });
</script>
</body>
</html>'''


def load_articles() -> list:
    if not ARTICLES_FILE.exists():
        return []
    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("articles", {}).values())


def load_source_tree() -> list[dict]:
    """解析 OPML，返回递归树结构（folder 和 source 节点）"""
    if not SOURCES_FILE.exists():
        return []

    tree = ET.parse(SOURCES_FILE)
    root = tree.getroot()
    source_id = 0

    def parse_node(node):
        nonlocal source_id
        title = node.get("title") or node.get("text") or "未命名"
        xml_url = node.get("xmlUrl")
        children_nodes = node.findall("outline")

        if xml_url:
            # 叶子源
            source_id += 1
            return {"type": "source", "id": source_id, "name": title.strip(), "url": xml_url.strip()}
        elif children_nodes:
            # 分类文件夹
            folder = {"type": "folder", "name": title.strip(), "children": []}
            for child in children_nodes:
                child_node = parse_node(child)
                if child_node:
                    folder["children"].append(child_node)
            return folder
        else:
            # 空文件夹或无xmlUrl且无子节点，忽略
            return None

    body = root.find("body")
    if body is None:
        return []
    sources = []
    for outline in body.findall("outline"):
        parsed = parse_node(outline)
        if parsed:
            sources.append(parsed)
    return sources


def generate_sources_json(sources: list):
    """生成 sources.json （树形结构）"""
    with open(PUBLIC_DIR / "sources.json", "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def flatten_sources(tree) -> dict:
    """从树中提取 url->name 映射"""
    mapping = {}
    def walk(nodes):
        for node in nodes:
            if node["type"] == "source":
                mapping[node["url"]] = node["name"]
            elif node["type"] == "folder":
                walk(node.get("children", []))
    walk(tree)
    return mapping


def generate_html(articles: list, source_tree: list, template_env=None):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    recent = [
        a for a in articles
        if datetime.fromisoformat(a["published"]).replace(tzinfo=timezone.utc) >= cutoff
    ]
    recent.sort(key=lambda x: x["published"], reverse=True)

    # 为文章分配显示用的 source_name（优先用 OPML 中的 name）
    url_to_name = flatten_sources(source_tree)
    for a in recent:
        # 如果已有 source 字段且与 url 映射不同，则覆盖？保留 article 中保存的 source 作为首选（fetch时写入的名称）
        # 但为了侧边栏过滤一致，我们使用 fetch 时写入的 source 名称，它已来自 OPML
        pass

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

    source_tree = load_source_tree()
    generate_sources_json(source_tree)

    articles = load_articles()
    print(f"[INFO] 已加载 {len(articles)} 篇文章")

    template_env = None
    if (TEMPLATE_DIR / "index.html.j2").exists():
        template_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    generate_html(articles, source_tree, template_env)
    generate_summary(articles)
    print("[INFO] 站点生成完成")


if __name__ == "__main__":
    main()
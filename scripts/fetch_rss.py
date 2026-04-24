#!/usr/bin/env python3
"""RSS 抓取：从 sources.opml 读取（支持嵌套分类） > 解析 > 去重 > 全文拉取 > 存入 articles.json"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import feedparser
import trafilatura
from dateutil import parser as dateparser

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.opml"
DATA_DIR = ROOT / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
PUBLIC_DIR = ROOT / "public"
FEED_DIR = PUBLIC_DIR / "feed"

REQUEST_TIMEOUT = 30
FULLTEXT_TIMEOUT = 15
LOOKBACK_HOURS = 24
MAX_ARTICLES = 50000


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FEED_DIR.mkdir(parents=True, exist_ok=True)


def load_articles() -> dict:
    if ARTICLES_FILE.exists():
        try:
            with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("articles", {})
        except (json.JSONDecodeError, KeyError):
            print("[WARN] articles.json 损坏，将重新初始化")
    return {}


def save_articles(articles: dict):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "count": len(articles),
            "articles": articles
        }, f, ensure_ascii=False, indent=2)


def load_sources() -> list[dict]:
    """递归解析 sources.opml，返回所有 RSS 源（扁平列表，带分类路径）"""
    if not SOURCES_FILE.exists():
        print(f"[ERROR] 未找到 {SOURCES_FILE}，请先创建 OPML 文件")
        sys.exit(1)

    try:
        tree = ET.parse(SOURCES_FILE)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"[ERROR] OPML 解析失败: {e}")
        sys.exit(1)

    sources = []

    def walk(node, category=""):
        # 节点的 text/title 可作为分类名或源名
        title = node.get("title") or node.get("text") or ""
        xml_url = node.get("xmlUrl")
        if xml_url:
            # 这是一个叶子源
            name = title.strip() or xml_url.split("//")[-1].split("/")[0]
            sources.append({
                "name": name,
                "url": xml_url.strip(),
                "category": category
            })
        else:
            # 可能是分类文件夹，继续递归子节点，标题作为新分类
            new_category = title.strip() if title.strip() else category
            for child in node.findall("outline"):
                walk(child, new_category)

    # 从 body 的直接子 outline 开始
    body = root.find("body")
    if body is not None:
        for outline in body.findall("outline"):
            walk(outline)
    else:
        print("[WARN] OPML 缺少 <body> 节点")

    if not sources:
        print("[ERROR] OPML 中未找到任何有效 RSS 源 (需要 xmlUrl)")
        sys.exit(1)

    print(f"[INFO] 从 OPML 加载 {len(sources)} 个源")
    return sources


def make_key(link: str, title: str, published: str) -> str:
    if link:
        return link.strip()
    raw = f"{title}|{published}".encode("utf-8")
    return "hash:" + hashlib.sha256(raw).hexdigest()[:16]


def fetch_full_text(link: str) -> str:
    try:
        downloaded = trafilatura.fetch_url(link, timeout=FULLTEXT_TIMEOUT)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, favor_precision=True, include_formatting=False)
        return text.strip() if text else ""
    except Exception:
        return ""


def clean_summary(entry) -> str:
    if hasattr(entry, "summary"):
        return entry.summary
    if hasattr(entry, "content"):
        for c in entry.content:
            if c.get("value"):
                return c.value
    return ""


def parse_published(entry) -> datetime:
    for attr in ["published_parsed", "updated_parsed", "published", "updated"]:
        val = getattr(entry, attr, None)
        if val:
            try:
                if hasattr(val, "tm_year"):
                    return datetime(*val[:6], tzinfo=timezone.utc)
                return dateparser.parse(val).replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)


def main():
    ensure_dirs()
    articles = load_articles()
    sources = load_sources()

    print(f"[INFO] 历史去重库: {len(articles)} 条")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    new_total = 0
    recent_articles = []

    for src in sources:
        name = src["name"]
        url = src["url"]
        category = src.get("category", "")
        print(f"\n--- {name} ({url})" + (f" [分类: {category}]" if category else ""))
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[WARN] 解析失败: {e}")
            continue
        if feed.bozo and not feed.entries:
            print(f"[WARN] 源可能无效: {feed.bozo_exception}")
            continue

        print(f"[INFO] {len(feed.entries)} 个条目")
        for entry in feed.entries:
            link = getattr(entry, "link", "")
            title = getattr(entry, "title", "(无标题)")
            published_dt = parse_published(entry)
            key = make_key(link, title, published_dt.isoformat())
            if key in articles:
                continue
            print(f"  [NEW] {title[:60]}...")
            full_text = ""
            if link:
                full_text = fetch_full_text(link)
                if full_text:
                    print(f"      全文 ({len(full_text)} 字符)")
                else:
                    print(f"      全文失败，使用摘要")
            summary = clean_summary(entry)

            article = {
                "title": title,
                "link": link,
                "source": name,           # 显示用名称
                "source_url": url,
                "category": category,     # 所属分类
                "published": published_dt.isoformat(),
                "summary": summary,
                "content": full_text or summary,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }
            articles[key] = article
            new_total += 1
            if published_dt >= cutoff:
                recent_articles.append(article)

    # 清理过期
    if len(articles) > MAX_ARTICLES:
        print(f"\n[INFO] 文章数 {len(articles)} > {MAX_ARTICLES}，清理中...")
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        articles = {
            k: v for k, v in articles.items()
            if dateparser.parse(v["fetched_at"]).replace(tzinfo=timezone.utc) > threshold
        }
        print(f"[INFO] 清理后保留 {len(articles)} 条")

    save_articles(articles)

    # 今日即时输出
    today_file = FEED_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    existing_today = []
    if today_file.exists():
        try:
            with open(today_file, "r", encoding="utf-8") as f:
                existing_today = json.load(f)
        except Exception:
            pass
    all_today = existing_today + recent_articles
    with open(today_file, "w", encoding="utf-8") as f:
        json.dump(all_today, f, ensure_ascii=False, indent=2)

    print(f"\n===== 完成 =====")
    print(f"新增: {new_total} 篇")
    print(f"最近 {LOOKBACK_HOURS}h: {len(recent_articles)} 篇")
    print(f"去重库总计: {len(articles)} 篇")


if __name__ == "__main__":
    main()
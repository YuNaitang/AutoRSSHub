#!/usr/bin/env python3
"""RSS 抓取脚本：解析源 -> 去重 -> 全文拉取 -> 存入 articles.json"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import trafilatura
from dateutil import parser as dateparser

# ---- 路径配置 ----
ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.txt"
DATA_DIR = ROOT / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
PUBLIC_DIR = ROOT / "public"
FEED_DIR = PUBLIC_DIR / "feed"

# ---- 常量 ----
REQUEST_TIMEOUT = 30          # RSS 源请求超时
FULLTEXT_TIMEOUT = 15         # 全文抓取单篇超时
LOOKBACK_HOURS = 24           # 即时输出窗口
MAX_ARTICLES = 50000          # 去重库最大条目数，超出则清理最旧 30 天


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


def load_sources() -> list[str]:
    if not SOURCES_FILE.exists():
        print(f"[ERROR] 未找到 {SOURCES_FILE}，请先创建并填入 RSS 源 URL")
        sys.exit(1)
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def make_key(link: str, title: str, published: str) -> str:
    """为去重生成唯一键：优先用 link，否则用 title+published 哈希"""
    if link:
        return link.strip()
    raw = f"{title}|{published}".encode("utf-8")
    return "hash:" + hashlib.sha256(raw).hexdigest()[:16]


def fetch_full_text(link: str) -> str:
    """用 trafilatura 抓取正文，失败返回空字符串"""
    try:
        downloaded = trafilatura.fetch_url(link, timeout=FULLTEXT_TIMEOUT)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, favor_precision=True, include_formatting=False)
        return text.strip() if text else ""
    except Exception:
        return ""


def clean_summary(entry) -> str:
    """从 feed 条目中提取摘要"""
    if hasattr(entry, "summary"):
        return entry.summary
    if hasattr(entry, "content"):
        for c in entry.content:
            if c.get("value"):
                return c.value
    return ""


def parse_published(entry) -> datetime:
    """解析发布时间，失败返回当前时间"""
    for attr in ["published_parsed", "updated_parsed", "published", "updated"]:
        val = getattr(entry, attr, None)
        if val:
            try:
                if hasattr(val, "tm_year"):  # time.struct_time
                    return datetime(*val[:6], tzinfo=timezone.utc)
                return dateparser.parse(val).replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)


def main():
    ensure_dirs()
    articles = load_articles()
    sources = load_sources()

    print(f"[INFO] 已加载 {len(articles)} 条历史记录")
    print(f"[INFO] 待抓取 {len(sources)} 个 RSS 源")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    new_this_run = 0
    recent_articles = []

    for src_url in sources:
        print(f"\n--- 处理源: {src_url} ---")
        try:
            feed = feedparser.parse(src_url)
        except Exception as e:
            print(f"[WARN] 解析失败: {e}")
            continue

        if feed.bozo and not feed.entries:
            print(f"[WARN] 源可能无效或无条目: {feed.bozo_exception}")
            continue

        print(f"[INFO] 共 {len(feed.entries)} 个条目")

        for entry in feed.entries:
            link = getattr(entry, "link", "")
            title = getattr(entry, "title", "(无标题)")
            published_dt = parse_published(entry)
            key = make_key(link, title, published_dt.isoformat())

            if key in articles:
                continue  # 已存在，跳过

            print(f"  [NEW] {title[:60]}...")

            # 全文抓取
            full_text = ""
            if link:
                full_text = fetch_full_text(link)
                if full_text:
                    print(f"      全文获取成功 ({len(full_text)} 字符)")
                else:
                    print(f"      全文获取失败，使用摘要")
            summary = clean_summary(entry)

            article = {
                "title": title,
                "link": link,
                "source": src_url,
                "published": published_dt.isoformat(),
                "summary": summary,
                "content": full_text or summary,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }
            articles[key] = article
            new_this_run += 1

            if published_dt >= cutoff:
                recent_articles.append(article)

    # 清理过期历史（超出上限时保留最近 30 天）
    if len(articles) > MAX_ARTICLES:
        print(f"\n[INFO] 条数 {len(articles)} > {MAX_ARTICLES}，清理中...")
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        articles = {
            k: v for k, v in articles.items()
            if dateparser.parse(v["fetched_at"]).replace(tzinfo=timezone.utc) > threshold
        }
        print(f"[INFO] 清理后保留 {len(articles)} 条")

    save_articles(articles)

    # 写入即时输出供页面生成使用
    today_file = FEED_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    # 合并已有今日记录 + 新抓的
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

    print(f"\n===== 本轮完成 =====")
    print(f"新增: {new_this_run} 篇")
    print(f"最近 {LOOKBACK_HOURS}h: {len(recent_articles)} 篇")
    print(f"去重库总计: {len(articles)} 篇")


if __name__ == "__main__":
    main()
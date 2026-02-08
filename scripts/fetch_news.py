"""
fetch_news.py -- ニュースソースから記事を取得して JSON に保存する
Usage:
    python scripts/fetch_news.py morning
    python scripts/fetch_news.py evening
"""

import argparse
import json
import sys
from datetime import datetime

import feedparser
import requests

from config import (
    DRAFTS_DIR,
    JST,
    ensure_dirs,
    load_sources,
    logger,
)

# ---------------------------------------------------------------------------
# Hacker News API helpers
# ---------------------------------------------------------------------------
HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


def _fetch_hackernews(max_items: int) -> list[dict]:
    """Hacker News API から上位記事を取得する。"""
    articles: list[dict] = []
    try:
        resp = requests.get(HN_TOP_STORIES_URL, timeout=15)
        resp.raise_for_status()
        story_ids: list[int] = resp.json()[:max_items]
    except Exception as exc:
        logger.error("Hacker News top stories の取得に失敗: %s", exc)
        return articles

    for story_id in story_ids:
        try:
            item_resp = requests.get(
                HN_ITEM_URL.format(id=story_id), timeout=10
            )
            item_resp.raise_for_status()
            item = item_resp.json()
            if item is None:
                continue
            articles.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "summary": "",
                    "source": "Hacker News",
                    "category": "Tech General",
                    "fetched_at": datetime.now(JST).isoformat(),
                }
            )
        except Exception as exc:
            logger.warning("HN item %s の取得に失敗: %s", story_id, exc)
            continue

    return articles


# ---------------------------------------------------------------------------
# RSS helpers
# ---------------------------------------------------------------------------
def _fetch_rss(source: dict) -> list[dict]:
    """RSS フィードからニュース記事を取得する。"""
    articles: list[dict] = []
    name = source["name"]
    url = source["url"]
    max_items = source.get("max_items", 5)
    categories = source.get("categories", [])
    category = categories[0] if categories else "General"

    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning("%s: フィードの解析に問題あり (%s)", name, feed.bozo_exception)
            return articles

        for entry in feed.entries[:max_items]:
            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary[:300]
            elif hasattr(entry, "description"):
                summary = entry.description[:300]

            articles.append(
                {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": summary,
                    "source": name,
                    "category": category,
                    "fetched_at": datetime.now(JST).isoformat(),
                }
            )
    except Exception as exc:
        logger.error("%s の RSS 取得に失敗: %s", name, exc)

    return articles


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
def main(session_type: str) -> str:
    """
    ニュースを取得して JSON ファイルに保存する。

    Args:
        session_type: "morning" or "evening"

    Returns:
        保存先ファイルパス (文字列)
    """
    if session_type not in ("morning", "evening"):
        raise ValueError(f"session_type は 'morning' または 'evening' を指定: {session_type}")

    ensure_dirs()
    sources_cfg = load_sources()
    sources = sources_cfg.get("sources", [])

    all_articles: list[dict] = []

    for source in sources:
        name = source.get("name", "unknown")
        src_type = source.get("type", "rss")
        logger.info("取得中: %s (type=%s)", name, src_type)

        if src_type == "api" and "hacker-news" in source.get("url", ""):
            articles = _fetch_hackernews(source.get("max_items", 5))
        elif src_type == "rss":
            articles = _fetch_rss(source)
        else:
            logger.warning("未対応のソースタイプ: %s (%s)", src_type, name)
            continue

        logger.info("  -> %d 件取得", len(articles))
        all_articles.extend(articles)

    # 保存
    today = datetime.now(JST).strftime("%Y-%m-%d")
    out_path = DRAFTS_DIR / f"news_{session_type}_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    logger.info("合計 %d 件を保存: %s", len(all_articles), out_path)
    return str(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ニュースソースから記事を取得する")
    parser.add_argument(
        "session_type",
        choices=["morning", "evening"],
        help="セッション種別 (morning / evening)",
    )
    args = parser.parse_args()

    try:
        result_path = main(args.session_type)
        print(f"完了: {result_path}")
    except Exception as e:
        logger.exception("ニュース取得中にエラーが発生しました")
        sys.exit(1)

"""
test_fetch_news.py -- fetch_news.py のテスト
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
for _d in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from conftest import FIXED_DATE_STR, FIXED_NOW, JST

import fetch_news


# ---------------------------------------------------------------------------
# _fetch_rss
# ---------------------------------------------------------------------------
class TestFetchRss:
    def _make_feed(self, entries):
        """feedparser.parse の返り値を模擬する。"""
        feed = MagicMock()
        feed.bozo = False
        feed.entries = entries
        return feed

    def _make_entry(self, title="Test Article", link="https://example.com/1",
                    summary="A test summary."):
        entry = SimpleNamespace()
        entry.title = title
        entry.link = link
        entry.summary = summary
        # get() をサポートするために辞書メソッドを追加
        entry.get = lambda key, default=None: getattr(entry, key, default)
        return entry

    def test_fetches_rss_articles(self):
        """RSS フィードから記事を取得できること。"""
        entries = [self._make_entry(title=f"Article {i}") for i in range(3)]
        feed = self._make_feed(entries)

        source = {
            "name": "Test RSS",
            "url": "https://example.com/feed",
            "max_items": 5,
            "categories": ["AI"],
        }

        with patch("fetch_news.feedparser.parse", return_value=feed), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = fetch_news._fetch_rss(source)

        assert len(articles) == 3
        assert articles[0]["title"] == "Article 0"
        assert articles[0]["source"] == "Test RSS"
        assert articles[0]["category"] == "AI"
        assert articles[0]["url"] == "https://example.com/1"

    def test_max_items_limits_results(self):
        """max_items で取得件数が制限されること。"""
        entries = [self._make_entry(title=f"Article {i}") for i in range(10)]
        feed = self._make_feed(entries)

        source = {
            "name": "Test RSS",
            "url": "https://example.com/feed",
            "max_items": 2,
            "categories": ["Tech General"],
        }

        with patch("fetch_news.feedparser.parse", return_value=feed), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = fetch_news._fetch_rss(source)

        assert len(articles) == 2

    def test_empty_feed(self):
        """空のフィードの場合、空リストを返すこと。"""
        feed = self._make_feed([])

        source = {
            "name": "Empty Source",
            "url": "https://example.com/empty",
            "max_items": 5,
            "categories": ["General"],
        }

        with patch("fetch_news.feedparser.parse", return_value=feed):
            articles = fetch_news._fetch_rss(source)

        assert articles == []

    def test_bozo_feed_without_entries(self):
        """bozo フィード（エラー）でエントリがない場合、空リストを返すこと。"""
        feed = MagicMock()
        feed.bozo = True
        feed.entries = []
        feed.bozo_exception = "XML parse error"

        source = {
            "name": "Bozo Source",
            "url": "https://example.com/bozo",
            "max_items": 5,
            "categories": ["General"],
        }

        with patch("fetch_news.feedparser.parse", return_value=feed):
            articles = fetch_news._fetch_rss(source)

        assert articles == []

    def test_default_category_when_no_categories(self):
        """categories が空の場合、'General' がデフォルトになること。"""
        entries = [self._make_entry()]
        feed = self._make_feed(entries)

        source = {
            "name": "No Cat Source",
            "url": "https://example.com/feed",
            "max_items": 5,
            "categories": [],
        }

        with patch("fetch_news.feedparser.parse", return_value=feed), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = fetch_news._fetch_rss(source)

        assert articles[0]["category"] == "General"

    def test_summary_truncation(self):
        """summary が 300 文字に切り詰められること。"""
        long_summary = "A" * 500
        entries = [self._make_entry(summary=long_summary)]
        feed = self._make_feed(entries)

        source = {
            "name": "Long Summary",
            "url": "https://example.com/feed",
            "max_items": 5,
            "categories": ["AI"],
        }

        with patch("fetch_news.feedparser.parse", return_value=feed), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = fetch_news._fetch_rss(source)

        assert len(articles[0]["summary"]) == 300


# ---------------------------------------------------------------------------
# _fetch_hackernews
# ---------------------------------------------------------------------------
class TestFetchHackerNews:
    def test_fetches_hackernews_articles(self):
        """Hacker News API から記事を取得できること。"""
        mock_top_resp = MagicMock()
        mock_top_resp.json.return_value = [100, 200, 300]
        mock_top_resp.raise_for_status.return_value = None

        def _make_item_resp(story_id):
            resp = MagicMock()
            resp.json.return_value = {
                "title": f"HN Story {story_id}",
                "url": f"https://hn.example.com/{story_id}",
            }
            resp.raise_for_status.return_value = None
            return resp

        def side_effect(url, **kwargs):
            if "topstories" in url:
                return mock_top_resp
            for sid in [100, 200, 300]:
                if str(sid) in url:
                    return _make_item_resp(sid)
            return MagicMock()

        with patch("fetch_news.requests.get", side_effect=side_effect), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = fetch_news._fetch_hackernews(max_items=3)

        assert len(articles) == 3
        assert articles[0]["source"] == "Hacker News"
        assert articles[0]["category"] == "Tech General"
        assert "HN Story" in articles[0]["title"]

    def test_max_items_limits_hn(self):
        """max_items で HN の取得件数が制限されること。"""
        mock_top_resp = MagicMock()
        mock_top_resp.json.return_value = [1, 2, 3, 4, 5]
        mock_top_resp.raise_for_status.return_value = None

        def side_effect(url, **kwargs):
            if "topstories" in url:
                return mock_top_resp
            resp = MagicMock()
            resp.json.return_value = {"title": "Story", "url": "https://example.com"}
            resp.raise_for_status.return_value = None
            return resp

        with patch("fetch_news.requests.get", side_effect=side_effect), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = fetch_news._fetch_hackernews(max_items=2)

        assert len(articles) == 2

    def test_api_failure_returns_empty(self):
        """API 障害時に空リストを返すこと。"""
        with patch("fetch_news.requests.get", side_effect=Exception("Connection error")):
            articles = fetch_news._fetch_hackernews(max_items=5)

        assert articles == []

    def test_null_item_is_skipped(self):
        """item が None の場合スキップされること。"""
        mock_top_resp = MagicMock()
        mock_top_resp.json.return_value = [100]
        mock_top_resp.raise_for_status.return_value = None

        mock_item_resp = MagicMock()
        mock_item_resp.json.return_value = None
        mock_item_resp.raise_for_status.return_value = None

        def side_effect(url, **kwargs):
            if "topstories" in url:
                return mock_top_resp
            return mock_item_resp

        with patch("fetch_news.requests.get", side_effect=side_effect):
            articles = fetch_news._fetch_hackernews(max_items=1)

        assert articles == []


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
class TestFetchNewsMain:
    def test_invalid_session_type(self):
        """不正な session_type で ValueError が発生すること。"""
        with pytest.raises(ValueError, match="morning.*evening"):
            fetch_news.main("invalid")

    def test_main_morning(self, patch_config_dirs, sources_file):
        """morning セッションで正常に動作すること。"""
        entries = [SimpleNamespace(
            title="Test Article",
            link="https://example.com/1",
            summary="Summary text",
            get=lambda key, default=None: {
                "title": "Test Article",
                "link": "https://example.com/1",
            }.get(key, default),
        )]
        feed = MagicMock()
        feed.bozo = False
        feed.entries = entries

        with patch("fetch_news.feedparser.parse", return_value=feed), \
             patch("fetch_news.requests.get") as mock_get, \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # HN API mock
            hn_resp = MagicMock()
            hn_resp.json.return_value = [1]
            hn_resp.raise_for_status.return_value = None
            item_resp = MagicMock()
            item_resp.json.return_value = {"title": "HN Story", "url": "https://hn.example.com/1"}
            item_resp.raise_for_status.return_value = None
            mock_get.side_effect = lambda url, **kw: hn_resp if "topstories" in url else item_resp

            result = fetch_news.main("morning")

        assert "news_morning_2026-02-09" in result
        # ファイルが存在すること
        out_path = Path(result)
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0

    def test_main_saves_json(self, patch_config_dirs, sources_file):
        """JSON ファイルが正しく保存されること。"""
        feed = MagicMock()
        feed.bozo = False
        feed.entries = []

        with patch("fetch_news.feedparser.parse", return_value=feed), \
             patch("fetch_news.requests.get") as mock_get, \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            hn_resp = MagicMock()
            hn_resp.json.return_value = []
            hn_resp.raise_for_status.return_value = None
            mock_get.return_value = hn_resp

            result = fetch_news.main("evening")

        out_path = Path(result)
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)

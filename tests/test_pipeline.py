"""
test_pipeline.py -- エンドツーエンド パイプラインテスト (全モック)

テスト対象フロー:
  fetch_news → generate_tweets → post_to_x → notify
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from conftest import FIXED_DATE_STR, FIXED_NOW, JST, SAMPLE_TWEETS

import fetch_news
import generate_tweets
import notify
import post_to_x


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------
def _make_rss_feed(entries_data):
    """feedparser.parse の戻り値を模擬する。"""
    entries = []
    for data in entries_data:
        entry = SimpleNamespace(**data)
        entry.get = lambda key, default=None, _e=entry: getattr(_e, key, default)
        entries.append(entry)
    feed = MagicMock()
    feed.bozo = False
    feed.entries = entries
    return feed


def _make_hn_responses(story_ids, stories):
    """Hacker News API のモックレスポンスを作成する。"""
    mock_top = MagicMock()
    mock_top.json.return_value = story_ids
    mock_top.raise_for_status.return_value = None

    item_responses = {}
    for sid, story in zip(story_ids, stories):
        resp = MagicMock()
        resp.json.return_value = story
        resp.raise_for_status.return_value = None
        item_responses[str(sid)] = resp

    def side_effect(url, **kwargs):
        if "topstories" in url:
            return mock_top
        for sid_str, resp in item_responses.items():
            if sid_str in url:
                return resp
        raise Exception(f"Unexpected URL: {url}")

    return side_effect


def _mock_claude_response(tweets):
    """Claude API のモックレスポンスを作成する。"""
    response_text = json.dumps(tweets, ensure_ascii=False)
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=f"```json\n{response_text}\n```")]
    return mock_message


# ---------------------------------------------------------------------------
# エンドツーエンド テスト
# ---------------------------------------------------------------------------
class TestPipeline:
    """fetch → generate → post → notify の一気通貫テスト。"""

    def test_full_pipeline_morning(self, patch_config_dirs, sources_file):
        """
        Morning セッションの完全パイプライン:
        1. RSS + HN からニュース取得
        2. Claude API でツイート生成
        3. X API で投稿
        4. Slack/Discord に通知
        """
        drafts = patch_config_dirs["drafts"]
        posted = patch_config_dirs["posted"]

        # -- Step 1: fetch_news --
        rss_feed = _make_rss_feed([
            {"title": "AI Breakthrough", "link": "https://example.com/ai",
             "summary": "A major AI breakthrough."},
            {"title": "Cloud Update", "link": "https://example.com/cloud",
             "summary": "New cloud features."},
        ])
        hn_side_effect = _make_hn_responses(
            [101],
            [{"title": "HN Top Story", "url": "https://hn.example.com/101"}],
        )

        with patch("fetch_news.feedparser.parse", return_value=rss_feed), \
             patch("fetch_news.requests.get", side_effect=hn_side_effect), \
             patch("fetch_news.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            news_path = fetch_news.main("morning")

        # ニュースファイルが存在すること
        assert Path(news_path).exists()
        news_data = json.loads(Path(news_path).read_text(encoding="utf-8"))
        assert len(news_data) > 0

        # -- Step 2: generate_tweets --
        claude_response = _mock_claude_response(SAMPLE_TWEETS)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = claude_response

        with patch("generate_tweets.ANTHROPIC_API_KEY", "sk-test-key"), \
             patch("generate_tweets.anthropic.Anthropic", return_value=mock_client), \
             patch("generate_tweets.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            tweets_path = generate_tweets.main("morning")

        assert Path(tweets_path).exists()
        tweets_data = json.loads(Path(tweets_path).read_text(encoding="utf-8"))
        assert len(tweets_data) == 3
        # メタデータが付与されていること
        for tw in tweets_data:
            assert "id" in tw
            assert tw["session_type"] == "morning"

        # -- Step 3: post_to_x --
        mock_twitter = MagicMock()
        tweet_ids = ["post-id-1", "post-id-2", "post-id-3"]
        call_count = [0]

        def create_tweet_side_effect(**kwargs):
            resp = MagicMock()
            resp.data = {"id": tweet_ids[call_count[0]]}
            call_count[0] += 1
            return resp

        mock_twitter.create_tweet.side_effect = create_tweet_side_effect

        with patch("post_to_x._get_twitter_client", return_value=mock_twitter), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main(session_type="morning", date=FIXED_DATE_STR)

        # 3 件投稿されていること
        assert mock_twitter.create_tweet.call_count == 3

        # posted/ にファイルがコピーされていること
        posted_path = posted / f"posted_{FIXED_DATE_STR}.json"
        assert posted_path.exists()
        posted_data = json.loads(posted_path.read_text(encoding="utf-8"))
        posted_tweets = [t for t in posted_data if t["status"] == "posted"]
        assert len(posted_tweets) == 3
        assert posted_tweets[0]["tweet_id"] == "post-id-1"

        # -- Step 4: notify --
        with patch("notify.datetime") as mock_dt, \
             patch("notify._send_slack") as mock_slack, \
             patch("notify._send_discord") as mock_discord:
            mock_dt.now.return_value = FIXED_NOW
            notify.main("posted")

        mock_slack.assert_called_once()
        mock_discord.assert_called_once()
        msg = mock_slack.call_args[0][0]
        assert "Posted" in msg
        assert "3 件" in msg

    def test_pipeline_with_partial_failure(self, patch_config_dirs, sources_file):
        """
        投稿で一部失敗するケース:
        - 2件目の投稿が失敗し、1件目と3件目は成功する
        """
        import tweepy
        drafts = patch_config_dirs["drafts"]

        # -- Step 1: fetch (空リストでもOK) --
        with patch("fetch_news.feedparser.parse") as mock_parse, \
             patch("fetch_news.requests.get") as mock_get, \
             patch("fetch_news.datetime") as mock_dt:
            mock_parse.return_value = MagicMock(bozo=False, entries=[])
            hn_resp = MagicMock()
            hn_resp.json.return_value = []
            hn_resp.raise_for_status.return_value = None
            mock_get.return_value = hn_resp
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            fetch_news.main("morning")

        # -- Step 2: generate (ニュースファイルにサンプルデータを直接書き込み) --
        news_path = drafts / f"news_morning_{FIXED_DATE_STR}.json"
        news_path.write_text(
            json.dumps([{"title": "t", "url": "u", "summary": "s",
                         "source": "src", "category": "AI",
                         "fetched_at": "2026-02-09T10:00:00+09:00"}],
                       ensure_ascii=False),
            encoding="utf-8",
        )

        claude_response = _mock_claude_response(SAMPLE_TWEETS)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = claude_response

        with patch("generate_tweets.ANTHROPIC_API_KEY", "sk-test-key"), \
             patch("generate_tweets.anthropic.Anthropic", return_value=mock_client), \
             patch("generate_tweets.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            generate_tweets.main("morning")

        # -- Step 3: post (2件目で失敗) --
        mock_twitter = MagicMock()
        call_count = [0]

        def create_tweet_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise tweepy.TweepyException("Duplicate content")
            resp = MagicMock()
            resp.data = {"id": f"ok-{call_count[0]}"}
            return resp

        mock_twitter.create_tweet.side_effect = create_tweet_side_effect

        with patch("post_to_x._get_twitter_client", return_value=mock_twitter), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            post_to_x.main(session_type="morning", date=FIXED_DATE_STR)

        # 結果を確認
        tweets_path = drafts / f"tweets_morning_{FIXED_DATE_STR}.json"
        data = json.loads(tweets_path.read_text(encoding="utf-8"))
        statuses = [t["status"] for t in data]
        assert statuses.count("posted") == 2
        assert statuses.count("failed") == 1

    def test_pipeline_no_news(self, patch_config_dirs, sources_file):
        """
        ニュースが 0 件のケース:
        - fetch は成功するが記事がない
        - generate でニュースファイルは存在するが空配列
        """
        with patch("fetch_news.feedparser.parse") as mock_parse, \
             patch("fetch_news.requests.get") as mock_get, \
             patch("fetch_news.datetime") as mock_dt:
            mock_parse.return_value = MagicMock(bozo=False, entries=[])
            hn_resp = MagicMock()
            hn_resp.json.return_value = []
            hn_resp.raise_for_status.return_value = None
            mock_get.return_value = hn_resp
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            news_path = fetch_news.main("morning")

        data = json.loads(Path(news_path).read_text(encoding="utf-8"))
        assert data == []

    def test_draft_notification_pipeline(self, patch_config_dirs, sources_file):
        """
        Draft 通知パイプライン:
        fetch → generate → draft 通知 (投稿前)
        """
        drafts = patch_config_dirs["drafts"]

        # fetch
        with patch("fetch_news.feedparser.parse") as mock_parse, \
             patch("fetch_news.requests.get") as mock_get, \
             patch("fetch_news.datetime") as mock_dt:
            mock_parse.return_value = MagicMock(bozo=False, entries=[])
            hn_resp = MagicMock()
            hn_resp.json.return_value = []
            hn_resp.raise_for_status.return_value = None
            mock_get.return_value = hn_resp
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            fetch_news.main("morning")

        # ニュースファイルにデータを追加
        news_path = drafts / f"news_morning_{FIXED_DATE_STR}.json"
        news_path.write_text(
            json.dumps([{"title": "Test", "url": "https://example.com",
                         "summary": "s", "source": "src", "category": "AI",
                         "fetched_at": "2026-02-09T10:00:00+09:00"}],
                       ensure_ascii=False),
            encoding="utf-8",
        )

        # generate
        claude_response = _mock_claude_response(SAMPLE_TWEETS[:1])
        mock_client = MagicMock()
        mock_client.messages.create.return_value = claude_response

        with patch("generate_tweets.ANTHROPIC_API_KEY", "sk-test"), \
             patch("generate_tweets.anthropic.Anthropic", return_value=mock_client), \
             patch("generate_tweets.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            generate_tweets.main("morning")

        # draft 通知
        with patch("notify.datetime") as mock_dt, \
             patch("notify._send_slack") as mock_slack, \
             patch("notify._send_discord") as mock_discord:
            mock_dt.now.return_value = FIXED_NOW
            notify.main("draft", session_type="morning",
                       pr_url="https://github.com/user/repo/pull/1")

        mock_slack.assert_called_once()
        msg = mock_slack.call_args[0][0]
        assert "Draft" in msg
        assert "morning" in msg
        assert "https://github.com/user/repo/pull/1" in msg

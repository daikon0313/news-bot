"""
test_post_to_x.py -- post_to_x.py のテスト
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
for _d in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from conftest import FIXED_DATE_STR, FIXED_NOW, JST, SAMPLE_TWEETS

import post_to_x


# ---------------------------------------------------------------------------
# _get_twitter_client
# ---------------------------------------------------------------------------
class TestGetTwitterClient:
    def test_missing_all_keys(self):
        """全ての認証情報が欠けている場合 EnvironmentError が発生すること。"""
        with patch("post_to_x.X_API_KEY", ""), \
             patch("post_to_x.X_API_SECRET", ""), \
             patch("post_to_x.X_ACCESS_TOKEN", ""), \
             patch("post_to_x.X_ACCESS_SECRET", ""):
            with pytest.raises(EnvironmentError, match="X_API_KEY.*X_API_SECRET.*X_ACCESS_TOKEN.*X_ACCESS_SECRET"):
                post_to_x._get_twitter_client()

    def test_missing_partial_keys(self):
        """一部の認証情報が欠けている場合、欠けたものがメッセージに含まれること。"""
        with patch("post_to_x.X_API_KEY", "key"), \
             patch("post_to_x.X_API_SECRET", ""), \
             patch("post_to_x.X_ACCESS_TOKEN", "token"), \
             patch("post_to_x.X_ACCESS_SECRET", ""):
            with pytest.raises(EnvironmentError, match="X_API_SECRET") as exc_info:
                post_to_x._get_twitter_client()
            assert "X_ACCESS_SECRET" in str(exc_info.value)
            assert "X_API_KEY" not in str(exc_info.value)

    def test_all_keys_present(self):
        """全ての認証情報がある場合、tweepy.Client が返されること。"""
        with patch("post_to_x.X_API_KEY", "key"), \
             patch("post_to_x.X_API_SECRET", "secret"), \
             patch("post_to_x.X_ACCESS_TOKEN", "token"), \
             patch("post_to_x.X_ACCESS_SECRET", "access_secret"), \
             patch("post_to_x.tweepy.Client") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            client = post_to_x._get_twitter_client()
            mock_client_cls.assert_called_once_with(
                consumer_key="key",
                consumer_secret="secret",
                access_token="token",
                access_token_secret="access_secret",
            )
            assert client is not None


# ---------------------------------------------------------------------------
# _find_latest_tweets_file
# ---------------------------------------------------------------------------
class TestFindLatestTweetsFile:
    def test_finds_latest_file(self, patch_config_dirs):
        """最新の tweets ファイルが見つかること。"""
        drafts = patch_config_dirs["drafts"]
        (drafts / "tweets_morning_2026-02-08.json").write_text("[]")
        (drafts / "tweets_morning_2026-02-09.json").write_text("[]")
        (drafts / "tweets_evening_2026-02-07.json").write_text("[]")

        result = post_to_x._find_latest_tweets_file()
        assert result is not None
        assert "2026-02-09" in result.name

    def test_no_files_returns_none(self, patch_config_dirs):
        """ファイルがない場合 None を返すこと。"""
        result = post_to_x._find_latest_tweets_file()
        assert result is None

    def test_ignores_news_files(self, patch_config_dirs):
        """news_*.json はスキップされること。"""
        drafts = patch_config_dirs["drafts"]
        (drafts / "news_morning_2026-02-09.json").write_text("[]")

        result = post_to_x._find_latest_tweets_file()
        assert result is None


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
class TestPostToXMain:
    def _write_tweets_file(self, drafts_dir, tweets=None, session="morning", date="2026-02-09"):
        """テスト用ツイートファイルを作成するヘルパー。"""
        if tweets is None:
            tweets = []
            for i, t in enumerate(SAMPLE_TWEETS):
                tweet = t.copy()
                tweet["id"] = f"test-uuid-{i+1}"
                tweet["generated_at"] = "2026-02-09T10:00:00+09:00"
                tweet["session_type"] = session
                tweets.append(tweet)

        path = drafts_dir / f"tweets_{session}_{date}.json"
        path.write_text(json.dumps(tweets, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_no_tweets_file(self, patch_config_dirs):
        """ツイートファイルがない場合、正常に終了すること。"""
        # session_type と date を指定した場合
        post_to_x.main(session_type="morning", date="2026-01-01")
        # エラーなく終了

    def test_no_pending_tweets(self, patch_config_dirs):
        """全てスキップ済みの場合、投稿処理が行われないこと。"""
        tweets = [
            {**SAMPLE_TWEETS[0], "id": "1", "status": "posted", "tweet_id": "123"},
        ]
        self._write_tweets_file(patch_config_dirs["drafts"], tweets=tweets)

        with patch("post_to_x._get_twitter_client") as mock_client:
            post_to_x.main(session_type="morning", date="2026-02-09")
            mock_client.assert_not_called()

    def test_successful_posting(self, patch_config_dirs):
        """pending ツイートが正常に投稿されること。"""
        self._write_tweets_file(patch_config_dirs["drafts"])

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"id": "posted-tweet-id-1"}
        mock_client.create_tweet.return_value = mock_response

        with patch("post_to_x._get_twitter_client", return_value=mock_client), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main(session_type="morning", date="2026-02-09")

        # 3 件投稿
        assert mock_client.create_tweet.call_count == 3

        # ファイルがアップデートされていること
        tweets_path = patch_config_dirs["drafts"] / "tweets_morning_2026-02-09.json"
        data = json.loads(tweets_path.read_text(encoding="utf-8"))
        for t in data:
            assert t["status"] == "posted"
            assert t["tweet_id"] == "posted-tweet-id-1"

        # posted/ にコピーされていること
        posted_path = patch_config_dirs["posted"] / "posted_2026-02-09.json"
        assert posted_path.exists()

    def test_posting_failure_marks_failed(self, patch_config_dirs):
        """投稿失敗時に status が 'failed' になること。"""
        import tweepy
        self._write_tweets_file(patch_config_dirs["drafts"])

        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = tweepy.TweepyException("Rate limit exceeded")

        with patch("post_to_x._get_twitter_client", return_value=mock_client), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main(session_type="morning", date="2026-02-09")

        tweets_path = patch_config_dirs["drafts"] / "tweets_morning_2026-02-09.json"
        data = json.loads(tweets_path.read_text(encoding="utf-8"))
        for t in data:
            assert t["status"] == "failed"
            assert "Rate limit" in t["error"]

        # posted/ には失敗分が含まれないこと
        posted_path = patch_config_dirs["posted"] / "posted_2026-02-09.json"
        posted_data = json.loads(posted_path.read_text(encoding="utf-8"))
        assert posted_data == []

    def test_partial_failure_posted_only_success(self, patch_config_dirs):
        """一部失敗時、posted/ には成功分のみ保存されること。"""
        import tweepy
        self._write_tweets_file(patch_config_dirs["drafts"])

        mock_client = MagicMock()
        call_count = [0]

        def create_tweet_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise tweepy.TweepyException("Duplicate content")
            resp = MagicMock()
            resp.data = {"id": f"ok-{call_count[0]}"}
            return resp

        mock_client.create_tweet.side_effect = create_tweet_side_effect

        with patch("post_to_x._get_twitter_client", return_value=mock_client), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main(session_type="morning", date="2026-02-09")

        posted_path = patch_config_dirs["posted"] / "posted_2026-02-09.json"
        posted_data = json.loads(posted_path.read_text(encoding="utf-8"))
        assert len(posted_data) == 2
        assert all(t["status"] == "posted" for t in posted_data)

    def test_sleep_between_posts(self, patch_config_dirs):
        """ツイート間に待機が入ること (最後のツイート後は待機しない)。"""
        self._write_tweets_file(patch_config_dirs["drafts"])

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"id": "123"}
        mock_client.create_tweet.return_value = mock_response

        with patch("post_to_x._get_twitter_client", return_value=mock_client), \
             patch("post_to_x.time.sleep") as mock_sleep, \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main(session_type="morning", date="2026-02-09")

        # 3 件の投稿で、最後以外の 2 回待機する
        assert mock_sleep.call_count == 2

    def test_fallback_to_latest_file(self, patch_config_dirs):
        """session_type/date 未指定時に最新ファイルにフォールバックすること。"""
        self._write_tweets_file(patch_config_dirs["drafts"])

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"id": "123"}
        mock_client.create_tweet.return_value = mock_response

        with patch("post_to_x._get_twitter_client", return_value=mock_client), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main()  # session_type, date 指定なし

        assert mock_client.create_tweet.call_count == 3

    def test_skip_status_not_posted(self, patch_config_dirs):
        """status=skip のツイートは投稿対象にならないこと。"""
        tweets = []
        for i, t in enumerate(SAMPLE_TWEETS):
            tweet = t.copy()
            tweet["id"] = f"test-uuid-{i+1}"
            tweet["generated_at"] = "2026-02-09T10:00:00+09:00"
            tweet["session_type"] = "morning"
            if i == 2:
                tweet["status"] = "skip"
            tweets.append(tweet)
        self._write_tweets_file(patch_config_dirs["drafts"], tweets=tweets)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"id": "123"}
        mock_client.create_tweet.return_value = mock_response

        with patch("post_to_x._get_twitter_client", return_value=mock_client), \
             patch("post_to_x.time.sleep"), \
             patch("post_to_x.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            post_to_x.main(session_type="morning", date="2026-02-09")

        # pending は 2 件のみ (3件目は skip)
        assert mock_client.create_tweet.call_count == 2

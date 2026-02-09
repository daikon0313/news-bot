"""
test_notify.py -- notify.py のテスト
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

from conftest import (
    FIXED_DATE_STR,
    FIXED_NOW,
    JST,
    SAMPLE_POSTED_TWEETS,
    SAMPLE_TWEETS,
)

import notify


# ---------------------------------------------------------------------------
# _build_draft_message
# ---------------------------------------------------------------------------
class TestBuildDraftMessage:
    def test_contains_session_type(self, tweets_file):
        """メッセージにセッション種別が含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning")

        assert "morning" in msg
        assert "Draft" in msg

    def test_contains_tweet_preview(self, tweets_file):
        """メッセージにツイートのプレビューが含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning")

        assert "1." in msg
        assert "2." in msg
        assert "3." in msg
        # ツイートテキストの先頭部分
        assert "GPT-5" in msg

    def test_contains_pr_url(self, tweets_file):
        """PR URL が含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning", pr_url="https://github.com/pr/1")

        assert "https://github.com/pr/1" in msg

    def test_no_pr_url(self, tweets_file):
        """PR URL なしでも動作すること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning")

        assert "PR:" not in msg

    def test_missing_tweets_file(self, patch_config_dirs):
        """ツイートファイルが存在しない場合のメッセージ。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning")

        assert "ツイートファイルが見つかりませんでした" in msg

    def test_contains_date(self, tweets_file):
        """メッセージに日付が含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning")

        assert FIXED_DATE_STR in msg

    def test_contains_review_instruction(self, tweets_file):
        """レビュー指示メッセージが含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_draft_message("morning")

        assert "レビュー" in msg


# ---------------------------------------------------------------------------
# _build_posted_message
# ---------------------------------------------------------------------------
class TestBuildPostedMessage:
    def test_contains_posted_count(self, posted_file):
        """投稿数が含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_posted_message()

        assert "Posted" in msg
        # SAMPLE_POSTED_TWEETS で posted は 2 件 (3件目は skip)
        assert "2 件" in msg

    def test_contains_tweet_urls(self, posted_file):
        """投稿済みツイートの URL が含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_posted_message()

        assert "https://x.com/i/status/1234567890" in msg

    def test_missing_posted_file(self, patch_config_dirs):
        """投稿済みファイルが存在しない場合のメッセージ。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_posted_message()

        assert "投稿済みファイルが見つかりませんでした" in msg

    def test_contains_date(self, posted_file):
        """メッセージに日付が含まれること。"""
        with patch("notify.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            msg = notify._build_posted_message()

        assert FIXED_DATE_STR in msg


# ---------------------------------------------------------------------------
# _send_slack / _send_discord
# ---------------------------------------------------------------------------
class TestSendSlack:
    def test_sends_to_slack(self):
        """Slack Webhook に POST されること。"""
        with patch("notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"), \
             patch("notify.requests.post") as mock_post:
            mock_post.return_value = MagicMock(raise_for_status=MagicMock())
            notify._send_slack("Test message")

            mock_post.assert_called_once_with(
                "https://hooks.slack.com/test",
                json={"text": "Test message"},
                timeout=10,
            )

    def test_skips_when_no_url(self):
        """SLACK_WEBHOOK_URL が空の場合スキップすること。"""
        with patch("notify.SLACK_WEBHOOK_URL", ""), \
             patch("notify.requests.post") as mock_post:
            notify._send_slack("Test message")
            mock_post.assert_not_called()

    def test_handles_error(self):
        """Slack 送信エラーでも例外が発生しないこと。"""
        with patch("notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"), \
             patch("notify.requests.post", side_effect=Exception("Connection error")):
            # エラーは logger.error で処理され、例外は発生しない
            notify._send_slack("Test message")


class TestSendDiscord:
    def test_sends_to_discord(self):
        """Discord Webhook に POST されること。"""
        with patch("notify.DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test"), \
             patch("notify.requests.post") as mock_post:
            mock_post.return_value = MagicMock(raise_for_status=MagicMock())
            notify._send_discord("Test message")

            mock_post.assert_called_once_with(
                "https://discord.com/api/webhooks/test",
                json={"content": "Test message"},
                timeout=10,
            )

    def test_skips_when_no_url(self):
        """DISCORD_WEBHOOK_URL が空の場合スキップすること。"""
        with patch("notify.DISCORD_WEBHOOK_URL", ""), \
             patch("notify.requests.post") as mock_post:
            notify._send_discord("Test message")
            mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
class TestNotifyMain:
    def test_draft_notification(self, tweets_file):
        """draft 通知が正常に送信されること。"""
        with patch("notify.datetime") as mock_dt, \
             patch("notify._send_slack") as mock_slack, \
             patch("notify._send_discord") as mock_discord:
            mock_dt.now.return_value = FIXED_NOW
            notify.main("draft", session_type="morning", pr_url="https://github.com/pr/1")

        mock_slack.assert_called_once()
        mock_discord.assert_called_once()
        msg = mock_slack.call_args[0][0]
        assert "Draft" in msg
        assert "morning" in msg

    def test_posted_notification(self, posted_file):
        """posted 通知が正常に送信されること。"""
        with patch("notify.datetime") as mock_dt, \
             patch("notify._send_slack") as mock_slack, \
             patch("notify._send_discord") as mock_discord:
            mock_dt.now.return_value = FIXED_NOW
            notify.main("posted")

        mock_slack.assert_called_once()
        mock_discord.assert_called_once()
        msg = mock_slack.call_args[0][0]
        assert "Posted" in msg

    def test_draft_without_session_type(self, patch_config_dirs):
        """draft 通知で session_type がない場合 ValueError が発生すること。"""
        with pytest.raises(ValueError, match="session_type が必要"):
            notify.main("draft")

    def test_invalid_notify_type(self, patch_config_dirs):
        """不正な通知タイプで ValueError が発生すること。"""
        with pytest.raises(ValueError, match="未対応の通知タイプ"):
            notify.main("invalid")

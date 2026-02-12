"""
test_config.py -- config.py のテスト
"""

import sys
from datetime import timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# scripts/ を import パスに追加
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import config


# ---------------------------------------------------------------------------
# タイムゾーン
# ---------------------------------------------------------------------------
class TestJST:
    def test_jst_offset(self):
        """JST は UTC+9 であること。"""
        assert config.JST == timezone(timedelta(hours=9))

    def test_jst_utcoffset(self):
        """utcoffset が 9 時間であること。"""
        assert config.JST.utcoffset(None) == timedelta(hours=9)


# ---------------------------------------------------------------------------
# ディレクトリパス
# ---------------------------------------------------------------------------
class TestPaths:
    def test_base_dir_is_project_root(self):
        """BASE_DIR はプロジェクトルート (scripts/ の親) を指すこと。"""
        assert config.BASE_DIR == Path(__file__).resolve().parent.parent

    def test_drafts_dir(self):
        assert config.DRAFTS_DIR == config.BASE_DIR / "drafts"

    def test_posted_dir(self):
        assert config.POSTED_DIR == config.BASE_DIR / "posted"

    def test_analytics_dir(self):
        assert config.ANALYTICS_DIR == config.BASE_DIR / "analytics"

    def test_templates_dir(self):
        assert config.TEMPLATES_DIR == config.BASE_DIR / "templates"

    def test_sources_file(self):
        assert config.SOURCES_FILE == config.BASE_DIR / "sources.yml"


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
class TestConstants:
    def test_tweets_per_session(self):
        assert config.TWEETS_PER_SESSION == 5

    def test_dedup_days(self):
        assert config.DEDUP_DAYS == 30

    def test_posting_interval_minutes(self):
        assert config.POSTING_INTERVAL_MINUTES == 5


# ---------------------------------------------------------------------------
# load_sources()
# ---------------------------------------------------------------------------
class TestLoadSources:
    def test_load_sources_success(self, tmp_path):
        """正常に sources.yml を読み込めること。"""
        yml_content = """
sources:
  - name: "Test Source"
    type: rss
    url: "https://example.com/feed"
    max_items: 3
    categories:
      - AI
tweets_per_session: 3
"""
        yml_path = tmp_path / "sources.yml"
        yml_path.write_text(yml_content, encoding="utf-8")

        with patch("config.SOURCES_FILE", yml_path):
            result = config.load_sources()

        assert "sources" in result
        assert len(result["sources"]) == 1
        assert result["sources"][0]["name"] == "Test Source"
        assert result["tweets_per_session"] == 3

    def test_load_sources_file_not_found(self, tmp_path):
        """存在しないファイルを指定すると FileNotFoundError が発生すること。"""
        fake_path = tmp_path / "nonexistent.yml"
        with patch("config.SOURCES_FILE", fake_path):
            with pytest.raises(FileNotFoundError, match="ソース定義ファイルが見つかりません"):
                config.load_sources()


# ---------------------------------------------------------------------------
# ensure_dirs()
# ---------------------------------------------------------------------------
class TestEnsureDirs:
    def test_creates_directories(self, tmp_path):
        """必要なディレクトリが作成されること。"""
        drafts = tmp_path / "drafts"
        posted = tmp_path / "posted"
        analytics = tmp_path / "analytics"
        templates = tmp_path / "templates"

        with patch("config.DRAFTS_DIR", drafts), \
             patch("config.POSTED_DIR", posted), \
             patch("config.ANALYTICS_DIR", analytics), \
             patch("config.TEMPLATES_DIR", templates):
            config.ensure_dirs()

        assert drafts.exists()
        assert posted.exists()
        assert analytics.exists()
        assert templates.exists()

    def test_idempotent(self, tmp_path):
        """既にディレクトリが存在していてもエラーにならないこと。"""
        drafts = tmp_path / "drafts"
        drafts.mkdir()

        with patch("config.DRAFTS_DIR", drafts), \
             patch("config.POSTED_DIR", tmp_path / "posted"), \
             patch("config.ANALYTICS_DIR", tmp_path / "analytics"), \
             patch("config.TEMPLATES_DIR", tmp_path / "templates"):
            config.ensure_dirs()  # 2回呼んでもエラーにならない
            config.ensure_dirs()

        assert drafts.exists()


# ---------------------------------------------------------------------------
# 環境変数
# ---------------------------------------------------------------------------
class TestEnvVars:
    def test_default_empty_strings(self):
        """環境変数が未設定の場合、デフォルトは空文字列であること。"""
        # 実行環境に応じてすでに設定されている場合があるので、
        # パッチでテストする
        with patch.dict("os.environ", {}, clear=True):
            # モジュールをリロードして環境変数を再評価
            import importlib
            importlib.reload(config)
            assert config.ANTHROPIC_API_KEY == ""
            assert config.X_API_KEY == ""
            assert config.SLACK_WEBHOOK_URL == ""
            assert config.DISCORD_WEBHOOK_URL == ""

    def test_reads_env_vars(self):
        """環境変数が設定されている場合、その値が使われること。"""
        env = {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "X_API_KEY": "x-test-key",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
        }
        with patch.dict("os.environ", env, clear=True):
            import importlib
            importlib.reload(config)
            assert config.ANTHROPIC_API_KEY == "sk-test-key"
            assert config.X_API_KEY == "x-test-key"
            assert config.SLACK_WEBHOOK_URL == "https://hooks.slack.com/test"

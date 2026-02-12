"""
config.py -- 設定・環境変数・パス定義
"""

import os
import logging
from datetime import timezone, timedelta
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# ロギング
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("news-bot")

# ---------------------------------------------------------------------------
# ディレクトリパス
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

DRAFTS_DIR = BASE_DIR / "drafts"
POSTED_DIR = BASE_DIR / "posted"
ANALYTICS_DIR = BASE_DIR / "analytics"
TEMPLATES_DIR = BASE_DIR / "templates"
SOURCES_FILE = BASE_DIR / "sources.yml"

# ---------------------------------------------------------------------------
# 環境変数
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ---------------------------------------------------------------------------
# タイムゾーン
# ---------------------------------------------------------------------------
JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
TWEETS_PER_SESSION = 5
POSTING_INTERVAL_MINUTES = 5
DEDUP_DAYS = 30
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------
def load_sources() -> dict:
    """sources.yml を読み込んで辞書として返す。"""
    if not SOURCES_FILE.exists():
        raise FileNotFoundError(f"ソース定義ファイルが見つかりません: {SOURCES_FILE}")
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs() -> None:
    """必要なディレクトリが存在しない場合は作成する。"""
    for d in (DRAFTS_DIR, POSTED_DIR, ANALYTICS_DIR, TEMPLATES_DIR):
        d.mkdir(parents=True, exist_ok=True)

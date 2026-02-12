"""
conftest.py -- テスト共通フィクスチャ
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# scripts/ を import パスに追加
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# テスト用 JST タイムゾーン
JST = timezone(timedelta(hours=9))

# テスト用固定日時 (2026-02-09 10:00:00 JST)
FIXED_NOW = datetime(2026, 2, 9, 10, 0, 0, tzinfo=JST)
FIXED_DATE_STR = "2026-02-09"


# ---------------------------------------------------------------------------
# サンプルデータ
# ---------------------------------------------------------------------------
SAMPLE_NEWS_ARTICLES = [
    {
        "title": "GPT-5 Released with Breakthrough Capabilities",
        "url": "https://example.com/gpt5",
        "summary": "OpenAI has released GPT-5 with significant improvements in reasoning.",
        "source": "TechCrunch AI",
        "category": "AI",
        "fetched_at": "2026-02-09T10:00:00+09:00",
    },
    {
        "title": "New Data Pipeline Framework Announced",
        "url": "https://example.com/pipeline",
        "summary": "A new open-source data pipeline framework has been released.",
        "source": "dbt Blog",
        "category": "Data Engineering",
        "fetched_at": "2026-02-09T10:00:00+09:00",
    },
    {
        "title": "Apple Vision Pro Gets Major Update",
        "url": "https://example.com/vision-pro",
        "summary": "Apple has released a major software update for Vision Pro.",
        "source": "The Verge",
        "category": "Tech General",
        "fetched_at": "2026-02-09T10:00:00+09:00",
    },
]

SAMPLE_TWEETS = [
    {
        "tweet_text": "GPT-5がリリース!推論能力が大幅に向上し、コーディングやデータ分析の精度が飛躍的にアップ。AIの進化が止まらない。 #AI #GPT5 https://example.com/gpt5",
        "source_title": "GPT-5 Released with Breakthrough Capabilities",
        "source_url": "https://example.com/gpt5",
        "category": "AI",
        "status": "pending",
    },
    {
        "tweet_text": "新しいオープンソースのデータパイプラインフレームワークが登場。dbtとの統合も可能で、データエンジニアリングの生産性向上に期待。 #DataEngineering https://example.com/pipeline",
        "source_title": "New Data Pipeline Framework Announced",
        "source_url": "https://example.com/pipeline",
        "category": "Data Engineering",
        "status": "pending",
    },
    {
        "tweet_text": "Apple Vision Proに大型アップデート。空間コンピューティングの未来がまた一歩前進。開発者向けAPIも拡充。 #Apple #VisionPro https://example.com/vision-pro",
        "source_title": "Apple Vision Pro Gets Major Update",
        "source_url": "https://example.com/vision-pro",
        "category": "Tech General",
        "status": "pending",
    },
]

SAMPLE_POSTED_TWEETS = [
    {
        **SAMPLE_TWEETS[0],
        "id": "test-uuid-1",
        "generated_at": "2026-02-09T10:00:00+09:00",
        "session_type": "morning",
        "status": "posted",
        "tweet_id": "1234567890",
        "posted_at": "2026-02-09T10:30:00+09:00",
    },
    {
        **SAMPLE_TWEETS[1],
        "id": "test-uuid-2",
        "generated_at": "2026-02-09T10:00:00+09:00",
        "session_type": "morning",
        "status": "posted",
        "tweet_id": "1234567891",
        "posted_at": "2026-02-09T11:00:00+09:00",
    },
    {
        **SAMPLE_TWEETS[2],
        "id": "test-uuid-3",
        "generated_at": "2026-02-09T10:00:00+09:00",
        "session_type": "morning",
        "status": "skip",
    },
]

SAMPLE_SOURCES_YML = """
sources:
  - name: "TechCrunch AI"
    type: rss
    url: "https://techcrunch.com/category/artificial-intelligence/feed/"
    max_items: 3
    categories:
      - AI
  - name: "Hacker News"
    type: api
    url: "https://hacker-news.firebaseio.com/v0/topstories.json"
    max_items: 2
    categories:
      - Tech General

posting:
  morning_slots: ["09:00", "09:30", "10:00"]
  evening_slots: ["20:00", "20:30", "21:00"]
  timezone: "Asia/Tokyo"

tweets_per_session: 3
"""


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_news():
    """サンプルニュース記事のリストを返す。"""
    return [article.copy() for article in SAMPLE_NEWS_ARTICLES]


@pytest.fixture
def sample_tweets():
    """サンプルツイートのリストを返す。"""
    return [tweet.copy() for tweet in SAMPLE_TWEETS]


@pytest.fixture
def sample_posted_tweets():
    """投稿済みサンプルツイートのリストを返す。"""
    return [tweet.copy() for tweet in SAMPLE_POSTED_TWEETS]


@pytest.fixture
def mock_dirs(tmp_path):
    """tmp_path にテスト用ディレクトリ構造を作成し、config のパスをパッチする。"""
    drafts = tmp_path / "drafts"
    posted = tmp_path / "posted"
    analytics = tmp_path / "analytics"
    templates = tmp_path / "templates"
    for d in (drafts, posted, analytics, templates):
        d.mkdir(parents=True, exist_ok=True)

    # プロンプトテンプレートをコピー
    src_template = Path(__file__).resolve().parent.parent / "templates" / "prompt_template.md"
    if src_template.exists():
        (templates / "prompt_template.md").write_text(
            src_template.read_text(encoding="utf-8"), encoding="utf-8"
        )

    return {
        "base": tmp_path,
        "drafts": drafts,
        "posted": posted,
        "analytics": analytics,
        "templates": templates,
    }


@pytest.fixture
def patch_config_dirs(mock_dirs):
    """config モジュールのディレクトリパスを tmp_path にパッチする。

    各スクリプトは ``from config import DRAFTS_DIR`` で独自バインディングを持つため、
    config だけでなくスクリプトモジュール側もパッチする。
    """
    with patch("config.DRAFTS_DIR", mock_dirs["drafts"]), \
         patch("config.POSTED_DIR", mock_dirs["posted"]), \
         patch("config.ANALYTICS_DIR", mock_dirs["analytics"]), \
         patch("config.TEMPLATES_DIR", mock_dirs["templates"]), \
         patch("config.BASE_DIR", mock_dirs["base"]), \
         patch("fetch_news.DRAFTS_DIR", mock_dirs["drafts"]), \
         patch("fetch_news.POSTED_DIR", mock_dirs["posted"]), \
         patch("generate_tweets.DRAFTS_DIR", mock_dirs["drafts"]), \
         patch("generate_tweets.TEMPLATES_DIR", mock_dirs["templates"]), \
         patch("post_to_x.DRAFTS_DIR", mock_dirs["drafts"]), \
         patch("post_to_x.POSTED_DIR", mock_dirs["posted"]), \
         patch("notify.DRAFTS_DIR", mock_dirs["drafts"]), \
         patch("notify.POSTED_DIR", mock_dirs["posted"]):
        yield mock_dirs


@pytest.fixture
def news_file(patch_config_dirs, sample_news):
    """drafts/ にニュースファイルを作成する。"""
    path = patch_config_dirs["drafts"] / f"news_morning_{FIXED_DATE_STR}.json"
    path.write_text(json.dumps(sample_news, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def tweets_file(patch_config_dirs, sample_tweets):
    """drafts/ にツイートファイルを作成する。"""
    import uuid
    tweets = []
    for t in sample_tweets:
        tweet = t.copy()
        tweet["id"] = str(uuid.uuid4())
        tweet["generated_at"] = "2026-02-09T10:00:00+09:00"
        tweet["session_type"] = "morning"
        tweets.append(tweet)
    path = patch_config_dirs["drafts"] / f"tweets_morning_{FIXED_DATE_STR}.json"
    path.write_text(json.dumps(tweets, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def posted_file(patch_config_dirs, sample_posted_tweets):
    """posted/ に投稿済みファイルを作成する。"""
    path = patch_config_dirs["posted"] / f"posted_{FIXED_DATE_STR}.json"
    path.write_text(
        json.dumps(sample_posted_tweets, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


@pytest.fixture
def sources_file(patch_config_dirs):
    """sources.yml をテスト用 base ディレクトリに作成する。"""
    path = patch_config_dirs["base"] / "sources.yml"
    path.write_text(SAMPLE_SOURCES_YML, encoding="utf-8")
    with patch("config.SOURCES_FILE", path):
        yield path


@pytest.fixture
def fixed_now():
    """テスト用固定日時を返す。"""
    return FIXED_NOW


@pytest.fixture
def mock_datetime_now():
    """datetime.now() を固定日時に置き換えるパッチ。"""
    with patch("config.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_dt

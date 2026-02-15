"""
test_generate_tweets.py -- generate_tweets.py のテスト
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
for _d in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from conftest import FIXED_DATE_STR, FIXED_NOW, JST, SAMPLE_NEWS_ARTICLES, SAMPLE_TWEETS

import generate_tweets


# ---------------------------------------------------------------------------
# _parse_tweets_json
# ---------------------------------------------------------------------------
class TestParseTweetsJson:
    def test_parse_json_code_block(self):
        """```json ... ``` ブロックから JSON を抽出できること。"""
        text = """Here are the tweets:
```json
[
  {"tweet_text": "Hello", "status": "pending"},
  {"tweet_text": "World", "status": "pending"}
]
```
"""
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 2
        assert result[0]["tweet_text"] == "Hello"

    def test_parse_plain_code_block(self):
        """``` ... ``` ブロック (json ラベルなし) から JSON を抽出できること。"""
        text = """
```
[{"tweet_text": "Test", "status": "pending"}]
```
"""
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 1
        assert result[0]["tweet_text"] == "Test"

    def test_parse_bare_json_array(self):
        """コードブロックなしの JSON 配列を抽出できること。"""
        text = '[{"tweet_text": "Bare JSON", "status": "pending"}]'
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 1
        assert result[0]["tweet_text"] == "Bare JSON"

    def test_parse_no_json_raises(self):
        """JSON が見つからない場合に ValueError が発生すること。"""
        text = "No JSON here, just plain text."
        with pytest.raises(ValueError, match="JSON 配列を検出できません"):
            generate_tweets._parse_tweets_json(text)

    def test_parse_json_with_surrounding_text(self):
        """前後にテキストがある JSON を抽出できること。"""
        text = """
Here are the tweets I generated:

```json
[
  {
    "tweet_text": "テストツイート #AI https://example.com",
    "source_title": "Test",
    "source_url": "https://example.com",
    "category": "AI",
    "status": "pending"
  }
]
```

Hope you like them!
"""
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 1
        assert result[0]["category"] == "AI"

    def test_parse_newlines_in_tweet_text(self):
        """ツイート本文内の改行を含む JSON をパースできること。"""
        text = '''```json
[
  {
    "tweet_text": "1行目のテキスト
2行目のテキスト #AI https://example.com",
    "source_title": "Test",
    "source_url": "https://example.com",
    "category": "AI",
    "status": "pending"
  }
]
```'''
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 1
        assert "1行目" in result[0]["tweet_text"]

    def test_parse_trailing_comma(self):
        """末尾カンマがある JSON をパースできること。"""
        text = '''[
  {
    "tweet_text": "テスト #AI https://example.com",
    "source_title": "Test",
    "source_url": "https://example.com",
    "category": "AI",
    "status": "pending",
  },
]'''
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 1

    def test_parse_tabs_in_text(self):
        """タブ文字を含む JSON をパースできること。"""
        text = '[{"tweet_text": "テスト\there #AI", "status": "pending"}]'
        # raw tab in the JSON string value — should be repaired
        raw = '[{"tweet_text": "テスト\there #AI", "status": "pending"}]'
        result = generate_tweets._parse_tweets_json(raw)
        assert len(result) == 1

    def test_parse_multiple_code_blocks_picks_valid(self):
        """複数コードブロックがある場合、有効な JSON を見つけること。"""
        text = '''Here is an example:
```
invalid json here
```

And here are the actual tweets:
```json
[{"tweet_text": "Valid", "status": "pending"}]
```'''
        result = generate_tweets._parse_tweets_json(text)
        assert len(result) == 1
        assert result[0]["tweet_text"] == "Valid"


# ---------------------------------------------------------------------------
# _load_news
# ---------------------------------------------------------------------------
class TestLoadNews:
    def test_load_news_success(self, news_file):
        """ニュースファイルが正常に読み込めること。"""
        with patch("generate_tweets.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            articles = generate_tweets._load_news("morning")

        assert len(articles) == 3
        assert articles[0]["title"] == "GPT-5 Released with Breakthrough Capabilities"

    def test_load_news_file_not_found(self, patch_config_dirs):
        """ニュースファイルが存在しない場合 FileNotFoundError が発生すること。"""
        with patch("generate_tweets.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            with pytest.raises(FileNotFoundError, match="ニュースファイルが見つかりません"):
                generate_tweets._load_news("morning")


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------
class TestBuildPrompt:
    def test_build_prompt_contains_articles(self, patch_config_dirs, sample_news):
        """プロンプトにニュース記事情報が含まれること。"""
        prompt = generate_tweets._build_prompt(sample_news)

        assert "GPT-5 Released" in prompt
        assert "https://example.com/gpt5" in prompt
        assert "TechCrunch AI" in prompt
        assert "3" in prompt  # tweets_per_session

    def test_build_prompt_template_not_found(self, tmp_path):
        """テンプレートが存在しない場合 FileNotFoundError が発生すること。"""
        with patch("generate_tweets.TEMPLATES_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="テンプレートが見つかりません"):
                generate_tweets._build_prompt([])


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
class TestGenerateTweetsMain:
    def test_invalid_session_type(self):
        """不正な session_type で ValueError が発生すること。"""
        with patch("generate_tweets.ANTHROPIC_API_KEY", "sk-test"):
            with pytest.raises(ValueError, match="morning"):
                generate_tweets.main("invalid")

    def test_missing_api_key(self):
        """API キーが未設定の場合 EnvironmentError が発生すること。"""
        with patch("generate_tweets.ANTHROPIC_API_KEY", ""):
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                generate_tweets.main("morning")

    def test_main_success(self, news_file, patch_config_dirs):
        """正常系: ツイート生成 -> JSON 保存が成功すること。"""
        # Claude API のモックレスポンスを作成
        mock_response_text = json.dumps(SAMPLE_TWEETS, ensure_ascii=False)
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=f"```json\n{mock_response_text}\n```")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("generate_tweets.ANTHROPIC_API_KEY", "sk-test-key"), \
             patch("generate_tweets.anthropic.Anthropic", return_value=mock_client), \
             patch("generate_tweets.datetime") as mock_dt, \
             patch("generate_tweets.uuid") as mock_uuid:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mock_uuid.uuid4.return_value = "test-uuid-1"

            result = generate_tweets.main("morning")

        assert "tweets_morning_2026-02-09" in result
        out_path = Path(result)
        assert out_path.exists()

        tweets = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(tweets) == 3
        # メタデータが追加されていること
        assert tweets[0]["id"] == "test-uuid-1"
        assert tweets[0]["session_type"] == "morning"
        assert "generated_at" in tweets[0]

    def test_main_calls_claude_api(self, news_file, patch_config_dirs):
        """Claude API が正しいパラメータで呼ばれること。"""
        mock_response_text = json.dumps(SAMPLE_TWEETS, ensure_ascii=False)
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=f"```json\n{mock_response_text}\n```")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("generate_tweets.ANTHROPIC_API_KEY", "sk-test-key"), \
             patch("generate_tweets.anthropic.Anthropic", return_value=mock_client) as mock_cls, \
             patch("generate_tweets.datetime") as mock_dt, \
             patch("generate_tweets.uuid"):
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            generate_tweets.main("morning")

        # Anthropic クライアントが API キーで初期化されること
        mock_cls.assert_called_once_with(api_key="sk-test-key")
        # messages.create が呼ばれること
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == 2048
        assert len(call_kwargs.kwargs["messages"]) == 1
        assert call_kwargs.kwargs["messages"][0]["role"] == "user"

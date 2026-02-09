"""
test_format_pr_body.py -- format_pr_body.py のテスト
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from conftest import SAMPLE_TWEETS

import format_pr_body


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
class TestFormatPrBody:
    def test_formats_tweets_list(self, tmp_path, capsys):
        """ツイートリストが正しくフォーマットされること。"""
        draft_file = tmp_path / "tweets.json"
        draft_file.write_text(json.dumps(SAMPLE_TWEETS, ensure_ascii=False), encoding="utf-8")

        with patch("sys.argv", ["format_pr_body.py", str(draft_file)]):
            format_pr_body.main()

        captured = capsys.readouterr()
        output = captured.out

        assert "### Tweet 1 [AI]" in output
        assert "### Tweet 2 [Data Engineering]" in output
        assert "### Tweet 3 [Tech General]" in output
        assert "GPT-5" in output
        assert "Source: GPT-5 Released" in output

    def test_formats_dict_with_tweets_key(self, tmp_path, capsys):
        """dict 形式 (tweets キー) のファイルもフォーマットできること。"""
        data = {"tweets": SAMPLE_TWEETS[:1]}
        draft_file = tmp_path / "tweets.json"
        draft_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        with patch("sys.argv", ["format_pr_body.py", str(draft_file)]):
            format_pr_body.main()

        captured = capsys.readouterr()
        assert "### Tweet 1" in captured.out

    def test_formats_single_dict(self, tmp_path, capsys):
        """単一の dict が渡された場合もフォーマットできること。"""
        single_tweet = SAMPLE_TWEETS[0]
        data = {"tweets": [single_tweet]}  # dict wrapping single tweet
        draft_file = tmp_path / "tweets.json"
        draft_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        with patch("sys.argv", ["format_pr_body.py", str(draft_file)]):
            format_pr_body.main()

        captured = capsys.readouterr()
        assert "### Tweet 1" in captured.out

    def test_tweet_text_in_blockquote(self, tmp_path, capsys):
        """ツイート本文が > 引用符で表示されること。"""
        draft_file = tmp_path / "tweets.json"
        draft_file.write_text(json.dumps(SAMPLE_TWEETS[:1], ensure_ascii=False), encoding="utf-8")

        with patch("sys.argv", ["format_pr_body.py", str(draft_file)]):
            format_pr_body.main()

        captured = capsys.readouterr()
        assert "> " in captured.out

    def test_source_title_displayed(self, tmp_path, capsys):
        """source_title が表示されること。"""
        draft_file = tmp_path / "tweets.json"
        draft_file.write_text(json.dumps(SAMPLE_TWEETS[:1], ensure_ascii=False), encoding="utf-8")

        with patch("sys.argv", ["format_pr_body.py", str(draft_file)]):
            format_pr_body.main()

        captured = capsys.readouterr()
        assert "Source:" in captured.out
        assert "GPT-5 Released" in captured.out

    def test_no_source_title(self, tmp_path, capsys):
        """source_title がない場合でもエラーにならないこと。"""
        tweet = {"tweet_text": "Test tweet", "category": "AI"}
        draft_file = tmp_path / "tweets.json"
        draft_file.write_text(json.dumps([tweet], ensure_ascii=False), encoding="utf-8")

        with patch("sys.argv", ["format_pr_body.py", str(draft_file)]):
            format_pr_body.main()

        captured = capsys.readouterr()
        assert "### Tweet 1 [AI]" in captured.out
        # Source: が表示されないこと
        assert "Source:" not in captured.out

    def test_missing_file_raises(self, tmp_path):
        """存在しないファイルを指定すると FileNotFoundError が発生すること。"""
        with patch("sys.argv", ["format_pr_body.py", str(tmp_path / "nonexistent.json")]):
            with pytest.raises(FileNotFoundError):
                format_pr_body.main()

"""
test_weekly_report.py -- weekly_report.py のテスト
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from conftest import SAMPLE_POSTED_TWEETS

import weekly_report


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------
def _create_posted_files(posted_dir, files_data):
    """テスト用 posted ファイルを作成する。

    files_data: [(filename, tweets_list), ...]
    """
    posted_dir.mkdir(parents=True, exist_ok=True)
    for filename, tweets in files_data:
        path = posted_dir / filename
        path.write_text(json.dumps(tweets, ensure_ascii=False, indent=2), encoding="utf-8")
    return posted_dir


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
class TestWeeklyReport:
    def test_report_with_data(self, tmp_path, capsys):
        """正常系: 投稿データがある週のレポートが生成されること。"""
        posted_dir = tmp_path / "posted"
        tweets_mon = [
            {"tweet_text": "AI tweet", "category": "AI", "source": "TechCrunch", "status": "posted"},
            {"tweet_text": "Data tweet", "category": "Data Engineering", "source": "dbt", "status": "posted"},
        ]
        tweets_tue = [
            {"tweet_text": "Tech tweet", "category": "Tech General", "source": "The Verge", "status": "posted"},
        ]
        _create_posted_files(posted_dir, [
            ("posted_morning_2026-02-03.json", tweets_mon),
            ("posted_2026-02-04.json", tweets_tue),
        ])

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        output = captured.out

        assert "Weekly Analysis Report" in output
        assert "2026-02-02 - 2026-02-09" in output
        assert "Total tweets posted: **3**" in output
        assert "Draft files processed: **2**" in output
        assert "AI" in output
        assert "Data Engineering" in output
        assert "Morning" in output

    def test_report_empty_week(self, tmp_path, capsys):
        """投稿がない週では "No tweets" メッセージが表示されること。"""
        posted_dir = tmp_path / "posted"
        posted_dir.mkdir(parents=True, exist_ok=True)

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        assert "No tweets were posted this week." in captured.out
        assert "Total tweets posted: **0**" in captured.out

    def test_report_date_filtering(self, tmp_path, capsys):
        """日付範囲外のファイルがフィルタされること。"""
        posted_dir = tmp_path / "posted"
        tweets = [
            {"tweet_text": "In range", "category": "AI", "source": "Test", "status": "posted"},
        ]
        out_of_range = [
            {"tweet_text": "Out of range", "category": "AI", "source": "Test", "status": "posted"},
        ]
        _create_posted_files(posted_dir, [
            ("posted_2026-02-05.json", tweets),       # 範囲内
            ("posted_2026-01-20.json", out_of_range), # 範囲外
            ("posted_2026-02-15.json", out_of_range), # 範囲外
        ])

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        assert "Total tweets posted: **1**" in captured.out
        assert "Draft files processed: **1**" in captured.out

    def test_category_distribution(self, tmp_path, capsys):
        """カテゴリ分布が正しく計算されること。"""
        posted_dir = tmp_path / "posted"
        tweets = [
            {"tweet_text": "t1", "category": "AI", "source": "s1"},
            {"tweet_text": "t2", "category": "AI", "source": "s1"},
            {"tweet_text": "t3", "category": "Tech General", "source": "s2"},
        ]
        _create_posted_files(posted_dir, [
            ("posted_2026-02-05.json", tweets),
        ])

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        assert "Category Distribution" in captured.out
        assert "AI: 2" in captured.out
        assert "Tech General: 1" in captured.out

    def test_top_sources(self, tmp_path, capsys):
        """Top Sources が正しく表示されること。"""
        posted_dir = tmp_path / "posted"
        tweets = [
            {"tweet_text": "t1", "category": "AI", "source": "TechCrunch"},
            {"tweet_text": "t2", "category": "AI", "source": "TechCrunch"},
            {"tweet_text": "t3", "category": "AI", "source": "OpenAI Blog"},
        ]
        _create_posted_files(posted_dir, [
            ("posted_2026-02-05.json", tweets),
        ])

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        assert "Top Sources" in captured.out
        assert "TechCrunch: 2" in captured.out
        assert "OpenAI Blog: 1" in captured.out

    def test_engagement_note(self, tmp_path, capsys):
        """エンゲージメント関連の注記が表示されること。"""
        posted_dir = tmp_path / "posted"
        posted_dir.mkdir(parents=True, exist_ok=True)

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        assert "Engagement metrics" in captured.out
        assert "X API Basic plan" in captured.out

    def test_malformed_json_file(self, tmp_path, capsys):
        """壊れた JSON ファイルがあってもクラッシュしないこと。"""
        posted_dir = tmp_path / "posted"
        posted_dir.mkdir(parents=True, exist_ok=True)
        (posted_dir / "posted_2026-02-05.json").write_text("not valid json")

        with patch("weekly_report.POSTED_DIR", posted_dir), \
             patch("sys.argv", ["weekly_report.py", "2026-02-02", "2026-02-09"]):
            weekly_report.main()

        captured = capsys.readouterr()
        assert "Total tweets posted: **0**" in captured.out
        # stderr にワーニングが出力されること
        assert "Warning" in capsys.readouterr().err or "Warning" in captured.err

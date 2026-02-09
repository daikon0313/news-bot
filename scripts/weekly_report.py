"""
weekly_report.py -- 週次投稿分析レポートを生成する
Usage:
    python scripts/weekly_report.py <week_start> <week_end>
    python scripts/weekly_report.py 2026-02-02 2026-02-09
"""

import glob
import json
import os
import sys
from collections import Counter


def main() -> None:
    week_start = sys.argv[1]
    week_end = sys.argv[2]

    posted_files = sorted(glob.glob("posted/*.json"))

    # Filter files within the date range
    weekly_files = []
    for f in posted_files:
        basename = os.path.basename(f)
        parts = basename.replace(".json", "").split("_")
        if len(parts) >= 3:
            file_date = parts[-1]
            if len(file_date) == 10 and week_start <= file_date <= week_end:
                weekly_files.append(f)

    total_tweets = 0
    categories: Counter[str] = Counter()
    sessions: Counter[str] = Counter()
    sources: Counter[str] = Counter()

    for f in weekly_files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            tweets = data if isinstance(data, list) else data.get("tweets", [data])
            total_tweets += len(tweets)
            for t in tweets:
                categories[t.get("category", "Uncategorized")] += 1
                sources[t.get("source", "Unknown")] += 1
            if "morning" in os.path.basename(f):
                sessions["morning"] += len(tweets)
            elif "evening" in os.path.basename(f):
                sessions["evening"] += len(tweets)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not parse {f}: {e}", file=sys.stderr)

    print(f"# Weekly Analysis Report")
    print(f"Period: {week_start} - {week_end}")
    print()
    print(f"## Summary")
    print(f"- Total tweets posted: **{total_tweets}**")
    print(f"- Draft files processed: **{len(weekly_files)}**")
    print()

    if sessions:
        print(f"## Session Breakdown")
        for session, count in sessions.most_common():
            print(f"- {session.capitalize()}: {count} tweets")
        print()

    if categories:
        print(f"## Category Distribution")
        for cat, count in categories.most_common(10):
            pct = (count / total_tweets * 100) if total_tweets > 0 else 0
            bar = "#" * int(pct / 5)
            print(f"- {cat}: {count} ({pct:.0f}%) {bar}")
        print()

    if sources:
        print(f"## Top Sources")
        for src, count in sources.most_common(5):
            print(f"- {src}: {count}")
        print()

    if total_tweets == 0:
        print("No tweets were posted this week.")
        print()

    print("---")
    print("Note: Engagement metrics (likes, retweets, impressions) require")
    print("X API Basic plan. Please check the X Analytics dashboard manually")
    print("for detailed engagement data.")


if __name__ == "__main__":
    main()

"""
format_pr_body.py -- ツイート案を PR body 用にフォーマットする
Usage:
    python scripts/format_pr_body.py <draft_file>
"""

import json
import sys


def main() -> None:
    draft_file = sys.argv[1]
    with open(draft_file, "r", encoding="utf-8") as f:
        tweets = json.load(f)

    if isinstance(tweets, dict):
        tweets = tweets.get("tweets", [tweets])

    for i, t in enumerate(tweets, 1):
        text = t.get("tweet_text", t.get("text", str(t)))
        category = t.get("category", "General")
        source = t.get("source_title", t.get("source", ""))
        print(f"### Tweet {i} [{category}]")
        print(f"> {text}")
        if source:
            print()
            print(f"Source: {source}")
        print()


if __name__ == "__main__":
    main()

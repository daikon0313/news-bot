"""
post_to_x.py -- ツイートを X (Twitter) に投稿する
Usage:
    python scripts/post_to_x.py
    python scripts/post_to_x.py --session-type morning --date 2025-01-01
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import tweepy

from config import (
    DRAFTS_DIR,
    JST,
    POSTED_DIR,
    POSTING_INTERVAL_MINUTES,
    X_ACCESS_SECRET,
    X_ACCESS_TOKEN,
    X_API_KEY,
    X_API_SECRET,
    ensure_dirs,
    logger,
)


def _get_twitter_client() -> tweepy.Client:
    """tweepy Client (API v2) を生成する。"""
    missing: list[str] = []
    if not X_API_KEY:
        missing.append("X_API_KEY")
    if not X_API_SECRET:
        missing.append("X_API_SECRET")
    if not X_ACCESS_TOKEN:
        missing.append("X_ACCESS_TOKEN")
    if not X_ACCESS_SECRET:
        missing.append("X_ACCESS_SECRET")

    if missing:
        raise EnvironmentError(
            "以下の環境変数が設定されていません: " + ", ".join(missing)
        )

    # 認証情報のデバッグ (値そのものは出力しない)
    logger.info(
        "認証情報: API_KEY=%d文字, API_SECRET=%d文字, "
        "ACCESS_TOKEN=%d文字, ACCESS_SECRET=%d文字",
        len(X_API_KEY), len(X_API_SECRET),
        len(X_ACCESS_TOKEN), len(X_ACCESS_SECRET),
    )

    # 前後の空白を除去して渡す
    return tweepy.Client(
        consumer_key=X_API_KEY.strip(),
        consumer_secret=X_API_SECRET.strip(),
        access_token=X_ACCESS_TOKEN.strip(),
        access_token_secret=X_ACCESS_SECRET.strip(),
    )


def _find_latest_tweets_file() -> Path | None:
    """drafts/ から最新の tweets_*.json を探す。"""
    candidates = sorted(DRAFTS_DIR.glob("tweets_*.json"), reverse=True)
    return candidates[0] if candidates else None


def main(session_type: str | None = None, date: str | None = None) -> None:
    """pending ステータスのツイートを X に投稿する。"""
    ensure_dirs()

    if session_type and date:
        tweets_file = DRAFTS_DIR / f"tweets_{session_type}_{date}.json"
        if not tweets_file.exists():
            logger.error("ファイルが見つかりません: %s", tweets_file)
            return
    else:
        tweets_file = _find_latest_tweets_file()
        if tweets_file is None:
            logger.warning("drafts/ にツイートファイルが見つかりません")
            return

    logger.info("ツイートファイル読み込み: %s", tweets_file)
    with open(tweets_file, "r", encoding="utf-8") as f:
        tweets: list[dict] = json.load(f)

    # 投稿対象の絞り込み
    pending = [t for t in tweets if t.get("status") == "pending"]
    skipped = [t for t in tweets if t.get("status") == "skip"]

    if skipped:
        logger.info("スキップ対象: %d 件", len(skipped))
    if not pending:
        logger.info("投稿対象の pending ツイートがありません")
        return

    logger.info("投稿対象: %d 件", len(pending))

    # Twitter クライアント作成
    client = _get_twitter_client()

    posted_count = 0
    for i, tweet in enumerate(pending):
        tweet_text = tweet.get("tweet_text", "")
        if not tweet_text:
            logger.warning("tweet_text が空のためスキップ: id=%s", tweet.get("id"))
            continue

        try:
            logger.info("投稿中 (%d/%d): %s...", i + 1, len(pending), tweet_text[:50])
            response = client.create_tweet(text=tweet_text)
            tweet_id = response.data["id"]

            tweet["status"] = "posted"
            tweet["tweet_id"] = tweet_id
            tweet["posted_at"] = datetime.now(JST).isoformat()
            posted_count += 1

            logger.info("  -> 投稿成功 (tweet_id=%s)", tweet_id)

        except tweepy.TweepyException as exc:
            logger.error("  -> 投稿失敗: %s", exc)
            # API エラーの詳細を出力
            if hasattr(exc, "response") and exc.response is not None:
                logger.error("  -> HTTP Status: %s", exc.response.status_code)
                logger.error("  -> Response: %s", exc.response.text)
            if hasattr(exc, "api_errors"):
                logger.error("  -> API Errors: %s", exc.api_errors)
            tweet["status"] = "failed"
            tweet["error"] = str(exc)

        # 元ファイルを都度更新（途中で落ちてもステータスを失わない）
        with open(tweets_file, "w", encoding="utf-8") as f:
            json.dump(tweets, f, ensure_ascii=False, indent=2)

        # 最後のツイート以外は間隔を空ける
        if i < len(pending) - 1:
            wait_sec = POSTING_INTERVAL_MINUTES * 60
            logger.info("次の投稿まで %d 分待機...", POSTING_INTERVAL_MINUTES)
            time.sleep(wait_sec)

    # posted/ にコピー
    today = datetime.now(JST).strftime("%Y-%m-%d")
    posted_path = POSTED_DIR / f"posted_{today}.json"
    shutil.copy2(tweets_file, posted_path)
    logger.info("投稿済みデータをコピー: %s", posted_path)

    logger.info("完了: %d 件投稿", posted_count)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X にツイートを投稿する")
    parser.add_argument("--session-type", default=None, choices=["morning", "evening"])
    parser.add_argument("--date", default=None, help="日付 (YYYY-MM-DD)")
    args = parser.parse_args()
    try:
        main(args.session_type, args.date)
    except Exception:
        logger.exception("X への投稿中にエラーが発生しました")
        sys.exit(1)

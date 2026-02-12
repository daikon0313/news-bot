"""
notify.py -- Slack / Discord Webhook 通知
Usage:
    python scripts/notify.py draft morning --pr-url https://github.com/...
    python scripts/notify.py posted
"""

import argparse
import json
import sys
from datetime import datetime

import requests

from config import (
    DISCORD_WEBHOOK_URL,
    DRAFTS_DIR,
    JST,
    POSTED_DIR,
    SLACK_WEBHOOK_URL,
    ensure_dirs,
    logger,
)


# ---------------------------------------------------------------------------
# 通知メッセージ組み立て
# ---------------------------------------------------------------------------
def _build_draft_message(
    session_type: str, pr_url: str | None = None
) -> str:
    """ドラフト通知用のメッセージを生成する。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    tweets_path = DRAFTS_DIR / f"tweets_{session_type}_{today}.json"

    lines = [f"*[Draft] {session_type} ツイート案が作成されました*"]
    lines.append(f"日付: {today}")

    if tweets_path.exists():
        with open(tweets_path, "r", encoding="utf-8") as f:
            tweets = json.load(f)
        lines.append(f"件数: {len(tweets)} 件")
        lines.append("")
        for i, tw in enumerate(tweets, 1):
            text_preview = tw.get("tweet_text", "")[:80]
            lines.append(f"{i}. {text_preview}...")
    else:
        lines.append("(ツイートファイルが見つかりませんでした)")

    if pr_url:
        lines.append("")
        lines.append(f"PR: {pr_url}")

    lines.append("")
    lines.append("PR をレビュー・マージして投稿を承認してください。")
    return "\n".join(lines)


def _build_posted_message() -> str:
    """投稿完了通知用のメッセージを生成する。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    posted_path = POSTED_DIR / f"posted_{today}.json"

    lines = [f"*[Posted] ツイートを投稿しました*"]
    lines.append(f"日付: {today}")

    if posted_path.exists():
        with open(posted_path, "r", encoding="utf-8") as f:
            tweets = json.load(f)

        posted = [t for t in tweets if t.get("status") == "posted"]
        lines.append(f"投稿数: {len(posted)} 件")
        lines.append("")
        for i, tw in enumerate(posted, 1):
            text_preview = tw.get("tweet_text", "")[:80]
            tweet_url = ""
            if tw.get("tweet_id"):
                tweet_url = f" (https://x.com/i/status/{tw['tweet_id']})"
            lines.append(f"{i}. {text_preview}...{tweet_url}")
    else:
        lines.append("(投稿済みファイルが見つかりませんでした)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Webhook 送信
# ---------------------------------------------------------------------------
def _send_slack(message: str) -> None:
    """Slack Incoming Webhook にメッセージを送信する。"""
    if not SLACK_WEBHOOK_URL:
        logger.info("SLACK_WEBHOOK_URL が未設定のためスキップ")
        return

    payload = {"text": message}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Slack 通知送信成功")
    except Exception as exc:
        logger.error("Slack 通知送信失敗: %s", exc)


def _send_discord(message: str) -> None:
    """Discord Webhook にメッセージを送信する。"""
    if not DISCORD_WEBHOOK_URL:
        logger.info("DISCORD_WEBHOOK_URL が未設定のためスキップ")
        return

    payload = {"content": message}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Discord 通知送信成功")
    except Exception as exc:
        logger.error("Discord 通知送信失敗: %s", exc)


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
def main(
    notify_type: str,
    session_type: str | None = None,
    pr_url: str | None = None,
) -> None:
    """
    通知を送信する。

    Args:
        notify_type: "draft" or "posted"
        session_type: "morning" or "evening" (draft 時に必要)
        pr_url: PR の URL (draft 時にオプション)
    """
    ensure_dirs()

    if notify_type == "draft":
        if not session_type:
            raise ValueError("draft 通知には session_type が必要です")
        message = _build_draft_message(session_type, pr_url)
    elif notify_type == "posted":
        message = _build_posted_message()
    else:
        raise ValueError(f"未対応の通知タイプ: {notify_type}")

    logger.info("通知メッセージ:\n%s", message)

    _send_slack(message)
    _send_discord(message)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Slack / Discord に通知を送る")
    parser.add_argument(
        "notify_type",
        choices=["draft", "posted"],
        help="通知タイプ (draft / posted)",
    )
    parser.add_argument(
        "session_type",
        nargs="?",
        default=None,
        choices=["morning"],
        help="セッション種別 (draft 時に必要)",
    )
    parser.add_argument(
        "--session-type",
        dest="session_type_flag",
        default=None,
        choices=["morning"],
        help="セッション種別 (--session-type フラグ版)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="日付 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--pr-url",
        default=None,
        help="PR の URL (draft 通知時にオプション)",
    )
    args = parser.parse_args()

    # --session-type フラグが位置引数より優先
    session_type = args.session_type_flag or args.session_type

    try:
        main(args.notify_type, session_type, args.pr_url)
    except Exception:
        logger.exception("通知送信中にエラーが発生しました")
        sys.exit(1)

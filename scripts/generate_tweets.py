"""
generate_tweets.py -- Claude API でツイートを生成する
Usage:
    python scripts/generate_tweets.py morning
    python scripts/generate_tweets.py evening
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    DRAFTS_DIR,
    JST,
    TEMPLATES_DIR,
    TWEETS_PER_SESSION,
    ensure_dirs,
    logger,
)


def _load_news(session_type: str) -> list[dict]:
    """指定セッションの最新ニュース JSON を読み込む。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    news_path = DRAFTS_DIR / f"news_{session_type}_{today}.json"
    if not news_path.exists():
        raise FileNotFoundError(f"ニュースファイルが見つかりません: {news_path}")
    with open(news_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_prompt(news_articles: list[dict]) -> str:
    """プロンプトテンプレートにニュースデータを埋め込む。"""
    template_path = TEMPLATES_DIR / "prompt_template.md"
    if not template_path.exists():
        raise FileNotFoundError(f"テンプレートが見つかりません: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # ニュース記事をテキストに変換
    articles_text = ""
    for i, article in enumerate(news_articles, 1):
        articles_text += (
            f"[{i}] {article['title']}\n"
            f"    URL: {article['url']}\n"
            f"    ソース: {article['source']} ({article['category']})\n"
            f"    概要: {article.get('summary', 'N/A')}\n\n"
        )

    prompt = template.replace("{news_articles}", articles_text)
    prompt = prompt.replace("{tweets_per_session}", str(TWEETS_PER_SESSION))
    return prompt


def _parse_tweets_json(text: str) -> list[dict]:
    """Claude のレスポンスから JSON 配列を抽出・パースする。"""
    # コードブロック内の JSON を優先的に探す
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        json_str = code_block.group(1).strip()
    else:
        # コードブロックがなければ [ ... ] を直接探す
        bracket = re.search(r"\[.*\]", text, re.DOTALL)
        if bracket:
            json_str = bracket.group(0)
        else:
            raise ValueError("レスポンスから JSON 配列を検出できませんでした")

    return json.loads(json_str)


def main(session_type: str) -> str:
    """
    ツイートを生成して JSON に保存する。

    Args:
        session_type: "morning" or "evening"

    Returns:
        保存先ファイルパス (文字列)
    """
    if session_type not in ("morning", "evening"):
        raise ValueError(f"session_type は 'morning' または 'evening' を指定: {session_type}")

    if not ANTHROPIC_API_KEY:
        raise EnvironmentError(
            "環境変数 ANTHROPIC_API_KEY が設定されていません。"
            " export ANTHROPIC_API_KEY='sk-...' を実行してください。"
        )

    ensure_dirs()

    # ニュース読み込み
    news_articles = _load_news(session_type)
    logger.info("ニュース記事 %d 件を読み込みました", len(news_articles))

    # プロンプト構築
    prompt = _build_prompt(news_articles)

    # Claude API 呼び出し
    logger.info("Claude API を呼び出し中 (model=%s) ...", CLAUDE_MODEL)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )

    response_text = message.content[0].text
    logger.info("Claude API からレスポンスを取得しました")

    # JSON パース
    tweets = _parse_tweets_json(response_text)
    logger.info("ツイート %d 件を生成しました", len(tweets))

    # メタデータを追加
    now_iso = datetime.now(JST).isoformat()
    for tweet in tweets:
        tweet["id"] = str(uuid.uuid4())
        tweet["generated_at"] = now_iso
        tweet["session_type"] = session_type

    # 保存
    today = datetime.now(JST).strftime("%Y-%m-%d")
    out_path = DRAFTS_DIR / f"tweets_{session_type}_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tweets, f, ensure_ascii=False, indent=2)

    logger.info("保存完了: %s", out_path)
    return str(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude API でツイートを生成する")
    parser.add_argument(
        "session_type",
        choices=["morning", "evening"],
        help="セッション種別 (morning / evening)",
    )
    args = parser.parse_args()

    try:
        result_path = main(args.session_type)
        print(f"完了: {result_path}")
    except Exception as e:
        logger.exception("ツイート生成中にエラーが発生しました")
        sys.exit(1)

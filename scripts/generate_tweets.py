"""
generate_tweets.py -- Claude API でツイートを生成する
Usage:
    python scripts/generate_tweets.py morning
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
        priority = article.get("priority", 3)
        articles_text += (
            f"[{i}] {article['title']}\n"
            f"    URL: {article['url']}\n"
            f"    ソース: {article['source']} ({article['category']}) [priority: {priority}]\n"
            f"    概要: {article.get('summary', 'N/A')}\n\n"
        )

    prompt = template.replace("{news_articles}", articles_text)
    prompt = prompt.replace("{tweets_per_session}", str(TWEETS_PER_SESSION))
    return prompt


def _parse_tweets_json(text: str) -> list[dict]:
    """Claude のレスポンスから JSON 配列を抽出・パースする。"""
    candidates: list[str] = []

    # 1. コードブロック内の JSON を優先的に探す
    for m in re.finditer(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL):
        candidates.append(m.group(1).strip())

    # 2. コードブロックがなければ [{ ... }] (JSON配列) を直接探す
    if not candidates:
        bracket = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        if bracket:
            candidates.append(bracket.group(0))

    # 3. それでもなければ全体を試す
    if not candidates:
        candidates.append(text.strip())

    last_error = None
    for json_str in candidates:
        # そのまま試す
        try:
            result = json.loads(json_str)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as exc:
            last_error = exc

        # 修復を試みる: 制御文字を除去、改行をエスケープ
        cleaned = _repair_json(json_str)
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                logger.warning("JSON を修復してパースしました")
                return result
        except json.JSONDecodeError as exc:
            last_error = exc

    # デバッグ用にレスポンスの冒頭をログ出力
    logger.error("JSON パース失敗。レスポンス冒頭 500 文字:\n%s", text[:500])
    raise ValueError(
        f"レスポンスから JSON 配列を検出できませんでした: {last_error}"
    )


def _repair_json(json_str: str) -> str:
    """よくある JSON の問題を修復する。"""
    # 文字列値内の生の改行を \\n にエスケープ
    # JSON の文字列リテラル内 ("..." の中) の生改行を処理
    result = []
    in_string = False
    escape_next = False
    for ch in json_str:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == '\\':
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch == '\n':
            result.append('\\n')
            continue
        if in_string and ch == '\t':
            result.append('\\t')
            continue
        result.append(ch)
    repaired = ''.join(result)

    # 末尾カンマを除去 (}, ] の前の ,)
    repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

    return repaired


def main(session_type: str) -> str:
    """
    ツイートを生成して JSON に保存する。

    Args:
        session_type: "morning"

    Returns:
        保存先ファイルパス (文字列)
    """
    if session_type not in ("morning",):
        raise ValueError(f"session_type は 'morning' を指定: {session_type}")

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
        choices=["morning"],
        help="セッション種別 (morning)",
    )
    args = parser.parse_args()

    try:
        result_path = main(args.session_type)
        print(f"完了: {result_path}")
    except Exception as e:
        logger.exception("ツイート生成中にエラーが発生しました")
        sys.exit(1)

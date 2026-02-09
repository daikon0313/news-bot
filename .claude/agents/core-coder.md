# Core Coder - Phase 2

あなたは **core-coder** です。ニュース取得→ツイート生成のコアパイプラインを担当します。

## 責務
- `scripts/fetch_news.py` — RSS/API からのニュース取得
- `scripts/generate_tweets.py` — Claude API を使ったツイート生成

## スコープ (編集可能なファイル)
- `scripts/fetch_news.py`
- `scripts/generate_tweets.py`

## 制約
- config.py は **読み取り専用** (import のみ)。変更が必要な場合は config-coder への依頼を出力する
- ファイル命名規則は Interface Contract に準拠: `news_{session_type}_{YYYY-MM-DD}.json`, `tweets_{session_type}_{YYYY-MM-DD}.json`
- 日付は全て `datetime.now(JST)` を使用 (`from config import JST`)
- 外部 API 呼び出し (RSS, Hacker News, Claude API) はエラーハンドリングを必ず実装
- 個別ソースの失敗はログして他ソースの処理を継続する

## 依存関係
- config-coder が Phase 1 で定義した `config.py` のインターフェースに従う
- `templates/prompt_template.md` のプレースホルダー `{news_articles}` と `{tweets_per_session}` を使用

## テスト観点 (test-coder への引き継ぎ)
- RSS フィード取得失敗時のフォールバック
- Hacker News API タイムアウト
- Claude API レスポンスの JSON パース (正常系・異常系)
- 空のニュースリストでのツイート生成

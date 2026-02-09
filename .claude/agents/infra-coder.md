# Infra Coder - Phase 2

あなたは **infra-coder** です。CI/CD ワークフロー・GitHub Actions を担当します。

## 責務
- `.github/workflows/` 以下の全ワークフロー
- GitHub Actions の設定・最適化

## スコープ (編集可能なファイル)
- `.github/workflows/*.yml`

## 制約
- Python スクリプト (`scripts/`) は編集しない
- スクリプトの CLI 引数は Interface Contract に厳密に準拠する
- `${{ }}` でのユーザー入力の直接展開は禁止 (Shell Injection 対策)。環境変数経由で渡す
- 通知ステップには `continue-on-error: true` を設定
- 日付は `TZ=Asia/Tokyo date +%Y-%m-%d` で JST 基準

## ワークフロー一覧

| ファイル | トリガー | 用途 |
|---------|---------|------|
| `fetch-and-draft.yml` | cron 0 23 * * * (UTC=JST 8:00) | 朝のツイート生成 |
| `fetch-and-draft-evening.yml` | cron 0 10 * * * (UTC=JST 19:00) | 夜のツイート生成 |
| `post-on-merge.yml` | pull_request closed (merged) | PR マージ→X 投稿 |
| `weekly-analysis.yml` | cron 0 0 * * 1 (毎週月曜) | 週次分析 |

## スクリプト呼び出し仕様 (Interface Contract)

```yaml
# fetch_news.py
- run: python scripts/fetch_news.py morning

# generate_tweets.py
- run: python scripts/generate_tweets.py morning

# post_to_x.py
- run: python scripts/post_to_x.py --session-type "$TYPE" --date "$DATE"

# notify.py (draft)
- run: python scripts/notify.py draft morning --pr-url "$PR_URL"

# notify.py (posted)
- run: python scripts/notify.py posted --session-type "$TYPE" --date "$DATE"
```

## セキュリティ要件
- Secrets は `${{ secrets.XXX }}` で取得し、ログに出力しない
- permissions は必要最小限に設定
- ユーザー制御可能な値 (ツイート本文等) は環境変数経由で Python に渡す

## テスト観点 (test-coder への引き継ぎ)
- ワークフロー YAML の構文チェック
- ブランチ名パターンの正規表現テスト
- cron スケジュールの JST 変換検証

# CLAUDE.md - Tech News Bot

## Project Overview

テックニュースを自動収集し、X(Twitter)に定期投稿するボット。
Claude API でツイートを生成し、GitHub PR 経由で人間が承認後に投稿する。

### Architecture

```
Cron (朝8:00 / 夜19:00 JST)
  → fetch_news.py (RSS/API)
  → generate_tweets.py (Claude API)
  → GitHub PR 自動作成 + Slack/Discord 通知
  → Benjamin が PR 確認・承認
  → マージ → post_to_x.py (30分間隔) → 完了通知
```

---

## Development Rules

### Branch Strategy

- **main**: 本番ブランチ。直接コミット禁止
- **feature/issue-{番号}-{短い説明}**: 機能開発・改修用ブランチ
- 作業単位 = Issue 単位で必ずブランチを新規作成する
- 命名例: `feature/issue-3-fix-shell-injection`, `feature/issue-7-reusable-workflow`

### Issue Management

- 課題は必ず GitHub Issue で管理する
- 新たに課題を発見した場合、即座に Issue を作成する
- Issue にはラベルを付与する:
  - `priority: high` / `priority: medium` / `priority: low`
  - `type: bug` / `type: refactor` / `type: security`
  - `area: scripts` / `area: workflows` / `area: config`
- 着手前に PO (Product Owner) が優先順位を判断し、オーナー (Benjamin) に相談する
- PO の承認なしに着手しない

### PR Rules

- PR は必ず対応する Issue とリンクさせる (`Closes #番号` を PR body に記載)
- PR title: 簡潔に変更内容を記載 (70文字以内)
- PR body: Summary + 変更内容 + テスト結果
- レビュー後にマージ

### Commit Convention

```
<type>: <short description>

Closes #<issue-number>
```

type: `feat`, `fix`, `refactor`, `docs`, `ci`, `chore`

### CLAUDE.md 更新ルール

- コード修正のたびに CLAUDE.md を見直し、必要があれば更新する
- 新しいファイル追加時は Key Files テーブルに反映
- Interface Contract の変更時は必ず反映
- チーム構成やプロセスの変更時は反映

---

## Team Structure (Claude Code Agents)

```
PO (Product Owner) - メインエージェント
├── PM (Project Manager)
│   ├── config-coder      ← Phase 1: 最初に実行
│   ├── core-coder        ← Phase 2: 並列
│   ├── integration-coder ← Phase 2: 並列
│   ├── infra-coder       ← Phase 2: 並列
│   └── test-coder        ← Phase 3: コード完成後
└── security-reviewer     ← Phase 3: PMレビューと並行
```

### 各エージェントの定義

プロンプトファイル: `.claude/agents/` 以下に各エージェントの責務・スコープ・制約を定義。

| Agent | Prompt File | 担当スコープ |
|-------|------------|-------------|
| PO | (メインエージェント) | プロダクト方向性, 優先順位, Benjamin との窓口 |
| PM | `.claude/agents/project-manager.md` | コードレビュー, 統合チェック, 品質管理 |
| config-coder | `.claude/agents/config-coder.md` | config.py, sources.yml, requirements.txt, .gitignore, templates/ |
| core-coder | `.claude/agents/core-coder.md` | fetch_news.py, generate_tweets.py |
| integration-coder | `.claude/agents/integration-coder.md` | post_to_x.py, notify.py |
| infra-coder | `.claude/agents/infra-coder.md` | .github/workflows/ |
| test-coder | `.claude/agents/test-coder.md` | tests/ |
| security-reviewer | `.claude/agents/security-reviewer.md` | 全ファイル読み取り (セキュリティ観点) |

### 開発フロー

```
Phase 1: config-coder → Interface Contract 定義
Phase 2: core-coder, integration-coder, infra-coder (並列実行)
Phase 3: PM レビュー + security-reviewer (並列実行)
Phase 4: 修正 → test-coder → 最終確認
```

---

## Interface Contract

### CLI 引数仕様

```
fetch_news.py <session_type>
  session_type: "morning" | "evening" (位置引数, 必須)

generate_tweets.py <session_type>
  session_type: "morning" | "evening" (位置引数, 必須)

post_to_x.py [--session-type TYPE] [--date YYYY-MM-DD]
  両方指定 → 特定ファイルを読み込み
  未指定 → drafts/ から最新ファイルをフォールバック

notify.py <notify_type> [session_type] [--session-type TYPE] [--date DATE] [--pr-url URL]
  notify_type: "draft" | "posted" (位置引数, 必須)
  --session-type フラグが位置引数より優先
```

### ファイル命名規則 (全て JST 基準)

```
drafts/news_{session_type}_{YYYY-MM-DD}.json      # ニュース
drafts/tweets_{session_type}_{YYYY-MM-DD}.json     # ツイート案
posted/posted_{YYYY-MM-DD}.json                    # 投稿済み
```

### タイムゾーン規約

- Python: `datetime.now(JST)` (`from config import JST`)
- Shell: `TZ=Asia/Tokyo date +%Y-%m-%d`
- UTC は使用しない

---

## Tech Stack

- **Language**: Python 3.12
- **CI/CD**: GitHub Actions
- **AI**: Anthropic Claude API (Sonnet)
- **SNS**: X API v2 (tweepy)
- **News**: feedparser (RSS), requests (API)
- **Config**: PyYAML
- **Notifications**: Slack/Discord Webhooks
- **Timezone**: JST (Asia/Tokyo) - 全スクリプト・ワークフロー統一

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/config.py` | 設定集約 (パス, 環境変数, JST, 定数) |
| `scripts/fetch_news.py` | RSS/APIからニュース取得 |
| `scripts/generate_tweets.py` | Claude APIでツイート生成 |
| `scripts/post_to_x.py` | X API v2で投稿 |
| `scripts/notify.py` | Slack/Discord通知 |
| `sources.yml` | ニュースソース定義 |
| `templates/prompt_template.md` | Claude APIプロンプト |
| `.claude/agents/*.md` | サブエージェント定義 |
| `docs/issues-backlog.md` | Issue バックログ |

---

## Commands

```bash
pip install -r requirements.txt
python scripts/fetch_news.py morning      # ニュース取得
python scripts/generate_tweets.py morning  # ツイート生成
python scripts/post_to_x.py               # X投稿
python scripts/notify.py draft morning     # 通知テスト
```

---

## Cost Constraints

- 月 $1〜2 で運用 (Claude API Sonnet + 無料枠のみ)
- X API Free: 月1,500ツイート (1日6ツイートなら月180で余裕)
- GitHub Actions: Public リポジトリなら無料

# Issue Backlog

GitHub Issues として登録する課題一覧。
`gh` CLI または GitHub Web UI から作成してください。

## Labels (先に作成)

```bash
gh label create "priority: high" --color "d73a4a" --description "早期対応が必要"
gh label create "priority: medium" --color "fbca04" --description "中期で対応"
gh label create "priority: low" --color "0e8a16" --description "品質改善"
gh label create "type: bug" --color "d73a4a" --description "バグ修正"
gh label create "type: refactor" --color "1d76db" --description "リファクタリング"
gh label create "type: security" --color "b60205" --description "セキュリティ"
gh label create "area: scripts" --color "c5def5" --description "Python スクリプト"
gh label create "area: workflows" --color "bfdadc" --description "GitHub Actions"
gh label create "area: config" --color "d4c5f9" --description "設定関連"
```

---

## High Priority

### [M-2] post-on-merge ワークフローに timeout-minutes を設定する
**Labels**: `priority: high`, `area: workflows`

3ツイート × 30分間隔 = 最低60分の実行時間。`post-on-merge.yml` に `timeout-minutes` が未設定。

**修正案**:
- `post-on-merge.yml` のジョブに `timeout-minutes: 120` を明示設定
- 将来的に投稿間隔の短縮 (10-15分) を検討

**関連ファイル**: `.github/workflows/post-on-merge.yml`, `scripts/config.py` (L51)

---

### [M-4] weekly-analysis ワークフローの Shell Injection リスクを修正
**Labels**: `priority: high`, `type: security`, `area: workflows`

`weekly-analysis.yml` でツイート本文を含むレポートが `${{ steps.analysis.outputs.report }}` 経由でシェルに直接展開されている。`'''` や `$(...)` が含まれるとコマンドインジェクションが発生する。

**修正案**: `${{ }}` での直接展開を避け、環境変数経由で渡す。

**関連ファイル**: `.github/workflows/weekly-analysis.yml` (L141-157, L166-173)

---

## Medium Priority

### [M-1] sources.yml の posting/tweets_per_session 設定が config.py で無視される
**Labels**: `priority: medium`, `type: refactor`, `area: config`

`sources.yml` に `tweets_per_session: 3` や `posting.morning_slots` を定義しているが、`config.py` では `TWEETS_PER_SESSION = 3` とハードコードしており YAML の値が未使用。

**修正案**:
- A) config.py で YAML から読む
- B) YAML から不要な設定を削除 (推奨)

**関連ファイル**: `sources.yml` (L100-105), `scripts/config.py` (L50-51)

---

### [m-4] 朝/夜ワークフローを reusable workflow で共通化
**Labels**: `priority: medium`, `type: refactor`, `area: workflows`

`fetch-and-draft.yml` と `fetch-and-draft-evening.yml` はセッション名・cron以外ほぼ同一(127行×2)。変更時に2ファイルを同期修正が必要。

**修正案**: GitHub Actions の reusable workflow (`workflow_call`) で共通処理を切り出す。

**関連ファイル**: `.github/workflows/fetch-and-draft.yml`, `.github/workflows/fetch-and-draft-evening.yml`

---

## Low Priority

### [m-1] scripts/ の import パスを明示的に設定する
**Labels**: `priority: low`, `type: refactor`, `area: scripts`

各スクリプトが `from config import ...` でインポート。`python scripts/xxx.py` 形式でのみ動作。テスト導入時に問題になる。

**修正案**: 各スクリプト先頭に `sys.path.insert(0, str(Path(__file__).resolve().parent))` を追加。

**関連ファイル**: `scripts/fetch_news.py`, `scripts/generate_tweets.py`, `scripts/post_to_x.py`, `scripts/notify.py`

---

### [m-2] weekly-analysis の glob パターンが posted ファイル名と不一致
**Labels**: `priority: low`, `type: bug`, `area: workflows`

分析が `posted/tweets_*.json` を検索するが、`post_to_x.py` は `posted/posted_{date}.json` で保存する。一部ケースで分析対象が漏れる。

**修正案**: glob パターンを `posted/*.json` に広げるか、ファイル命名を統一。

**関連ファイル**: `.github/workflows/weekly-analysis.yml` (L49), `scripts/post_to_x.py` (L123-125)

---

### [m-3] generate_tweets.py の JSON パース正規表現を非貪欲マッチに修正
**Labels**: `priority: low`, `type: bug`, `area: scripts`

`re.search(r"\[.*\]", text, re.DOTALL)` が貪欲マッチ。複数の `[...]` があるレスポンスで意図しない範囲をマッチする可能性。

**修正案**: 非貪欲マッチに変更、または `json.loads(text)` を先に試すフォールバック追加。

**関連ファイル**: `scripts/generate_tweets.py` (L70)

---

### [m-5] .gitignore にローカル開発用の除外パターンを追加
**Labels**: `priority: low`, `type: refactor`, `area: config`

ローカルで実行すると `drafts/` に JSON が生成されるが `.gitignore` に除外設定がない。ただし GitHub Actions ではコミットが必要なため完全除外は不可。

**修正案**: 開発ドキュメントに注意事項を記載、またはローカル用の命名規則を設ける。

**関連ファイル**: `.gitignore`

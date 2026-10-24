# Lumi Spark Growth OS Ver.1.0（ローカルMVP）

Lumi Sparkのnote記事を資産として管理し、ハブ記事から関連記事へ読者をつなぎ、
読者との関係（認知→信頼→対話→参加意向→有料参加→継続→実践成果）を継続的に管理・分析・改善するためのローカルアプリです。

```
記事を公開 → 新しい読者 → ハブから関連記事へ → 信頼が深まる → コメント・議論
   ↑                                                              ↓
実践成果が新しい記事に ← 共同研究・実践 ← メンバーシップ ← 読者の課題を把握
```

> 技術的に動くことと、読者回遊の改善や収益化が成功することは別です。
> このアプリは判断材料を整える道具であり、最終判断は人間が行います。

## 安全方針（このアプリがしないこと）

- noteへの投稿・編集・データ取得（スクレイピング、非公式API、セッションクッキーの利用）
- 決済・課金処理、会員情報の取得・保存
- 既存台帳（Google Sheets / Excel）の更新・削除（取込は読み取り専用、前後のSHA-256で確認）
- 外部通信（Streamlitの利用統計送信も `.streamlit/config.toml` で無効化、localhostのみで待受）
- APIキー・有料サービスの利用

## noteのRSSからの取り込み（オーナー承認：2026-10-24）

noteが公式に提供するRSS（`https://note.com/lumispark/rss`）から、記事のタイトル・URL・公開日時を取り込めます。
取得するのはRSSだけで、記事ページの読み取り・ログイン・非公式APIは使いません。通信するのは `scripts/rss_sync.py` だけで、アプリ本体（`lumi_growth_os/`・`app/`）は通信しません。

```bash
python scripts/rss_sync.py --local --actor 西冨 --dry-run   # 反映内容の確認
python scripts/rss_sync.py --local --actor 西冨             # パソコン版へ反映
```

- 途中までのタイトル（「…（以降未確認）」）は、RSSのタイトルと前方一致すれば自動で補います。
- URLの共有用パラメータは除去し、公開日時は日本時間に変換します。公開日時は未登録の記事にだけ入れます。
- 新しい記事は `LS-A010` 以降の番号で追加します（テーマ・タグは未設定）。
- RSSに載るのは最近の記事だけです。古い記事はスマホ版の「まとめて貼り付け」で入れてください。
- Claude Codeのクラウド環境から実行する場合は、環境の Network access で `note.com` を許可する必要があります。

## 動作環境

- Python 3.10 以上（3.13 で検証）
- Windows / macOS / Linux（検証はLinuxのみ）

## セットアップと起動

```bash
cd lumi-spark-growth-os
python -m venv .venv
# Windows: .venv\Scripts\activate   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python scripts/lumi.py init          # DB作成＋初期データ投入（実データ＋明示されたサンプル）
streamlit run app/main.py            # ブラウザで http://localhost:8501 を開く
```

- 初回起動時にDBがなければ自動で作成・初期データ投入されます（`data/lumi_growth.db`）。
- サンプルなしで始める場合：`python scripts/lumi.py init --no-samples`（DB作成前に実行）
- DBの場所を変える場合：環境変数 `LUMI_DB_PATH`、バックアップ先は `LUMI_BACKUP_DIR`
- `data/initial/lumi_growth_initial.db` は納品時点の初期DBのコピーです（参照用）。

## 画面

| 画面 | できること |
|---|---|
| ホーム | 循環の全体像、3ハブ、人間の確認・承認が必要な事項 |
| 記事資産台帳 | 一覧からの一括編集、詳細編集、新規登録、計測履歴、旧台帳の原文表示 |
| ハブ構造 | 3ハブの編集、導線ステップの一覧編集、ハブと関連記事の図（補助） |
| 関連記事推薦 | タグ・ルールによる推薦（2〜3件）、推薦理由・価値・リンク文・挿入場所・URL状態の表示、提案登録 |
| リンク承認・貼り付け文 | 提案→確認→承認→note反映→表示確認、操作履歴、note貼り付け用文章のコピー、リンク検査 |
| 記事分析 | 24h/72h/累積を分けた実績、Proxy指標と比較警告、構造コード分析、アカウント全体、ランキング、読者理解 |
| 収益導線 | 段階ごとの担当記事、確認済み実績の記録（出典必須） |
| 取込・バックアップ・履歴 | CSV/Excel取込（試し取込あり）、バックアップ・復旧、Excel書き出し、全操作履歴 |

書き込み操作には、サイドバーの「担当者名」の入力が必要です（操作履歴に記録）。

## 取込フォーマット

列見出しで自動判別します。

| 判別結果 | 必須の列 | 例 |
|---|---|---|
| 旧台帳『記事台帳』（38列） | `Article_ID`, `タイトル`, `24h PV` | note記事運用台帳 Ver.0.1 をxlsxでダウンロードしたもの |
| 旧台帳『日次アカウント』 | `集計日時`, `28日PV` | 同上（シートを選択） |
| 記事 | `article_id`, `title` | `data/samples/sample_articles.csv` |
| 実績 | `article_id`, `measured_at`, `window_type` | `data/samples/sample_metrics.csv` |
| リンク提案 | `source_article_id`, `target_article_id` | `data/samples/sample_links.csv` |

- 空欄は「未計測（NULL）」で、0とは区別されます。`100+` のような不正確な値は数値化しません。
- 既存の記事IDは上書きしません。旧台帳の列のうち新モデルにないものは `legacy_json` に原文のまま保全します。
- タイトルが `【サンプル】` で始まる記事、または「サンプルとして登録」を選んだ取込は、サンプル扱いになります。

## コマンド

```bash
python scripts/lumi.py backup --label 作業前
python scripts/lumi.py list-backups
python scripts/lumi.py restore lumi_YYYYMMDD_....db --yes
python scripts/lumi.py import 台帳.xlsx --sheet 記事台帳 --dry-run --actor 西冨
python scripts/lumi.py export exports/全データ.xlsx
python -m pytest                     # テスト
python scripts/run_acceptance.py     # 受入テストを実行し docs/受入テスト結果.md を更新
```

## 構成

```
lumi_growth_os/   データモデル・業務ロジック（画面から独立）
  db.py           SQLiteスキーマ
  codes.py        Ver.6.1の構造コード・マスタ
  validation.py   入力検証（URL形式、欠損と0、日時）
  repository.py   記事・ハブ・リンク・実績・監査ログの操作
  recommend.py    ルールベース推薦
  textgen.py      note貼り付け用文章
  metrics.py      Proxy指標・比較警告・構造分析
  importer.py     非破壊インポート
  backup.py       バックアップ・復旧・書き出し
  seed.py         初期データ（出典つき実データ＋サンプル）
app/              Streamlit画面（main.py と views/）
scripts/          CLI・受入テスト報告
tests/            pytest
docs/             設計書・マニュアル・報告書
data/samples/     取込練習用のサンプルファイル（実績ではない）
```

## ドキュメント

- [設計書（Phase 0：環境調査・データモデル）](docs/設計書_データモデル.md)
- [操作マニュアル](docs/操作マニュアル.md)
- [データ移行・バックアップ手順](docs/データ移行・バックアップ手順.md)
- [既存台帳との差分報告](docs/既存台帳との差分報告.md)
- [受入テスト結果](docs/受入テスト結果.md)
- [確認待ち事項（未確認データ・人間の承認が必要な事項）](docs/確認待ち事項.md)
- [今後の拡張計画](docs/今後の拡張計画.md)

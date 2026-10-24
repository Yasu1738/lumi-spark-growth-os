# スマホ版（iPhone向け）

`lumi_spark_mobile.html` は、claude.ai上の非公開ページとして公開している iPhone 向けの画面です。

- 公開先：https://claude.ai/artifact/ViGffCC5QJiyqNcvjQ9JMX （本人のみ閲覧可）
- データはページの保存機能（claude.aiのデータベース）に保存され、パソコン版のSQLiteとは別です。
- 初期データは `data/initial/lumi_growth_initial.db` の実データのみ（サンプルは入れていません）。
- 判定ルール（URL検証・共有用パラメータ除去、24h/72h値の時間範囲、リンク承認の順番と仮案の承認禁止、ルール推薦、貼り付け文）はパソコン版と同じです。
- noteへの投稿・編集・データ取得は行いません。

## 毎日の自動更新（2026-10-24〜）

毎朝6:47（日本時間）に、RSS取込・テーマ/タグ推定・関連記事の自動提案を行う。手順は `docs/毎日の自動更新手順.md`、
計画づくりの処理は `lumi_growth_os/mobile_sync.py`（通信なし）と `scripts/mobile_sync.py`。

## 操作（オーナー了承により簡略化）

- 関連記事：「承認」1タップ →「コピー」→ noteに貼る →「貼った」1タップ
- 数字：noteアクセス状況（期間「全期間」）のスクショを選ぶと、Claudeが読み取り、確認して記録

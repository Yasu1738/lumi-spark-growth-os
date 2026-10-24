"""コマンドライン操作。

  python scripts/lumi.py init [--no-samples]     DBを作成し初期データを投入
  python scripts/lumi.py backup [--label 名前]    バックアップを作成
  python scripts/lumi.py list-backups             バックアップ一覧
  python scripts/lumi.py restore <ファイル> --yes  バックアップから復旧（復旧前の状態は自動退避）
  python scripts/lumi.py import <ファイル> [--sheet シート名] [--dry-run] [--as-sample] --actor 担当者
  python scripts/lumi.py export <出力.xlsx>        全テーブルをExcelに書き出し
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lumi_growth_os import backup, config, db, importer, seed  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lumi Spark Growth OS CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--no-samples", action="store_true")
    p_backup = sub.add_parser("backup")
    p_backup.add_argument("--label", default="manual")
    sub.add_parser("list-backups")
    p_restore = sub.add_parser("restore")
    p_restore.add_argument("file")
    p_restore.add_argument("--yes", action="store_true")
    p_import = sub.add_parser("import")
    p_import.add_argument("file")
    p_import.add_argument("--sheet")
    p_import.add_argument("--dry-run", action="store_true")
    p_import.add_argument("--actor", required=True)
    p_import.add_argument("--as-sample", action="store_true", help="記事をサンプル（実績ではない）として登録")
    p_export = sub.add_parser("export")
    p_export.add_argument("output")
    args = parser.parse_args(argv)

    db_file = config.db_path()
    if args.command == "init":
        conn = db.connect(db_file)
        db.init_db(conn)
        created = seed.seed_all(conn, include_samples=not args.no_samples)
        print(f"DB: {db_file}　初期データ投入: {'実施' if created else '済み（変更なし）'}")
    elif args.command == "backup":
        print(backup.create_backup(db_file, config.backup_dir(), label=args.label))
    elif args.command == "list-backups":
        for item in backup.list_backups(config.backup_dir()):
            print(item["path"].name, item.get("created_at"), item.get("counts"))
    elif args.command == "restore":
        if not args.yes:
            parser.error("復旧は現在のDBを置き換えます。確認のうえ --yes を付けて実行してください")
        target = Path(args.file)
        if not target.exists():
            target = config.backup_dir() / args.file
        pre = backup.restore_backup(target, db_file, config.backup_dir())
        print(f"復旧しました。復旧前の状態: {pre}")
    elif args.command == "import":
        conn = db.connect(db_file)
        db.init_db(conn)
        if not args.dry_run:
            print("取込前バックアップ:", backup.create_backup(db_file, config.backup_dir(), label="pre-import"))
        report = importer.import_file(conn, args.file, args.actor, sheet=args.sheet, dry_run=args.dry_run,
                                     as_sample=args.as_sample)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    elif args.command == "export":
        conn = db.connect(db_file)
        print(backup.export_excel(conn, args.output))


if __name__ == "__main__":
    main()

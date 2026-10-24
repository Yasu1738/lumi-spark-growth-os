"""バックアップと復旧。

- バックアップはSQLiteのオンラインバックアップAPIで取得し、SHA-256と件数をマニフェストに残す。
- 復旧前に必ず現在のDBを退避（pre-restore バックアップ）し、復旧元の整合性を検証する。
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import db

COUNT_TABLES = ["articles", "hubs", "hub_path_steps", "link_proposals", "article_metrics",
                "account_snapshots", "ranking_entries", "funnel_observations", "reader_insights",
                "audit_log"]


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table_counts(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in COUNT_TABLES}


def create_backup(db_file, backup_dir, label="manual") -> Path:
    db_file, backup_dir = Path(db_file), Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = "".join(c for c in label if c.isalnum() or c in "-_") or "manual"
    target = backup_dir / f"lumi_{stamp}_{safe_label}.db"
    src = sqlite3.connect(str(db_file))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    check = db.connect(target)
    try:
        counts = table_counts(check)
    finally:
        check.close()
    manifest = {
        "backup_file": target.name, "source_db": str(db_file), "created_at": datetime.now().isoformat(),
        "label": safe_label, "sha256": _sha256(target), "counts": counts,
    }
    target.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def list_backups(backup_dir):
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []
    items = []
    for path in sorted(backup_dir.glob("lumi_*.db"), reverse=True):
        manifest_path = path.with_suffix(".json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        items.append({"path": path, **manifest})
    return items


def verify_backup(backup_file) -> list:
    """問題のリストを返す（空なら復旧可能）。"""
    backup_file = Path(backup_file)
    problems = []
    if not backup_file.exists():
        return [f"ファイルがありません: {backup_file}"]
    manifest_path = backup_file.with_suffix(".json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") and manifest["sha256"] != _sha256(backup_file):
            problems.append("SHA-256がマニフェストと一致しません（ファイルが変更された可能性）")
    try:
        conn = sqlite3.connect(f"file:{backup_file}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                problems.append(f"整合性チェック失敗: {result}")
            missing = db.REQUIRED_TABLES - db.table_names(conn)
            if missing:
                problems.append(f"必要なテーブルがありません: {', '.join(sorted(missing))}")
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        problems.append(f"SQLiteとして開けません: {exc}")
    return problems


def restore_backup(backup_file, db_file, backup_dir) -> Path:
    """バックアップから復旧する。復旧前のDBを退避し、その退避ファイルのパスを返す。"""
    problems = verify_backup(backup_file)
    if problems:
        raise ValueError("復旧を中止しました: " + " / ".join(problems))
    db_file = Path(db_file)
    pre_restore = create_backup(db_file, backup_dir, label="pre-restore") if db_file.exists() else None
    src = sqlite3.connect(f"file:{backup_file}?mode=ro", uri=True)
    dst = sqlite3.connect(str(db_file))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return pre_restore


def export_excel(conn, path) -> Path:
    """全テーブルを人間が読めるExcelへ書き出す（新規ファイルのみ。既存ファイルは上書きしない）。"""
    import pandas as pd

    path = Path(path)
    if path.exists():
        raise FileExistsError(f"既存ファイルは上書きしません: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for table in sorted(db.REQUIRED_TABLES):
            frame = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            frame.to_excel(writer, sheet_name=table[:31], index=False)
    return path

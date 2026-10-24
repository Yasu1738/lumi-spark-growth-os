"""パス設定。環境変数 LUMI_DB_PATH / LUMI_BACKUP_DIR で上書きできる。"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "lumi_growth.db"
DEFAULT_BACKUP_DIR = ROOT / "backups"


def db_path() -> Path:
    return Path(os.environ.get("LUMI_DB_PATH", DEFAULT_DB_PATH))


def backup_dir() -> Path:
    return Path(os.environ.get("LUMI_BACKUP_DIR", DEFAULT_BACKUP_DIR))

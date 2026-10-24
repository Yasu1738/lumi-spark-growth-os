import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lumi_growth_os import db, importer, repository, seed  # noqa: E402

ACTOR = "テスト担当"


@pytest.fixture
def db_file(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_file):
    connection = db.connect(db_file)
    db.init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def seeded(conn):
    seed.seed_all(conn, include_samples=True)
    return conn


def make_article(conn, article_id, **kwargs):
    data = {"article_id": article_id, "title": f"記事{article_id}", **kwargs}
    return repository.create_article(conn, data, ACTOR)


def make_verified_article(conn, article_id, url_suffix, **kwargs):
    """URL・タイトル・本文が確認済みの実記事（本番反映可能条件を満たす）。"""
    return make_article(
        conn, article_id, url=f"https://note.com/lumispark/n/n{url_suffix}", url_status="表示確認済み",
        title_status="確認済み", content_reviewed=True, **kwargs,
    )


def write_legacy_xlsx(path, rows):
    """note記事運用台帳 Ver.0.1「記事台帳」と同じ38列ヘッダーのxlsxを作る。"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "記事台帳"
    ws.append(importer.LEGACY_LEDGER_COLUMNS)
    for row in rows:
        ws.append([row.get(c) for c in importer.LEGACY_LEDGER_COLUMNS])
    for _ in range(5):  # テンプレートの空行
        ws.append([None] * len(importer.LEGACY_LEDGER_COLUMNS))
    account = wb.create_sheet("日次アカウント")
    account.append(importer.LEGACY_ACCOUNT_COLUMNS)
    account.append(["2026-09-09 20:09", "2026-08-13", "2026-09-09", 152901, 3370, 1968, 97, None, 72,
                    None, None, None, None, None, None, "フォロワー増100+人"])
    wb.save(path)
    return path

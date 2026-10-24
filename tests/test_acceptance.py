"""MVP受入条件 1〜14 のテスト。関数名の test_acNN が受入条件の番号に対応する。"""

import csv
import json
import os
import socket

import pytest

from conftest import ACTOR, ROOT, make_article, make_verified_article, write_legacy_xlsx
from lumi_growth_os import backup, importer, metrics, recommend, repository, seed, textgen
from lumi_growth_os.validation import ValidationError, validate_url


# 1. 記事10件以上を管理できる
def test_ac01_manage_ten_or_more_articles(conn):
    for i in range(1, 13):
        make_article(conn, f"T-{i:03d}", theme="AI" if i % 2 else "ORG", topic_tags="AI活用")
    assert len(repository.list_articles(conn)) == 12
    updated = repository.update_article(conn, "T-005", {"title": "改題", "human_code": "H3"}, ACTOR)
    assert updated["title"] == "改題" and updated["human_code"] == "H3"
    with pytest.raises(ValidationError):
        make_article(conn, "T-005")  # 重複IDは登録不可


def test_ac01_seed_has_more_than_ten_articles(seeded):
    articles = repository.list_articles(seeded)
    assert len(articles) >= 10
    assert len([a for a in articles if a["data_kind"] == "real"]) == 9


# 2. 3ハブを表示・編集できる
def test_ac02_three_hubs_display_and_edit(seeded):
    hubs = repository.list_hubs(seeded)
    assert [h["hub_id"] for h in hubs] == ["HUB-AI", "HUB-ORG", "HUB-REG"]
    assert repository.get_hub(seeded, "HUB-ORG")["status"].startswith("仮登録")
    repository.update_hub(seeded, "HUB-REG", {"name": "地域産業の未来（改）", "related_topics": "町工場"}, ACTOR)
    assert repository.get_hub(seeded, "HUB-REG")["name"] == "地域産業の未来（改）"
    steps = repository.replace_path_steps(seeded, "HUB-AI", [
        {"label": "AIエージェント", "funnel_stage": "信頼"},
        {"label": "業務設計", "funnel_stage": "信頼", "article_id": "LS-A004"},
        {"label": "メンバーシップ", "funnel_stage": "参加意向"},
    ], ACTOR)
    assert [s["label"] for s in steps] == ["AIエージェント", "業務設計", "メンバーシップ"]
    assert steps[1]["article_id"] == "LS-A004"
    with pytest.raises(ValidationError):
        repository.replace_path_steps(seeded, "HUB-AI", [{"label": "x", "funnel_stage": "不明な段階"}], ACTOR)


def test_ac02_hub_page_renders_three_hubs(seeded, db_file, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("LUMI_DB_PATH", str(db_file))
    at = AppTest.from_file(str(ROOT / "app" / "views" / "hubs.py"), default_timeout=60).run()
    assert not at.exception
    titles = [s.value for s in at.subheader]
    assert any("HUB-AI" in t for t in titles) and any("HUB-ORG" in t for t in titles) \
        and any("HUB-REG" in t for t in titles)


# 3. 関連記事リンク案を合計9件以上登録できる
def test_ac03_nine_or_more_link_proposals(seeded):
    real_links = [l for l in repository.list_links(seeded) if l["data_kind"] == "real"]
    assert len(real_links) >= 9
    for hub in repository.list_hubs(seeded):
        per_hub = [l for l in real_links if l["source_article_id"] == hub["hub_article_id"]]
        assert 2 <= len(per_hub) <= 3
    # 未確認URLを含むため、すべて仮案であり本番反映可能と表示しない
    for link in real_links:
        readiness = repository.link_readiness(seeded, link)
        assert readiness["label"] == "仮案（本番反映不可）"
        assert readiness["production_ready"] is False


# 4. 各リンク案の根拠・承認状態が記録できる
def test_ac04_link_evidence_status_and_audit(conn):
    make_verified_article(conn, "A", "000000000001", theme="AI", topic_tags="AI活用,業務設計")
    make_verified_article(conn, "B", "000000000002", theme="AI", topic_tags="AI活用")
    link = repository.create_link(conn, "A", "B", ACTOR, reason="共通タグ", evidence="手動判断",
                                  reader_value="実践を知れる", anchor_text="続きはこちら",
                                  insert_position="結びの直前")
    assert link["status"] == "提案" and link["evidence"] == "手動判断"
    with pytest.raises(ValidationError):  # 段階の飛ばしは不可
        repository.transition_link(conn, link["link_id"], "承認", ACTOR, approver="西冨")
    repository.transition_link(conn, link["link_id"], "確認", ACTOR, comment="本文を確認")
    assert repository.get_link(conn, link["link_id"])["relevance_status"] == "確認済み"
    with pytest.raises(ValidationError):  # 承認者なしの承認は不可
        repository.transition_link(conn, link["link_id"], "承認", ACTOR)
    repository.transition_link(conn, link["link_id"], "承認", ACTOR, approver="西冨")
    assert repository.link_readiness(conn, repository.get_link(conn, link["link_id"]))["production_ready"]
    repository.transition_link(conn, link["link_id"], "note反映", ACTOR, comment="人間がnoteで設置")
    repository.transition_link(conn, link["link_id"], "表示確認", ACTOR)
    assert repository.get_link(conn, link["link_id"])["status"] == "表示確認"
    logs = repository.list_audit(conn, entity_type="link", entity_id=link["link_id"])
    actions = [l["action"] for l in logs]
    assert "リンク状態変更: 確認→承認" in actions
    approval = next(l for l in logs if l["action"] == "リンク状態変更: 確認→承認")
    assert approval["actor"] == ACTOR and approval["approver"] == "西冨" and approval["at"]
    assert approval["before_json"] and approval["after_json"]


def test_ac04_draft_cannot_be_approved_or_published(seeded):
    link = repository.list_links(seeded, source_id="LS-A001")[0]
    repository.transition_link(seeded, link["link_id"], "確認", ACTOR)
    after = repository.get_link(seeded, link["link_id"])
    assert after["relevance_status"] != "確認済み"  # 本文未確認の記事を含む
    with pytest.raises(ValidationError, match="仮案"):
        repository.transition_link(seeded, link["link_id"], "承認", ACTOR, approver="西冨")
    repository.transition_link(seeded, link["link_id"], "却下", ACTOR, comment="テスト")
    repository.transition_link(seeded, link["link_id"], "提案", ACTOR)


def test_ac04_writes_require_actor(conn):
    with pytest.raises(ValidationError, match="担当者"):
        repository.create_article(conn, {"article_id": "X1", "title": "t"}, "  ")


# 5. note貼り付け用文章を生成できる
def test_ac05_paste_text_draft_hides_unverified_urls(seeded):
    result = textgen.generate_guidance(seeded, "LS-A001")
    assert result["text"].startswith("AIに仕事を任せることを、もう少し具体的に考えたい方へ。")
    assert textgen.URL_PLACEHOLDER in result["text"]
    assert result["production_ready"] is False
    assert any("仮案" in w for w in result["warnings"])


def test_ac05_paste_text_when_production_ready(conn):
    make_verified_article(conn, "HUB", "aaaaaaaaaaaa", theme="AI", topic_tags="AI活用,業務設計")
    make_verified_article(conn, "SPOKE", "bbbbbbbbbbbb", theme="AI", topic_tags="業務設計",
                          primary_purpose="専門・実務")
    link = repository.create_link(conn, "HUB", "SPOKE", ACTOR, anchor_text="業務設計を考えたい方へ")
    for status in ("確認", "承認"):
        repository.transition_link(conn, link["link_id"], status, ACTOR, approver="西冨")
    result = textgen.generate_guidance(conn, "HUB")
    assert result["production_ready"] is True
    assert "https://note.com/lumispark/n/nbbbbbbbbbbbb" in result["text"]
    assert textgen.URL_PLACEHOLDER not in result["text"]
    assert "実際の業務設計の視点から掘り下げています" in result["text"]


# 6. Excel・CSVを非破壊で取り込める
LEGACY_ROWS = [
    {"Article_ID": "OLD-001", "公開日時": "2026-09-25 07:00", "タイトル": "旧台帳の記事1",
     "URL": "https://note.com/lumispark/n/n0123456789ab", "主目的": "認知", "テーマ": "AI",
     "24h PV": 120, "24h スキ": 10, "24h コメント": 0, "24h期限": "2026-09-26 07:00",
     "72h PV": None, "72h スキ": None, "メモ": "メモ1", "4象限": "判定待ち"},
    {"Article_ID": "OLD-002", "タイトル": "旧台帳の記事2", "URL": "note.com/lumispark/n/xyz",
     "テーマ": "組織", "フォロー増(参考)": "100+"},
    {"Article_ID": None, "タイトル": "ID空欄の記事"},
]


def test_ac06_excel_import_is_non_destructive(conn, tmp_path):
    path = write_legacy_xlsx(tmp_path / "ledger.xlsx", LEGACY_ROWS)
    stat_before = path.stat().st_mtime_ns
    report = importer.import_file(conn, path, ACTOR)
    assert report["format"] == "legacy_ledger"
    assert report["source_unchanged"] and report["sha256_before"] == report["sha256_after"]
    assert path.stat().st_mtime_ns == stat_before
    assert report["inserted"] == 3 and report["metrics_inserted"] == 1
    old1 = repository.get_article(conn, "OLD-001")
    assert old1["url_status"] == "未確認"  # 旧台帳のURLでも人間の確認前は未確認
    legacy = json.loads(old1["legacy_json"])
    assert legacy["4象限"] == "判定待ち"  # 新モデルにない列も保全
    old2 = repository.get_article(conn, "OLD-002")
    assert old2["url_status"] == "不正" and old2["theme"] is None  # 「組織」は推測でORGにしない
    assert json.loads(old2["legacy_json"])["テーマ"] == "組織"
    # 既存IDは上書きしない
    repository.update_article(conn, "OLD-001", {"title": "手動で修正"}, ACTOR)
    report2 = importer.import_file(conn, path, ACTOR)
    assert repository.get_article(conn, "OLD-001")["title"] == "手動で修正"
    assert any("上書きしません" in s for s in report2["skipped"])


def test_ac06_dry_run_does_not_change_db(conn, tmp_path):
    path = write_legacy_xlsx(tmp_path / "ledger.xlsx", LEGACY_ROWS)
    report = importer.import_file(conn, path, ACTOR, dry_run=True)
    assert report["inserted"] == 3
    assert repository.list_articles(conn) == []
    assert conn.execute("SELECT COUNT(*) FROM article_metrics").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0


def test_ac06_account_sheet_and_csv_import(conn, tmp_path):
    path = write_legacy_xlsx(tmp_path / "ledger.xlsx", [])
    report = importer.import_file(conn, path, ACTOR, sheet="日次アカウント")
    assert report["format"] == "legacy_account" and report["inserted"] == 1
    snap = repository.list_account_snapshots(conn)[0]
    assert snap["pv"] == 3370 and snap["follows"] is None
    csv_path = tmp_path / "articles.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["article_id", "title", "theme", "url"])
        writer.writerow(["CSV-1", "CSVの記事", "REG", ""])
        writer.writerow(["CSV-2", "CSVの記事2", "AI", "https://note.com/lumispark/n/nabcdefabcdef"])
    before = importer.file_sha256(csv_path)
    report = importer.import_file(conn, csv_path, ACTOR)
    assert report["format"] == "native_articles" and report["inserted"] == 2
    assert importer.file_sha256(csv_path) == before


def test_ac06_sample_rows_are_never_imported_as_real(conn, tmp_path):
    rows = [{"Article_ID": "S-1", "タイトル": "【サンプル】練習用"}, {"Article_ID": "R-1", "タイトル": "通常の記事"}]
    path = write_legacy_xlsx(tmp_path / "ledger.xlsx", rows)
    importer.import_file(conn, path, ACTOR)
    assert repository.get_article(conn, "S-1")["data_kind"] == "sample"
    assert repository.get_article(conn, "R-1")["data_kind"] == "real"
    path2 = write_legacy_xlsx(tmp_path / "ledger2.xlsx", [{"Article_ID": "S-2", "タイトル": "練習"}])
    importer.import_file(conn, path2, ACTOR, as_sample=True)
    assert repository.get_article(conn, "S-2")["data_kind"] == "sample"


def test_ac06_cp932_csv(conn, tmp_path):
    csv_path = tmp_path / "sjis.csv"
    csv_path.write_bytes("article_id,title\nSJ-1,シフトJISの記事\n".encode("cp932"))
    report = importer.import_file(conn, csv_path, ACTOR)
    assert report["inserted"] == 1
    assert repository.get_article(conn, "SJ-1")["title"] == "シフトJISの記事"


# 7. 未確認URLを未確認として管理できる
def test_ac07_unverified_urls(seeded):
    hub_org = repository.get_article(seeded, "LS-A002")
    assert hub_org["url"] is None and hub_org["url_status"] == "未確認"
    assert hub_org["title_status"] == "一部のみ"
    with pytest.raises(ValidationError):
        repository.update_article(seeded, "LS-A002", {"url_status": "表示確認済み"}, ACTOR)
    # URLを変更すると確認状態は未確認に戻る
    repository.update_article(seeded, "LS-A001", {"url": "https://note.com/lumispark/n/n111111111111"}, ACTOR)
    assert repository.get_article(seeded, "LS-A001")["url_status"] == "未確認"
    unverified = repository.pending_human_items(seeded)["URL未確認の記事"]
    assert {"LS-A002", "LS-A004"} <= {a["article_id"] for a in unverified}


def test_ac07_recommendations_label_unreviewed_relevance(seeded):
    for rec in recommend.recommend(seeded, "LS-A002", limit=3):
        assert rec["relevance_basis"] == "タイトル・タグからのルール推定（本文未確認）"
        assert rec["approval_status"].startswith("未登録")


# 8. 欠損値と0を区別できる
def test_ac08_missing_vs_zero(conn):
    make_article(conn, "M1", published_at="2026-10-01 07:00")
    row = repository.add_metric(conn, "M1", "2026-10-02 07:00", "24h",
                                {"pv": 100, "likes": "", "comments": 0, "imp": None}, "管理画面", ACTOR)
    assert row["likes"] is None and row["comments"] == 0 and row["imp"] is None
    p = metrics.compute_proxies(row)
    assert p["comment_pv_proxy"] == 0.0 and p["like_pv_proxy"] is None and p["imp_pv_proxy"] is None
    with pytest.raises(ValidationError, match="正確な数値ではありません"):
        repository.add_metric(conn, "M1", "2026-10-02 07:00", "24h", {"follows": "100+"}, "画面", ACTOR)
    with pytest.raises(ValidationError):
        repository.add_metric(conn, "M1", "2026-10-02 07:00", "24h", {}, "画面", ACTOR)


def test_ac08_import_keeps_blank_as_null(conn, tmp_path):
    path = write_legacy_xlsx(tmp_path / "ledger.xlsx", LEGACY_ROWS)
    importer.import_file(conn, path, ACTOR)
    m = repository.list_metrics(conn, "OLD-001")[0]
    assert m["pv"] == 120 and m["comments"] == 0 and m["imp"] is None
    assert repository.list_metrics(conn, "OLD-001", window_type="72h") == []  # 空欄から72h値を作らない
    snap_follow = repository.get_article(conn, "OLD-002")
    assert json.loads(snap_follow["legacy_json"])["フォロー増(参考)"] == "100+"


# 9. 計測日時付きの実績を保存できる
def test_ac09_metrics_require_timestamp_and_respect_windows(conn):
    make_article(conn, "W1", published_at="2026-10-01 07:00")
    make_article(conn, "W2", published_at="2026-10-01")  # 時刻不明
    with pytest.raises(ValidationError, match="計測日時"):
        repository.add_metric(conn, "W1", None, "24h", {"pv": 1}, "画面", ACTOR)
    with pytest.raises(ValidationError, match="出典"):
        repository.add_metric(conn, "W1", "2026-10-02 07:00", "24h", {"pv": 1}, "", ACTOR)
    ok = repository.add_metric(conn, "W1", "2026-10-04 08:00", "72h", {"pv": 300}, "画面", ACTOR)
    assert ok["measured_at"] == "2026-10-04 08:00" and ok["hours_since_publish"] == 73.0
    # 後から取得した累積値を72h値として登録できない
    with pytest.raises(ValidationError, match="cumulative"):
        repository.add_metric(conn, "W1", "2026-10-20 08:00", "72h", {"pv": 900}, "画面", ACTOR)
    with pytest.raises(ValidationError, match="時刻"):
        repository.add_metric(conn, "W2", "2026-10-02 07:00", "24h", {"pv": 10}, "画面", ACTOR)
    with pytest.raises(ValidationError, match="公開日時より前"):
        repository.add_metric(conn, "W1", "2026-09-30 07:00", "cumulative", {"pv": 10}, "画面", ACTOR)
    cum = repository.add_metric(conn, "W1", "2026-10-20 08:00", "cumulative", {"pv": 900}, "画面", ACTOR)
    assert cum["window_type"] == "cumulative"


def test_ac09_article_and_account_metrics_are_separate(seeded):
    assert all(m["article_id"] for m in repository.list_metrics(seeded))
    snaps = repository.list_account_snapshots(seeded)
    assert {s["measured_at"] for s in snaps if s["data_kind"] == "real"} == {"2026-09-09 20:09", "2026-08-23"}


# 10. Proxy指標が正しく計算される
def test_ac10_proxy_calculation():
    row = {"imp": 2000, "pv": 150, "likes": 12, "comments": 3}
    p = metrics.compute_proxies(row)
    assert p == {"imp_pv_proxy": 7.5, "like_pv_proxy": 8.0, "comment_pv_proxy": 2.0}
    assert metrics.proxy(1, 3) == 33.33
    assert metrics.proxy(5, 0) is None
    assert metrics.proxy(None, 10) is None
    assert metrics.proxy(0, 10) == 0.0


def test_ac10_comparability_warnings(seeded):
    cumulative = repository.list_metrics(seeded, window_type="cumulative")
    warnings = metrics.comparability_warnings(cumulative)
    assert any("累積値" in w for w in warnings)
    assert any("出典" in w for w in warnings)
    mixed = repository.list_metrics(seeded, article_id="SMP-001")
    assert any("計測区分が混在" in w for w in metrics.comparability_warnings(mixed))
    assert any("スキがPVを上回って" in w for w in metrics.row_warnings({"likes": 1968, "pv": 1000}))


# 11. 不正URL、重複リンク、自己リンクを検出できる
@pytest.mark.parametrize("url,kind", [
    ("https://note.com/lumispark/n/n3466216b81dc", "note_article"),
    ("https://note.com/other/n/n3466216b81dc", "note_article"),
    ("http://note.com/lumispark/n/n3466216b81dc", "invalid"),
    ("https://note.com/lumispark/n/3466216b81dc", "invalid"),
    ("https://note.com/lumispark/n/n3466216b81dcX", "invalid"),
    ("note.com/lumispark", "invalid"),
    ("https://note.com/lumispark/n/n3466 216b81dc", "invalid"),
    ("https://example.com/page", "other_https"),
    ("", "empty"),
])
def test_ac11_url_validation(url, kind):
    assert validate_url(url)[0] == kind


def test_ac11_duplicate_and_self_links(conn):
    make_article(conn, "A")
    make_article(conn, "B")
    with pytest.raises(ValidationError, match="自己リンク"):
        repository.create_link(conn, "A", "A", ACTOR)
    repository.create_link(conn, "A", "B", ACTOR)
    with pytest.raises(ValidationError, match="重複リンク"):
        repository.create_link(conn, "A", "B", ACTOR)
    repository.create_link(conn, "B", "A", ACTOR)  # 逆方向は別リンク
    with pytest.raises(ValidationError, match="不正なURL"):
        make_article(conn, "C", url="http://note.com/x")
    repository.create_article(conn, {"article_id": "D", "title": "d", "url": "note.com/bad"}, ACTOR, strict_url=False)
    assert any("不正URL" in i for i in repository.check_link_candidate(conn, "A", "D"))
    assert any("存在しません" in i for i in repository.check_link_candidate(conn, "A", "ZZZ"))


def test_ac11_link_csv_import_reports_issues(conn, tmp_path):
    make_article(conn, "A")
    make_article(conn, "B")
    path = tmp_path / "links.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source_article_id", "target_article_id", "reason"])
        w.writerow(["A", "B", "ok"])
        w.writerow(["A", "B", "dup"])
        w.writerow(["A", "A", "self"])
    report = importer.import_file(conn, path, ACTOR)
    assert report["inserted"] == 1
    assert any("重複リンク" in s for s in report["skipped"])
    assert any("自己リンク" in s for s in report["skipped"])


def test_ac11_recommend_never_returns_self_or_existing(seeded):
    for article in repository.list_articles(seeded):
        recs = recommend.recommend(seeded, article["article_id"], limit=3)
        existing = {l["target_article_id"] for l in repository.list_links(seeded, source_id=article["article_id"])}
        for rec in recs:
            assert rec["target_article_id"] != article["article_id"]
            assert rec["target_article_id"] not in existing
            if article["data_kind"] == "real":
                assert repository.get_article(seeded, rec["target_article_id"])["data_kind"] == "real"


# 12. バックアップから復旧できる
def test_ac12_backup_and_restore(seeded, db_file, tmp_path):
    backup_dir = tmp_path / "backups"
    snapshot = backup.create_backup(db_file, backup_dir, label="test")
    assert backup.verify_backup(snapshot) == []
    manifest = json.loads(snapshot.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["counts"]["articles"] == 15
    repository.update_article(seeded, "LS-A001", {"title": "壊れた変更"}, ACTOR)
    make_article(seeded, "AFTER-BACKUP")
    pre = backup.restore_backup(snapshot, db_file, backup_dir)
    assert pre is not None and pre.exists()
    assert repository.get_article(seeded, "LS-A001")["title"].startswith("プロンプトが上手い人より")
    assert repository.get_article(seeded, "AFTER-BACKUP") is None
    # 退避した pre-restore からさらに戻せる
    backup.restore_backup(pre, db_file, backup_dir)
    assert repository.get_article(seeded, "AFTER-BACKUP") is not None


def test_ac12_corrupted_backup_is_refused(seeded, db_file, tmp_path):
    backup_dir = tmp_path / "backups"
    snapshot = backup.create_backup(db_file, backup_dir)
    with open(snapshot, "r+b") as fh:
        fh.seek(200)
        fh.write(b"corrupted!!")
    assert backup.verify_backup(snapshot)
    with pytest.raises(ValueError, match="中止"):
        backup.restore_backup(snapshot, db_file, backup_dir)
    assert len(repository.list_articles(seeded)) == 15


def test_ac12_excel_export_never_overwrites(seeded, tmp_path):
    out = backup.export_excel(seeded, tmp_path / "export.xlsx")
    assert out.exists()
    with pytest.raises(FileExistsError):
        backup.export_excel(seeded, out)


# 13. APIキーなしで基本機能が動作する
def test_ac13_works_without_api_keys(conn, monkeypatch, tmp_path):
    for key in list(os.environ):
        if "KEY" in key or "TOKEN" in key or "SECRET" in key:
            monkeypatch.delenv(key, raising=False)
    seed.seed_all(conn)
    assert recommend.recommend(conn, "LS-A001", include_existing=True)
    assert textgen.generate_guidance(conn, "LS-A002")["text"]
    for path in ROOT.joinpath("lumi_growth_os").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "API_KEY" not in text and "anthropic" not in text.lower() and "openai" not in text.lower()


# 14. noteへの外部操作が発生しない
def test_ac14_no_network_access_in_core_workflow(conn, db_file, tmp_path, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError(f"外部通信が試みられました: {args}")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    seed.seed_all(conn)
    recs = recommend.recommend(conn, "LS-A003")
    recommend.save_recommendations(conn, "LS-A003", recs, ACTOR)
    textgen.generate_guidance(conn, "LS-A003")
    path = write_legacy_xlsx(tmp_path / "ledger.xlsx", LEGACY_ROWS)
    importer.import_file(conn, path, ACTOR)
    snapshot = backup.create_backup(db_file, tmp_path / "b")
    backup.restore_backup(snapshot, db_file, tmp_path / "b")


def test_ac14_no_network_libraries_in_source():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    forbidden = ["import requests", "import urllib", "from urllib", "http.client", "import socket",
                 "import httpx", "aiohttp", "selenium", "playwright", "webbrowser"]
    for folder in ("lumi_growth_os", "app"):
        for path in (root / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for word in forbidden:
                assert word not in text, f"{path} に {word} が含まれています"


def test_ac14_streamlit_telemetry_disabled():
    from pathlib import Path

    config = (Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config
    assert 'address = "localhost"' in config

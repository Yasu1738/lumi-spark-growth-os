"""スマホ版の毎日の自動更新（計画づくり）のテスト。URLは試験用の架空のもの。"""

import json

from lumi_growth_os import mobile_sync, rss
from test_rss import FEED

NOW = "2026-10-25 06:47"


def article(i, title, url=None, theme=None, tags=None, title_status="確認済み"):
    return {"id": i, "title": title, "title_status": title_status, "url": url,
            "url_status": "オーナー提示" if url else "未確認", "theme": theme, "topic_tags": tags, "data_kind": "real"}


def dump():
    return {
        "articles": {
            "LS-A001": article("LS-A001", "ハブ記事", "https://note.com/lumispark/n/n0000000000a1", "ORG", "経営者依存,事業承継"),
            "LS-A007": article("LS-A007", "社長がいなくなったら、会社は何日もつのか", None, "ORG", "経営者依存"),
            "LS-A004": article("LS-A004", "LINEとCodexをつないだら…（以降未確認）", None, "AI", "AI活用", "一部のみ"),
        },
        "links": {"LNK-0001": {"id": "LNK-0001", "source": "LS-A001", "target": "LS-A007", "status": "提案"}},
        "hubs": {"HUB-ORG": {"id": "HUB-ORG", "name": "経営", "hub_article_id": "LS-A001", "related_topics": "事業承継"}},
        "versions": {"LS-A001": 2, "LS-A007": 1, "LS-A004": 3},
    }


def test_plan_imports_estimates_and_proposes_only_ready_links():
    estimates = {"LS-A008": {"theme": "ORG", "topic_tags": "経営者依存,組織づくり"},
                 "LS-A001": {"theme": "AI", "topic_tags": "上書きしない"}}
    writes, summary = mobile_sync.build_plan(dump(), rss.parse_rss(FEED), estimates, NOW, "テスト")
    by = {(w["collection"], w["doc_id"]): w for w in writes}
    # RSSで途中までのタイトルが補われ、版番号で上書き保護される
    upd = by[("articles", "LS-A004")]
    assert upd["op"] == "update" and upd["if_version"] == 3 and upd["data"]["title_status"] == "確認済み"
    assert by[("articles", "LS-A007")]["data"]["url"] == "https://note.com/lumispark/n/n00000000000a"
    # 人が入れたテーマ・タグは上書きしない
    assert ("articles", "LS-A001") not in by
    # 新しい記事に推定タグが入り、推定であることが記録される
    new = by[("articles", "LS-A008")]["data"]  # 既存の最大番号 LS-A007 の続き
    assert new["title"] == "試験用の新しい記事" and new["theme"] == "ORG" and new["tags_estimated"].startswith("Claudeがタイトルから推定")
    # 提案は、まだ提案のない記事から、URL・タイトルのそろった記事へだけ
    links = [w["data"] for w in writes if w["collection"] == "links"]
    assert links and all(l["status"] == "提案" for l in links)
    assert {l["id"] for l in links} >= {"LNK-0002"}
    assert all(l["source"] != "LS-A001" for l in links)  # 既に提案があるハブからは作らない
    assert any(l["source"] == "LS-A008" and l["target"] == "LS-A007" for l in links)
    assert by[("audit", "sync-2026-10-25T0647")]["data"]["action"].startswith("毎日の自動更新")
    assert ("LS-A008", "試験用の新しい記事") in summary["created"]


def test_second_run_is_noop_except_audit(tmp_path):
    first, _ = mobile_sync.build_plan(dump(), rss.parse_rss(FEED), {}, NOW, "テスト")
    d = dump()
    for w in first:
        coll = w["collection"]
        if coll in ("articles", "links"):
            d[coll][w["doc_id"]] = {**d[coll].get(w["doc_id"], {}), **w["data"], "id": w["doc_id"]}
    second, summary = mobile_sync.build_plan(d, rss.parse_rss(FEED), {}, NOW, "テスト")
    assert [w["collection"] for w in second] == ["audit"]
    assert not summary["created"] and not summary["links"]


def test_write_batches_splits_by_50(tmp_path):
    writes = [{"op": "set", "collection": "audit", "doc_id": f"x{i}", "data": {"i": i}} for i in range(120)]
    files = mobile_sync.write_batches(writes, tmp_path)
    sizes = [len(json.loads(f.read_text(encoding="utf-8"))) for f in files]
    assert sizes == [50, 50, 20]
    first = json.loads(files[0].read_text(encoding="utf-8"))[0]
    assert "data" not in first and json.loads(open(first["file_path"], encoding="utf-8").read()) == {"i": 0}

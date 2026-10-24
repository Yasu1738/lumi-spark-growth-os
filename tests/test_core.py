"""受入条件以外の振る舞いのテスト。"""

import glob

import pytest

from conftest import ACTOR, ROOT, make_article
from lumi_growth_os import codes, metrics, recommend, repository, seed
from lumi_growth_os.validation import ValidationError, parse_count, parse_datetime


def test_seed_is_idempotent(conn):
    assert seed.seed_all(conn) is True
    assert seed.seed_all(conn) is False
    assert len(repository.list_articles(conn)) == 15


def test_seed_real_articles_have_no_invented_codes_or_urls(seeded):
    for a in repository.list_articles(seeded, "real"):
        assert a["title_structure"] is None and a["human_code"] is None
        assert a["source"]
        if a["article_id"] not in ("LS-A001", "LS-A002", "LS-A003"):  # オーナー提示URLのみ
            assert a["url"] is None


def test_sample_data_is_marked(seeded):
    for a in repository.list_articles(seeded, "sample"):
        assert a["title"].startswith("【サンプル】")
    for m in repository.list_metrics(seeded):
        if m["article_id"].startswith("SMP-"):
            assert m["data_kind"] == "sample"


def test_ranking_snapshot_keeps_unmatched_entries(seeded):
    snap = repository.list_rankings(seeded)[0]
    assert [e["value"] for e in snap["entries"]] == seed.RANKING_VALUES
    unmatched = [e for e in snap["entries"] if e["article_id"] is None]
    assert len(unmatched) == 7
    assert all(e["match_status"].startswith("未照合") for e in unmatched)


def test_parse_helpers():
    assert parse_count("1,234") == 1234 and parse_count(0) == 0 and parse_count("") is None
    with pytest.raises(ValidationError):
        parse_count(1.5)
    with pytest.raises(ValidationError):
        parse_count(-1)
    assert parse_datetime("2026/10/24 11:51") == "2026-10-24 11:51"
    assert parse_datetime("2026-10-24") == "2026-10-24"
    with pytest.raises(ValidationError):
        parse_datetime("昨日")


def test_codes_are_validated(conn):
    with pytest.raises(ValidationError):
        make_article(conn, "X", human_code="H9")
    with pytest.raises(ValidationError):
        make_article(conn, "X", title_structure="T01,T11")
    a = make_article(conn, "X", title_structure="t02, T05,T02")
    assert a["title_structure"] == "T02,T05"


def test_funnel_observation_requires_source(conn):
    with pytest.raises(ValidationError, match="出典"):
        repository.add_funnel_observation(conn, {"observed_at": "2026-10-24", "stage": "有料参加", "value": 3}, ACTOR)
    with pytest.raises(ValidationError, match="値は必須"):
        repository.add_funnel_observation(conn, {"observed_at": "2026-10-24", "stage": "有料参加",
                                                 "source": "画面"}, ACTOR)
    row = repository.add_funnel_observation(conn, {"observed_at": "2026-10-24", "stage": "有料参加", "value": 0,
                                                   "source": "noteメンバーシップ管理画面"}, ACTOR)
    assert row["value"] == 0


def test_reader_insight_rejects_personal_handles(conn):
    with pytest.raises(ValidationError, match="個人"):
        repository.add_reader_insight(conn, {"summary": "@someone さんの意見"}, ACTOR)
    row = repository.add_reader_insight(conn, {"summary": "例外処理が人に戻る経験", "tags": ["経験"],
                                               "hypothesis_impact": "拡張"}, ACTOR)
    assert row["tags"] == "経験"


def test_structure_summary_flags_small_samples():
    rows = [{"specificity_code": "C3", "imp_pv_proxy": 10.0}, {"specificity_code": "C3", "imp_pv_proxy": 12.0},
            {"specificity_code": "C1", "imp_pv_proxy": 4.0}, {"specificity_code": "C3", "imp_pv_proxy": 8.0}]
    summary = {r["コード"]: r for r in metrics.summarize_by_code(rows, "specificity_code", "imp_pv_proxy")}
    assert summary["C3"]["記事数(n)"] == 3 and summary["C3"]["中央値"] == 10.0
    assert summary["C3"]["判定"].startswith("判定可")
    assert summary["C1"]["判定"].startswith("データ不足")


def test_recommend_prefers_shared_tags(conn):
    make_article(conn, "SRC", theme="AI", topic_tags="AIエージェント,業務設計", funnel_stage="認知")
    make_article(conn, "NEAR", theme="AI", topic_tags="AIエージェント,業務設計", funnel_stage="信頼")
    make_article(conn, "FAR", theme="REG", topic_tags="町工場")
    recs = recommend.recommend(conn, "SRC")
    assert recs[0]["target_article_id"] == "NEAR"
    assert all(r["target_article_id"] != "FAR" for r in recs)
    assert "認知→信頼" in recs[0]["reason"]


def test_allowed_transitions():
    assert repository.allowed_transitions("提案") == ["確認", codes.LINK_REJECTED]
    assert repository.allowed_transitions("表示確認") == []
    assert repository.allowed_transitions(codes.LINK_REJECTED) == ["提案"]


def test_all_pages_render(seeded, db_file, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("LUMI_DB_PATH", str(db_file))
    for path in sorted(glob.glob(str(ROOT / "app" / "views" / "*.py"))) + [str(ROOT / "app" / "main.py")]:
        at = AppTest.from_file(path, default_timeout=60).run()
        assert not at.exception, f"{path}: {[e.value for e in at.exception]}"


def test_ui_link_approval_flow(seeded, db_file, monkeypatch):
    """画面操作で担当者なしの書き込みが止まり、担当者ありで状態が変わること。"""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("LUMI_DB_PATH", str(db_file))
    at = AppTest.from_file(str(ROOT / "app" / "views" / "links.py"), default_timeout=60).run()
    form_button = next(b for b in at.button if b.label == "状態を変更")
    form_button.click().run()
    assert any("担当者名" in w.value for w in at.warning)
    at.sidebar.text_input[0].input("UI担当").run()
    next(b for b in at.button if b.label == "状態を変更").click().run()
    assert any("確認 に変更しました" in s.value for s in at.success)

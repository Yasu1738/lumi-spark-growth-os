"""noteのRSS取り込み（解析と照合）のテスト。URLは試験用の架空のもの。"""

from conftest import ACTOR
from lumi_growth_os import repository, rss, seed

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Lumi Spark</title>
<item><title>LINEとCodexをつないだら、現場の報告が変わった</title>
  <link>https://note.com/lumispark/n/n00000000000b?sub_rt=share_b</link>
  <pubDate>Sun, 16 Aug 2026 22:00:00 +0000</pubDate></item>
<item><title>社長がいなくなったら、会社は何日もつのか</title>
  <link>https://note.com/lumispark/n/n00000000000a</link>
  <pubDate>Mon, 17 Aug 2026 07:00:00 +0900</pubDate></item>
<item><title>試験用の新しい記事</title>
  <link>https://note.com/lumispark/n/n00000000000c</link>
  <pubDate>Fri, 23 Oct 2026 21:30:00 +0000</pubDate></item>
<item><title>マガジン</title><link>https://note.com/lumispark/m/mabc</link></item>
</channel></rss>"""


def test_parse_rss_normalizes_url_and_jst():
    items = rss.parse_rss(FEED)
    assert len(items) == 3  # マガジンURLは記事ではないので除外
    assert items[0]["url"] == "https://note.com/lumispark/n/n00000000000b"
    assert items[0]["published_at"] == "2026-08-17 07:00"  # UTC 22:00 → JST 翌7:00
    assert items[2]["published_at"] == "2026-10-24 06:30"


def test_plan_completes_partial_titles_and_adds_new(seeded):
    planned = {p["title"]: p for p in rss.plan(rss.parse_rss(FEED), repository.list_articles(seeded))}
    line = planned["LINEとCodexをつないだら、現場の報告が変わった"]
    assert line["action"] == "update" and line["id"] == "LS-A004"
    assert line["changes"]["title_status"] == "確認済み" and line["changes"]["url_status"] == "オーナー提示"
    assert line["changes"]["published_at"] == "2026-08-17 07:00"
    assert planned["社長がいなくなったら、会社は何日もつのか"]["id"] == "LS-A007"
    new = planned["試験用の新しい記事"]
    assert new["action"] == "new" and new["id"] == "LS-A010"


def test_apply_local_and_rerun_is_idempotent(seeded):
    items = rss.parse_rss(FEED)
    counts = rss.apply_local(seeded, rss.plan(items, repository.list_articles(seeded)), ACTOR)
    assert counts["update"] == 2 and counts["new"] == 1
    a = repository.get_article(seeded, "LS-A004")
    assert a["title"] == "LINEとCodexをつないだら、現場の報告が変わった" and a["published_at"] == "2026-08-17 07:00"
    again = rss.plan(items, repository.list_articles(seeded))
    assert {p["action"] for p in again} == {"same"}


def test_plan_skips_sample_articles(conn):
    seed.seed_samples(conn)
    planned = rss.plan(rss.parse_rss(FEED), repository.list_articles(conn))
    assert all(p["action"] == "new" for p in planned)

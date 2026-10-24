"""noteの公式RSS（https://note.com/<ユーザー名>/rss）の解析と、記事台帳への反映計画。

このモジュール自体は通信しない。RSSの取得は scripts/rss_sync.py が行う
（オーナーが2026-10-24にRSSの利用を承認。記事ページの読み取りは行わない）。
"""

import re
import xml.etree.ElementTree as ET
from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime

from .validation import validate_url

JST = timezone(timedelta(hours=9))
FEED_URL = "https://note.com/lumispark/rss"


def parse_rss(xml_text: str) -> list:
    """RSSの各記事を {title, url, published_at} にする。URLは共有用パラメータを除いて正規化する。"""
    root = ET.fromstring(xml_text)
    items, seen = [], set()
    for item in root.iter("item"):
        kind, url, _ = validate_url((item.findtext("link") or "").strip())
        if kind != "note_article" or url in seen:
            continue
        seen.add(url)
        published = None
        pub = item.findtext("pubDate")
        if pub:
            try:
                published = parsedate_to_datetime(pub.strip()).astimezone(JST).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError):
                published = None
        items.append({"title": (item.findtext("title") or "").strip(), "url": url, "published_at": published})
    return items


def core_title(title) -> str:
    """「…（以降未確認）」など、途中までのタイトルの末尾表記を除いた部分。"""
    text = re.sub(r"（以降未確認）$", "", str(title or ""))
    return re.sub(r"(…|\.\.\.)$", "", text).strip()


def next_article_ids(existing_ids):
    numbers = [int(i[4:]) for i in existing_ids if re.fullmatch(r"LS-A\d+", i)]
    start = max(numbers, default=0)
    count = 0
    while True:
        count += 1
        yield f"LS-A{start + count:03d}"


def plan(items: list, articles: list) -> list:
    """RSSの記事を既存記事と照合し、更新・追加・変更なしを決める。

    articles: id（または article_id）、title、title_status、url、url_status、published_at、data_kind を持つ辞書。
    照合はURLの一致、次にタイトルの前方一致（途中までのタイトルを補うため）。
    """
    real = [{**a, "id": a.get("id") or a.get("article_id")} for a in articles if a.get("data_kind", "real") != "sample"]
    ids = next_article_ids([a["id"] for a in real])
    result = []
    for it in items:
        match = next((a for a in real if a.get("url") and a["url"] == it["url"]), None)
        if match is None and it["title"]:
            for a in real:
                core = core_title(a["title"])
                if len(core) >= 6 and (it["title"].startswith(core) or core.startswith(it["title"])):
                    match = a
                    break
        if match is None:
            if not it["title"]:
                result.append({**it, "action": "skip", "reason": "タイトルがありません"})
            else:
                result.append({**it, "action": "new", "id": next(ids)})
            continue
        changes = {}
        if it["title"] and it["title"] != match["title"]:
            changes["title"] = it["title"]
        if it["title"] and match.get("title_status") != "確認済み":
            changes["title_status"] = "確認済み"
        if match.get("url") != it["url"] or match.get("url_status") not in ("オーナー提示", "表示確認済み"):
            changes["url"] = it["url"]
            changes["url_status"] = "オーナー提示"
        if it["published_at"] and not match.get("published_at"):
            changes["published_at"] = it["published_at"]
        result.append({**it, "id": match["id"], "action": "update" if changes else "same", "changes": changes,
                       "before": {k: match.get(k) for k in changes}})
    return result


def apply_local(conn, planned: list, actor: str) -> dict:
    """パソコン版（SQLite）へ反映する。"""
    from . import repository

    counts = {"update": 0, "new": 0, "same": 0, "skip": 0}
    for x in planned:
        counts[x["action"]] += 1
        if x["action"] == "update":
            repository.update_article(conn, x["id"], x["changes"], actor, comment="noteのRSSから反映")
        elif x["action"] == "new":
            repository.create_article(conn, {
                "article_id": x["id"], "title": x["title"], "title_status": "確認済み", "url": x["url"],
                "url_status": "オーナー提示", "published_at": x["published_at"], "verification_status": "一部確認",
                "source": f"noteのRSS（{FEED_URL}）", "data_kind": "real",
                "notes": "RSSから登録。テーマ・タグは未設定。",
            }, actor)
    return counts

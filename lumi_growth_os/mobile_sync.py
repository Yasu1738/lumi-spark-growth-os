"""スマホ版（claude.aiのページのデータベース）を毎日自動で更新するための計画づくり。

通信はしない。入力はスマホ版から読み出したJSON、RSSの解析結果、テーマ・タグの推定。
出力はスマホ版へ書き込む内容（ArtifactData の batch 形式）。

オーナー了承（2026-10-24）:
- RSSからタイトル・URL・公開日時を取り込む
- テーマ・タグはタイトルからの推定を入れてよい（推定であることを記録する）
- 関連記事の提案は自動で作る（承認は人が行う）
"""

import json
import re
from pathlib import Path

from . import codes, db, recommend, repository, rss

MIN_SCORE = 2.0
PER_ARTICLE = 2
USABLE = codes.URL_STATUSES_USABLE


def load_dump(dump_dir):
    """ArtifactData の list(out_dir=...) で保存したフォルダを読む。versions.json で版番号を補う。"""
    dump_dir = Path(dump_dir)
    versions = {}
    vfile = dump_dir / "versions.json"
    if vfile.exists():
        versions = json.loads(vfile.read_text(encoding="utf-8"))
    data = {}
    for coll in ("articles", "links", "hubs"):
        docs = {}
        for path in sorted((dump_dir / coll).glob("*.json")) if (dump_dir / coll).exists() else []:
            raw = json.loads(path.read_text(encoding="utf-8"))
            body = raw.get("data", raw)
            doc_id = body.get("id") or path.stem
            docs[doc_id] = {**body, "id": doc_id}
        data[coll] = docs
    data["versions"] = versions
    return data


def _usable(article):
    return bool(article.get("url")) and article.get("url_status") in USABLE and article.get("title_status") == "確認済み" \
        and article.get("data_kind", "real") != "sample"


def build_plan(dump, rss_items, estimates, now, actor):
    """書き込み計画（batch の entries）と、人に伝える要約を返す。"""
    articles = {k: dict(v) for k, v in dump["articles"].items()}
    versions = dump["versions"]
    changes = {}  # article_id -> 更新するフィールド
    created = {}  # article_id -> 新規ドキュメント

    # 1) RSS
    for x in rss.plan(rss_items, list(articles.values())):
        if x["action"] == "update":
            changes.setdefault(x["id"], {}).update(x["changes"])
            articles[x["id"]].update(x["changes"])
        elif x["action"] == "new":
            doc = {"id": x["id"], "title": x["title"], "title_status": "確認済み", "url": x["url"],
                   "url_status": "オーナー提示", "published_at": x["published_at"], "content_reviewed": False,
                   "data_kind": "real", "verification_status": "一部確認", "theme": None, "topic_tags": None,
                   "source": f"noteのRSS（{rss.FEED_URL}）", "notes": "RSSから自動登録。", "created_at": now, "updated_at": now}
            created[x["id"]] = doc
            articles[x["id"]] = doc

    # 2) テーマ・タグの推定（空のものだけ。人が入れた値は上書きしない）
    tagged = []
    for article_id, est in (estimates or {}).items():
        a = articles.get(article_id)
        if not a:
            continue
        fields = {}
        if not a.get("theme") and est.get("theme") in codes.THEMES:
            fields["theme"] = est["theme"]
        if not a.get("topic_tags") and est.get("topic_tags"):
            fields["topic_tags"] = est["topic_tags"]
        if fields:
            fields["tags_estimated"] = f"Claudeがタイトルから推定（{now[:10]}）"
            a.update(fields)
            (created[article_id] if article_id in created else changes.setdefault(article_id, {})).update(fields)
            tagged.append(article_id)

    # 3) 関連記事の提案（両端のURL・タイトルがそろっていて、まだ提案のない記事から）
    conn = db.connect(":memory:")
    db.init_db(conn)
    for a in articles.values():
        repository.create_article(conn, {
            "article_id": a["id"], "title": a.get("title") or a["id"], "title_status": a.get("title_status") or "未確認",
            "url": a.get("url"), "url_status": a.get("url_status") or "未確認",
            "theme": a.get("theme") if a.get("theme") in codes.THEMES else None, "topic_tags": a.get("topic_tags"),
            "funnel_stage": a.get("funnel_stage") if a.get("funnel_stage") in codes.FUNNEL_STAGES else None,
            "primary_purpose": a.get("primary_purpose") if a.get("primary_purpose") in codes.PURPOSES else None,
            "data_kind": a.get("data_kind", "real"),
        }, actor, strict_url=False)
    for h in dump["hubs"].values():
        conn.execute("INSERT INTO hubs(hub_id, name, hub_article_id, related_topics, status, sort_order, created_at, updated_at)"
                     " VALUES (?,?,?,?,?,?,?,?)", (h["id"], h.get("name") or h["id"], h.get("hub_article_id"),
                                                   h.get("related_topics"), h.get("status") or "候補", h.get("sort_order") or 0, now, now))
    for l in dump["links"].values():
        conn.execute("INSERT OR IGNORE INTO link_proposals(link_id, source_article_id, target_article_id, proposed_by, status,"
                     " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                     (l["id"], l["source"], l["target"], l.get("proposed_by") or "?", l.get("status") or "提案", now, now))
    numbers = [int(k[4:]) for k in dump["links"] if re.fullmatch(r"LNK-\d+", k)]
    next_no = max(numbers, default=0)
    has_outgoing = {l["source"] for l in dump["links"].values()}
    new_links = []
    for a in sorted(articles.values(), key=lambda x: x["id"]):
        if a["id"] in has_outgoing or not _usable(a):
            continue
        picked = 0
        for rec in recommend.recommend(conn, a["id"], limit=10):
            if picked >= PER_ARTICLE or rec["score"] < MIN_SCORE or not _usable(articles[rec["target_article_id"]]):
                continue
            next_no += 1
            new_links.append({
                "id": f"LNK-{next_no:04d}", "source": a["id"], "target": rec["target_article_id"], "hub_id": rec.get("hub_id"),
                "reason": rec["reason"], "reader_value": rec["reader_value"], "anchor_text": rec["anchor_text"],
                "insert_position": rec["insert_position"],
                "evidence": f"{recommend.ENGINE_NAME}（自動）: score={rec['score']}（タグはタイトルからの推定を含む）",
                "score": rec["score"], "proposed_by": recommend.ENGINE_NAME + "（毎日の自動提案）", "status": "提案",
                "relevance_status": "未確認", "history": [], "created_at": now, "updated_at": now,
            })
            picked += 1
    conn.close()

    # 4) 書き込み内容
    writes = []
    for article_id, doc in created.items():
        writes.append({"op": "set", "collection": "articles", "doc_id": article_id, "data": doc})
    for article_id, fields in changes.items():
        entry = {"op": "update", "collection": "articles", "doc_id": article_id, "data": {**fields, "updated_at": now}}
        if versions.get(article_id):
            entry["if_version"] = versions[article_id]
        writes.append(entry)
    for link in new_links:
        writes.append({"op": "set", "collection": "links", "doc_id": link["id"], "data": link})
    stamp = now.replace(" ", "T").replace(":", "")
    writes.append({"op": "set", "collection": "audit", "doc_id": f"sync-{stamp}", "data": {
        "at": now, "actor": actor, "action": f"毎日の自動更新：新規{len(created)}件・更新{len(changes)}件・推定タグ{len(tagged)}件・提案{len(new_links)}件",
        "entity": "sync", "entity_id": stamp, "before": None,
        "after": {"created": list(created), "updated": list(changes), "tagged": tagged, "links": [l["id"] for l in new_links]},
        "approver": None, "comment": None}})
    summary = {"created": [(k, v["title"]) for k, v in created.items()], "updated": list(changes),
               "tagged": tagged, "links": [(l["id"], articles[l["source"]]["title"], articles[l["target"]]["title"]) for l in new_links],
               "needs_estimate": [a["id"] for a in articles.values() if a.get("data_kind", "real") != "sample"
                                  and (not a.get("theme") or not a.get("topic_tags"))]}
    return writes, summary


def write_batches(writes, out_dir, size=50):
    """batch は1回50件まで。data をファイルにして file_path 形式で出力する。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, w in enumerate(writes):
        path = out_dir / f"{i:03d}_{w['collection']}_{w['doc_id']}.json"
        path.write_text(json.dumps(w["data"], ensure_ascii=False), encoding="utf-8")
        entry = {k: v for k, v in w.items() if k != "data"}
        entry["file_path"] = str(path)
        entries.append(entry)
    files = []
    for n in range(0, len(entries), size):
        f = out_dir / f"batch_{n // size + 1}.json"
        f.write_text(json.dumps(entries[n:n + size], ensure_ascii=False), encoding="utf-8")
        files.append(f)
    return files

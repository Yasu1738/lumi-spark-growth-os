"""データ操作層。画面（Streamlit）から独立しており、すべての書き込みを監査ログに残す。"""

import json
from datetime import datetime

from . import codes
from .validation import (
    ValidationError,
    check_article_id,
    check_code,
    check_title_structure,
    clean_text,
    has_time,
    parse_count,
    parse_datetime,
    to_datetime,
    validate_url,
)

ARTICLE_TEXT_FIELDS = [
    "title", "target_reader", "core_claim", "revenue_path", "topic_tags",
    "pre_hypothesis", "source", "notes", "secondary_purpose",
]
ARTICLE_FIELDS = [
    "article_id", "title", "title_status", "url", "url_status", "published_at",
    "theme", "primary_purpose", "secondary_purpose", "target_reader", "core_claim",
    "title_structure", "human_code", "perspective_code", "specificity_code",
    "emotion_temp", "funnel_stage", "revenue_path", "topic_tags", "content_reviewed",
    "pre_hypothesis", "hypothesis_verdict", "source", "verification_status",
    "data_kind", "notes", "legacy_json",
]
METRIC_FIELDS = [
    "imp", "pv", "likes", "comments", "meaningful_comments",
    "follows", "consultations", "membership_joins",
]
METRIC_LABELS = {
    "imp": "IMP", "pv": "PV", "likes": "スキ", "comments": "コメント",
    "meaningful_comments": "有意味コメント", "follows": "フォロー増",
    "consultations": "相談件数", "membership_joins": "メンバーシップ参加数",
}


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _commit(conn):
    """インポートなど外側のトランザクション管理中はコミットしない。"""
    if getattr(conn, "defer_commit", 0):
        return
    conn.commit()


def _require_actor(actor):
    actor = clean_text(actor)
    if actor is None:
        raise ValidationError("担当者名を入力してください（操作履歴に記録します）")
    return actor


def _row_dict(row):
    return dict(row) if row is not None else None


def log_action(conn, actor, action, entity_type, entity_id, before=None, after=None,
               approver=None, comment=None):
    conn.execute(
        "INSERT INTO audit_log(at, actor, action, entity_type, entity_id, before_json, after_json, approver, comment)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (
            now_iso(), actor, action, entity_type, entity_id,
            json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
            json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
            clean_text(approver), clean_text(comment),
        ),
    )


# ---------------------------------------------------------------- 記事

def _normalize_article(data: dict, strict_url: bool = True) -> dict:
    out = {}
    for key in ARTICLE_TEXT_FIELDS:
        if key in data:
            out[key] = clean_text(data[key])
    if "title" in data and out.get("title") is None:
        raise ValidationError("記事タイトルは必須です（未確認の場合も仮タイトルを入れてください）")
    if "published_at" in data:
        out["published_at"] = parse_datetime(data["published_at"], "公開日時")
    if "theme" in data:
        out["theme"] = check_code(data["theme"], list(codes.THEMES), "テーマ")
    if "primary_purpose" in data:
        out["primary_purpose"] = check_code(data["primary_purpose"], codes.PURPOSES, "主目的")
    if "title_structure" in data:
        out["title_structure"] = check_title_structure(data["title_structure"])
    if "human_code" in data:
        out["human_code"] = check_code(data["human_code"], list(codes.HUMAN_CODES), "Humanコード")
    if "perspective_code" in data:
        out["perspective_code"] = check_code(data["perspective_code"], list(codes.PERSPECTIVE_CODES), "Perspective Shiftコード")
    if "specificity_code" in data:
        out["specificity_code"] = check_code(data["specificity_code"], list(codes.SPECIFICITY_CODES), "Specificityコード")
    if "emotion_temp" in data:
        out["emotion_temp"] = check_code(data["emotion_temp"], codes.EMOTION_TEMPS, "感情温度")
    if "funnel_stage" in data:
        out["funnel_stage"] = check_code(data["funnel_stage"], codes.FUNNEL_STAGES, "収益導線の段階")
    if "hypothesis_verdict" in data:
        out["hypothesis_verdict"] = check_code(data["hypothesis_verdict"], codes.HYPOTHESIS_VERDICTS, "仮説判定")
    if "title_status" in data:
        out["title_status"] = check_code(data["title_status"], codes.TITLE_STATUSES, "タイトル確認状態") or "未確認"
    if "verification_status" in data:
        out["verification_status"] = check_code(
            data["verification_status"], codes.VERIFICATION_STATUSES, "確認状態") or "未確認"
    if "data_kind" in data:
        out["data_kind"] = check_code(data["data_kind"], list(codes.DATA_KINDS), "データ区分") or "real"
    if "content_reviewed" in data:
        out["content_reviewed"] = 1 if data["content_reviewed"] in (True, 1, "1", "true", "True", "はい") else 0
    if "legacy_json" in data:
        out["legacy_json"] = data["legacy_json"]

    if "url" in data or "url_status" in data:
        kind, normalized, message = validate_url(data.get("url"))
        requested = check_code(data.get("url_status"), codes.URL_STATUSES, "URL確認状態")
        if kind == "empty":
            if requested in codes.URL_STATUSES_USABLE:
                raise ValidationError("URLが空欄のため、URL確認状態を「未確認」以外にできません")
            out["url"], out["url_status"] = None, "未確認"
        elif kind == "invalid":
            if strict_url:
                raise ValidationError(f"不正なURL: {message}")
            out["url"], out["url_status"] = clean_text(data.get("url")), "不正"
        else:
            if requested == "不正":
                requested = None
            out["url"], out["url_status"] = normalized, requested or "未確認"
    return out


def create_article(conn, data: dict, actor: str, strict_url: bool = True) -> dict:
    actor = _require_actor(actor)
    article_id = check_article_id(data.get("article_id"))
    if get_article(conn, article_id) is not None:
        raise ValidationError(f"記事ID {article_id} は既に存在します")
    values = _normalize_article({**{"title": None}, **data}, strict_url=strict_url)
    values["article_id"] = article_id
    values.setdefault("url_status", "未確認")
    ts = now_iso()
    values["created_at"] = values["updated_at"] = ts
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO articles({columns}) VALUES ({placeholders})", list(values.values()))
    log_action(conn, actor, "記事登録", "article", article_id, after=values)
    _commit(conn)
    return get_article(conn, article_id)


def update_article(conn, article_id: str, changes: dict, actor: str, comment=None) -> dict:
    actor = _require_actor(actor)
    before = get_article(conn, article_id)
    if before is None:
        raise ValidationError(f"記事ID {article_id} が見つかりません")
    changes = {k: v for k, v in changes.items() if k in ARTICLE_FIELDS and k != "article_id"}
    if "url" in changes and "url_status" not in changes:
        changes["url_status"] = before["url_status"] if before["url"] == clean_text(changes["url"]) else "未確認"
    if "url_status" in changes and "url" not in changes:
        changes["url"] = before["url"]
    values = _normalize_article(changes)
    diff = {k: v for k, v in values.items() if before.get(k) != v}
    if not diff:
        return before
    diff["updated_at"] = now_iso()
    assignments = ", ".join(f"{k} = ?" for k in diff)
    conn.execute(f"UPDATE articles SET {assignments} WHERE article_id = ?", [*diff.values(), article_id])
    log_action(conn, actor, "記事更新", "article", article_id,
               before={k: before.get(k) for k in diff}, after=diff, comment=comment)
    _commit(conn)
    return get_article(conn, article_id)


def get_article(conn, article_id):
    return _row_dict(conn.execute("SELECT * FROM articles WHERE article_id = ?", (article_id,)).fetchone())


def list_articles(conn, data_kind=None):
    if data_kind:
        rows = conn.execute("SELECT * FROM articles WHERE data_kind = ? ORDER BY article_id", (data_kind,))
    else:
        rows = conn.execute("SELECT * FROM articles ORDER BY data_kind, article_id")
    return [dict(r) for r in rows.fetchall()]


def hub_ids_for_article(conn, article_id):
    rows = conn.execute("SELECT hub_id FROM hubs WHERE hub_article_id = ?", (article_id,)).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------- ハブ

def create_hub(conn, data: dict, actor: str) -> dict:
    actor = _require_actor(actor)
    hub_id = check_article_id(data.get("hub_id"))
    name = clean_text(data.get("name"))
    if name is None:
        raise ValidationError("ハブ名は必須です")
    hub_article_id = clean_text(data.get("hub_article_id"))
    if hub_article_id and get_article(conn, hub_article_id) is None:
        raise ValidationError(f"ハブ記事 {hub_article_id} が記事台帳に存在しません")
    ts = now_iso()
    values = {
        "hub_id": hub_id, "name": name, "description": clean_text(data.get("description")),
        "hub_article_id": hub_article_id, "related_topics": clean_text(data.get("related_topics")),
        "status": clean_text(data.get("status")) or "候補", "sort_order": int(data.get("sort_order") or 0),
        "notes": clean_text(data.get("notes")), "created_at": ts, "updated_at": ts,
    }
    conn.execute(
        f"INSERT INTO hubs({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
        list(values.values()),
    )
    log_action(conn, actor, "ハブ登録", "hub", hub_id, after=values)
    _commit(conn)
    return get_hub(conn, hub_id)


def update_hub(conn, hub_id: str, changes: dict, actor: str) -> dict:
    actor = _require_actor(actor)
    before = get_hub(conn, hub_id)
    if before is None:
        raise ValidationError(f"ハブ {hub_id} が見つかりません")
    allowed = {"name", "description", "hub_article_id", "related_topics", "status", "sort_order", "notes"}
    values = {}
    for key, value in changes.items():
        if key not in allowed:
            continue
        values[key] = int(value or 0) if key == "sort_order" else clean_text(value)
    if "name" in values and values["name"] is None:
        raise ValidationError("ハブ名は必須です")
    if values.get("hub_article_id") and get_article(conn, values["hub_article_id"]) is None:
        raise ValidationError(f"ハブ記事 {values['hub_article_id']} が記事台帳に存在しません")
    diff = {k: v for k, v in values.items() if before.get(k) != v}
    if not diff:
        return before
    diff["updated_at"] = now_iso()
    conn.execute(
        f"UPDATE hubs SET {', '.join(f'{k} = ?' for k in diff)} WHERE hub_id = ?",
        [*diff.values(), hub_id],
    )
    log_action(conn, actor, "ハブ更新", "hub", hub_id, before={k: before.get(k) for k in diff}, after=diff)
    _commit(conn)
    return get_hub(conn, hub_id)


def get_hub(conn, hub_id):
    return _row_dict(conn.execute("SELECT * FROM hubs WHERE hub_id = ?", (hub_id,)).fetchone())


def list_hubs(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM hubs ORDER BY sort_order, hub_id").fetchall()]


def list_path_steps(conn, hub_id):
    rows = conn.execute(
        "SELECT * FROM hub_path_steps WHERE hub_id = ? ORDER BY step_order, step_id", (hub_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def replace_path_steps(conn, hub_id: str, steps: list, actor: str):
    """ハブの導線ステップを一覧の内容で置き換える（一覧編集用）。"""
    actor = _require_actor(actor)
    if get_hub(conn, hub_id) is None:
        raise ValidationError(f"ハブ {hub_id} が見つかりません")
    cleaned = []
    for index, step in enumerate(steps, start=1):
        label = clean_text(step.get("label"))
        if label is None:
            continue
        article_id = clean_text(step.get("article_id"))
        if article_id and get_article(conn, article_id) is None:
            raise ValidationError(f"ステップ「{label}」の記事ID {article_id} が存在しません")
        cleaned.append({
            "step_order": index, "label": label,
            "funnel_stage": check_code(step.get("funnel_stage"), codes.FUNNEL_STAGES, "収益導線の段階"),
            "article_id": article_id, "notes": clean_text(step.get("notes")),
        })
    before = list_path_steps(conn, hub_id)
    conn.execute("DELETE FROM hub_path_steps WHERE hub_id = ?", (hub_id,))
    for step in cleaned:
        conn.execute(
            "INSERT INTO hub_path_steps(hub_id, step_order, label, funnel_stage, article_id, notes)"
            " VALUES (?,?,?,?,?,?)",
            (hub_id, step["step_order"], step["label"], step["funnel_stage"], step["article_id"], step["notes"]),
        )
    log_action(conn, actor, "ハブ導線更新", "hub", hub_id, before=before, after=cleaned)
    _commit(conn)
    return list_path_steps(conn, hub_id)


# ---------------------------------------------------------------- リンク提案

def _next_link_id(conn):
    row = conn.execute(
        "SELECT link_id FROM link_proposals WHERE link_id LIKE 'LNK-%' ORDER BY link_id DESC LIMIT 1"
    ).fetchone()
    number = int(row[0].split("-")[1]) + 1 if row else 1
    return f"LNK-{number:04d}"


def check_link_candidate(conn, source_id, target_id):
    """自己リンク・重複リンク・記事不在・不正URLを検出する。問題のリストを返す。"""
    issues = []
    source_id, target_id = clean_text(source_id), clean_text(target_id)
    if not source_id or not target_id:
        issues.append("リンク元・リンク先の記事IDは必須です")
        return issues
    if source_id == target_id:
        issues.append(f"自己リンク: {source_id} から自分自身へのリンクです")
    source, target = get_article(conn, source_id), get_article(conn, target_id)
    if source is None:
        issues.append(f"リンク元 {source_id} が記事台帳に存在しません")
    if target is None:
        issues.append(f"リンク先 {target_id} が記事台帳に存在しません")
    dup = conn.execute(
        "SELECT link_id, status FROM link_proposals WHERE source_article_id = ? AND target_article_id = ?",
        (source_id, target_id),
    ).fetchone()
    if dup:
        issues.append(f"重複リンク: {source_id}→{target_id} は既に {dup['link_id']}（{dup['status']}）として登録済みです")
    for role, article in (("リンク元", source), ("リンク先", target)):
        if article and article["url_status"] == "不正":
            issues.append(f"不正URL: {role} {article['article_id']} のURL「{article['url']}」が不正です")
    return issues


def create_link(conn, source_id, target_id, actor, *, reason=None, reader_value=None,
                anchor_text=None, insert_position=None, evidence=None, hub_id=None,
                score=None, proposed_by=None) -> dict:
    actor = _require_actor(actor)
    blocking = [i for i in check_link_candidate(conn, source_id, target_id) if not i.startswith("不正URL")]
    if blocking:
        raise ValidationError(" / ".join(blocking))
    source, target = get_article(conn, source_id), get_article(conn, target_id)
    if hub_id and get_hub(conn, hub_id) is None:
        raise ValidationError(f"ハブ {hub_id} が見つかりません")
    data_kind = "sample" if "sample" in (source["data_kind"], target["data_kind"]) else "real"
    ts = now_iso()
    values = {
        "link_id": _next_link_id(conn), "source_article_id": source_id, "target_article_id": target_id,
        "hub_id": clean_text(hub_id), "reason": clean_text(reason), "reader_value": clean_text(reader_value),
        "anchor_text": clean_text(anchor_text), "insert_position": clean_text(insert_position),
        "evidence": clean_text(evidence), "score": score, "proposed_by": clean_text(proposed_by) or actor,
        "status": "提案", "relevance_status": "未確認", "data_kind": data_kind,
        "created_at": ts, "updated_at": ts,
    }
    conn.execute(
        f"INSERT INTO link_proposals({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
        list(values.values()),
    )
    log_action(conn, actor, "リンク提案登録", "link", values["link_id"], after=values)
    _commit(conn)
    return get_link(conn, values["link_id"])


def get_link(conn, link_id):
    return _row_dict(conn.execute("SELECT * FROM link_proposals WHERE link_id = ?", (link_id,)).fetchone())


def list_links(conn, source_id=None, hub_id=None):
    sql = (
        "SELECT l.*, s.title AS source_title, t.title AS target_title, t.url AS target_url,"
        " t.url_status AS target_url_status, s.url_status AS source_url_status"
        " FROM link_proposals l JOIN articles s ON s.article_id = l.source_article_id"
        " JOIN articles t ON t.article_id = l.target_article_id"
    )
    clauses, params = [], []
    if source_id:
        clauses.append("l.source_article_id = ?")
        params.append(source_id)
    if hub_id:
        clauses.append("l.hub_id = ?")
        params.append(hub_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY l.link_id"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_link_content(conn, link_id, changes: dict, actor):
    """提案内容（理由・リンク文など）の修正。状態は変えない。"""
    actor = _require_actor(actor)
    before = get_link(conn, link_id)
    if before is None:
        raise ValidationError(f"リンク {link_id} が見つかりません")
    allowed = {"reason", "reader_value", "anchor_text", "insert_position", "evidence", "hub_id"}
    diff = {k: clean_text(v) for k, v in changes.items() if k in allowed and before.get(k) != clean_text(v)}
    if not diff:
        return before
    diff["updated_at"] = now_iso()
    conn.execute(
        f"UPDATE link_proposals SET {', '.join(f'{k} = ?' for k in diff)} WHERE link_id = ?",
        [*diff.values(), link_id],
    )
    log_action(conn, actor, "リンク提案修正", "link", link_id, before={k: before.get(k) for k in diff}, after=diff)
    _commit(conn)
    return get_link(conn, link_id)


def link_blockers(conn, link) -> list:
    """本番反映（note上での実リンク設置）を妨げる要因。状態（承認前）は含めない。"""
    reasons = []
    source = get_article(conn, link["source_article_id"])
    target = get_article(conn, link["target_article_id"])
    for role, article in (("リンク元", source), ("リンク先", target)):
        if article["data_kind"] == "sample":
            reasons.append(f"{role}がサンプル記事")
        if not article["url"] or article["url_status"] not in codes.URL_STATUSES_USABLE:
            reasons.append(f"{role}のURLが未確認（{article['url_status']}）")
        if not article["content_reviewed"]:
            reasons.append(f"{role}の本文内容が未確認")
        if article["title_status"] != "確認済み":
            reasons.append(f"{role}のタイトルが未照合（{article['title_status']}）")
    return reasons


def link_readiness(conn, link) -> dict:
    blockers = link_blockers(conn, link)
    approved = link["status"] in ("承認", "note反映", "表示確認")
    if link["status"] == codes.LINK_REJECTED:
        label = "却下"
    elif blockers:
        label = "仮案（本番反映不可）"
    elif not approved:
        label = "承認待ち"
    elif link["status"] == "承認":
        label = "承認済み・note反映待ち（人間が操作）"
    else:
        label = link["status"] + "済み"
    return {"label": label, "blockers": blockers, "production_ready": approved and not blockers}


def allowed_transitions(status):
    if status == codes.LINK_REJECTED:
        return ["提案"]
    if status not in codes.LINK_STATUSES:
        return []
    index = codes.LINK_STATUSES.index(status)
    nexts = codes.LINK_STATUSES[index + 1:index + 2]
    if status != "表示確認":
        nexts.append(codes.LINK_REJECTED)
    return nexts


def transition_link(conn, link_id, new_status, actor, approver=None, comment=None) -> dict:
    actor = _require_actor(actor)
    link = get_link(conn, link_id)
    if link is None:
        raise ValidationError(f"リンク {link_id} が見つかりません")
    if new_status not in allowed_transitions(link["status"]):
        raise ValidationError(
            f"「{link['status']}」から「{new_status}」へは変更できません"
            f"（可能: {', '.join(allowed_transitions(link['status'])) or 'なし'}）"
        )
    blockers = link_blockers(conn, link)
    updates = {"status": new_status}
    if new_status == "確認":
        source = get_article(conn, link["source_article_id"])
        target = get_article(conn, link["target_article_id"])
        both_reviewed = source["content_reviewed"] and target["content_reviewed"]
        updates["relevance_status"] = "確認済み" if both_reviewed else "未確認（本文未確認の記事を含む）"
    if new_status == "承認":
        if clean_text(approver) is None:
            raise ValidationError("承認には承認者名が必要です")
        if blockers:
            raise ValidationError("承認できません（仮案のため）: " + " / ".join(blockers))
    if new_status in ("note反映", "表示確認") and blockers:
        raise ValidationError("本番反映の記録はできません: " + " / ".join(blockers))
    if new_status == "提案":
        updates["relevance_status"] = "未確認"
    updates["updated_at"] = now_iso()
    conn.execute(
        f"UPDATE link_proposals SET {', '.join(f'{k} = ?' for k in updates)} WHERE link_id = ?",
        [*updates.values(), link_id],
    )
    log_action(conn, actor, f"リンク状態変更: {link['status']}→{new_status}", "link", link_id,
               before={"status": link["status"], "relevance_status": link["relevance_status"]},
               after=updates, approver=approver, comment=comment)
    _commit(conn)
    return get_link(conn, link_id)


# ---------------------------------------------------------------- 実績

def add_metric(conn, article_id, measured_at, window_type, values: dict, source, actor,
               condition_note=None) -> dict:
    actor = _require_actor(actor)
    article = get_article(conn, article_id)
    if article is None:
        raise ValidationError(f"記事ID {article_id} が見つかりません")
    measured = parse_datetime(measured_at, "計測日時")
    if measured is None:
        raise ValidationError("計測日時は必須です")
    if window_type not in codes.WINDOW_TYPES:
        raise ValidationError(f"計測区分は {', '.join(codes.WINDOW_TYPES)} のいずれかです")
    source = clean_text(source)
    if source is None:
        raise ValidationError("情報の出典（どの画面・資料から取得したか）は必須です")
    numbers = {field: parse_count(values.get(field), codes_label(field)) for field in METRIC_FIELDS}
    if all(v is None for v in numbers.values()):
        raise ValidationError("少なくとも1つの指標を入力してください")

    published = article["published_at"]
    hours = None
    if published and has_time(published) and has_time(measured):
        hours = round((to_datetime(measured) - to_datetime(published)).total_seconds() / 3600, 2)
        if hours < 0:
            raise ValidationError("計測日時が公開日時より前です")
    elif published and to_datetime(measured).date() < to_datetime(published).date():
        raise ValidationError("計測日時が公開日時より前です")
    if window_type in codes.WINDOW_TOLERANCE_HOURS:
        low, high = codes.WINDOW_TOLERANCE_HOURS[window_type]
        if hours is None:
            raise ValidationError(
                f"公開日時・計測日時の時刻が揃っていないため {window_type} 値として検証できません。"
                "累積値（cumulative）として登録してください"
            )
        if not (low <= hours <= high):
            raise ValidationError(
                f"公開後 {hours} 時間の値は {window_type} 値として登録できません（許容 {low}〜{high} 時間）。"
                "後から取得した累積値は cumulative として登録してください"
            )
    ts = now_iso()
    row = {
        "article_id": article_id, "measured_at": measured, "window_type": window_type,
        "hours_since_publish": hours, **numbers, "source": source,
        "condition_note": clean_text(condition_note), "data_kind": article["data_kind"], "created_at": ts,
    }
    cur = conn.execute(
        f"INSERT INTO article_metrics({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    log_action(conn, actor, "実績登録", "metric", str(cur.lastrowid), after=row)
    _commit(conn)
    return _row_dict(conn.execute("SELECT * FROM article_metrics WHERE metric_id = ?", (cur.lastrowid,)).fetchone())


def codes_label(field):
    return METRIC_LABELS.get(field, field)


def list_metrics(conn, article_id=None, window_type=None):
    sql = "SELECT m.*, a.title, a.published_at FROM article_metrics m JOIN articles a USING(article_id)"
    clauses, params = [], []
    if article_id:
        clauses.append("m.article_id = ?")
        params.append(article_id)
    if window_type:
        clauses.append("m.window_type = ?")
        params.append(window_type)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.article_id, m.measured_at"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def add_account_snapshot(conn, data: dict, actor) -> dict:
    actor = _require_actor(actor)
    measured = parse_datetime(data.get("measured_at"), "集計日時")
    if measured is None:
        raise ValidationError("集計日時は必須です")
    source = clean_text(data.get("source"))
    if source is None:
        raise ValidationError("情報の出典は必須です")
    row = {
        "measured_at": measured,
        "period_start": parse_datetime(data.get("period_start"), "対象期間開始"),
        "period_end": parse_datetime(data.get("period_end"), "対象期間終了"),
        **{k: parse_count(data.get(k), k) for k in ("imp", "pv", "likes", "comments", "follows", "posts")},
        "period_note": clean_text(data.get("period_note")), "source": source,
        "notes": clean_text(data.get("notes")),
        "data_kind": check_code(data.get("data_kind"), list(codes.DATA_KINDS), "データ区分") or "real",
        "created_at": now_iso(),
    }
    cur = conn.execute(
        f"INSERT INTO account_snapshots({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    log_action(conn, actor, "アカウント実績登録", "account_snapshot", str(cur.lastrowid), after=row)
    _commit(conn)
    return row


def list_account_snapshots(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM account_snapshots ORDER BY measured_at").fetchall()]


def list_rankings(conn):
    snaps = [dict(r) for r in conn.execute("SELECT * FROM ranking_snapshots ORDER BY captured_at").fetchall()]
    for snap in snaps:
        snap["entries"] = [dict(r) for r in conn.execute(
            "SELECT e.*, a.title AS article_title FROM ranking_entries e LEFT JOIN articles a USING(article_id)"
            " WHERE snapshot_id = ? ORDER BY position", (snap["snapshot_id"],)).fetchall()]
    return snaps


# ---------------------------------------------------------------- 収益導線・読者理解

def add_funnel_observation(conn, data: dict, actor) -> dict:
    """確認できた数値のみ登録する。出典必須、推定値は登録不可。"""
    actor = _require_actor(actor)
    stage = check_code(data.get("stage"), codes.FUNNEL_STAGES, "段階")
    if stage is None:
        raise ValidationError("段階は必須です")
    value = parse_count(data.get("value"), "値")
    if value is None:
        raise ValidationError("値は必須です（確認できない場合は登録しないでください）")
    source = clean_text(data.get("source"))
    if source is None:
        raise ValidationError("出典は必須です（確認できる数値のみ登録します）")
    observed = parse_datetime(data.get("observed_at"), "確認日時")
    if observed is None:
        raise ValidationError("確認日時は必須です")
    row = {
        "observed_at": observed, "stage": stage, "value": value,
        "unit": clean_text(data.get("unit")) or "件", "source": source,
        "data_kind": check_code(data.get("data_kind"), list(codes.DATA_KINDS), "データ区分") or "real",
        "notes": clean_text(data.get("notes")), "created_at": now_iso(),
    }
    cur = conn.execute(
        f"INSERT INTO funnel_observations({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    log_action(conn, actor, "導線実績登録", "funnel", str(cur.lastrowid), after=row)
    _commit(conn)
    return row


def list_funnel_observations(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM funnel_observations ORDER BY observed_at").fetchall()]


def add_reader_insight(conn, data: dict, actor) -> dict:
    """読者コメントから得た課題・関心の要約。個人名・アカウント名は記録しない。"""
    actor = _require_actor(actor)
    summary = clean_text(data.get("summary"))
    if summary is None:
        raise ValidationError("要約は必須です")
    if "@" in summary:
        raise ValidationError("個人を特定できる情報（@アカウント名など）は記録しないでください")
    article_id = clean_text(data.get("article_id"))
    if article_id and get_article(conn, article_id) is None:
        raise ValidationError(f"記事ID {article_id} が見つかりません")
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in tags.split(",") if t]
    for tag in tags:
        if tag not in codes.COMMENT_TAGS:
            raise ValidationError(f"コメントタグ「{tag}」は定義外です")
    row = {
        "article_id": article_id,
        "observed_at": parse_datetime(data.get("observed_at"), "確認日時") or now_iso()[:16],
        "tags": ",".join(tags) or None, "summary": summary,
        "hypothesis_impact": check_code(data.get("hypothesis_impact"), codes.HYPOTHESIS_IMPACTS, "元仮説への影響"),
        "derived_candidate": clean_text(data.get("derived_candidate")),
        "data_kind": check_code(data.get("data_kind"), list(codes.DATA_KINDS), "データ区分") or "real",
        "created_at": now_iso(),
    }
    cur = conn.execute(
        f"INSERT INTO reader_insights({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    log_action(conn, actor, "読者理解の記録", "insight", str(cur.lastrowid), after=row)
    _commit(conn)
    return row


def list_reader_insights(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM reader_insights ORDER BY observed_at DESC").fetchall()]


def list_audit(conn, limit=500, entity_type=None, entity_id=None):
    sql, params = "SELECT * FROM audit_log", []
    clauses = []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY log_id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def pending_human_items(conn) -> dict:
    """人間の確認・承認が必要な事項の一覧。"""
    real = list_articles(conn, "real")
    return {
        "URL未確認の記事": [a for a in real if a["url_status"] not in codes.URL_STATUSES_USABLE],
        "タイトル未照合の記事": [a for a in real if a["title_status"] != "確認済み"],
        "本文内容が未確認の記事": [a for a in real if not a["content_reviewed"]],
        "構造コード未設定の記事": [
            a for a in real
            if not all([a["title_structure"], a["human_code"], a["perspective_code"], a["specificity_code"]])
        ],
        "承認待ちのリンク提案": [
            l for l in list_links(conn) if l["data_kind"] == "real" and l["status"] in ("提案", "確認")
        ],
    }

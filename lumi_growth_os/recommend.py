"""タグとルールに基づく関連記事推薦（LLM API不要）。

推薦結果は「提案」にすぎない。本文を確認していない記事の関連性は
「ルール推定」と表示し、確認済みとは表示しない。
"""

from . import codes, repository
from .validation import split_tags

ENGINE_NAME = "rule-engine v1"

WEIGHTS = {"theme": 3.0, "tag": 6.0, "hub_topic": 2.0, "funnel_next": 1.5, "funnel_same": 0.5}

READER_VALUE_BY_PURPOSE = {
    "認知": "テーマの全体像をつかみ、自分に関係する話かを判断できる",
    "共感・信頼": "自分の状況に近い場面を通じて、言葉にできなかった違和感を整理できる",
    "経営・組織": "判断と責任の置き方を、組織の構造から考え直せる",
    "専門・実務": "現場で試せる具体的な手順や判断基準が得られる",
    "地域・活動": "地域や業界の動きを、自分の仕事との関係で捉え直せる",
    "相談・仕事接続": "自社の課題を整理し、相談すべきかを判断できる",
    "読者定着・世界観": "Lumi Sparkが考え続けている問いの全体像が見える",
}

ANCHOR_BY_THEME = {
    "AI": "AIに仕事を任せることを、もう一歩具体的に考えたい方へ",
    "ORG": "組織と責任の関係を、別の角度から考えたい方へ",
    "REG": "地域の産業のこれからを、もう少し考えてみたい方へ",
    "MKT": "お客さまとの関係づくりを考えたい方へ",
    "FIN": "経営の数字と判断のつながりを考えたい方へ",
    "EVENT": "この出来事の背景をもう少し知りたい方へ",
    "META": "Lumi Sparkの取り組みをもう少し知りたい方へ",
}


def anchor_text(source_terms, candidate):
    """推奨リンク文。共通タグがあればそれを主題にし、なければテーマ別の定型文を使う。"""
    cand_tags = split_tags(candidate.get("topic_tags"))
    shared = [t for t in cand_tags if t in source_terms]
    if shared:
        return f"「{shared[0]}」を、もう一歩考えたい方へ"
    return ANCHOR_BY_THEME.get(candidate.get("theme"), "あわせて読みたい記事")


def _article_terms(article, hubs):
    terms = set(split_tags(article.get("topic_tags")))
    for hub in hubs:
        if hub.get("hub_article_id") == article["article_id"]:
            terms |= set(split_tags(hub.get("related_topics")))
    return terms


def _funnel_index(stage):
    return codes.FUNNEL_STAGES.index(stage) if stage in codes.FUNNEL_STAGES else None


def _insert_position(source, candidate, is_hub_source, funnel_next):
    if is_hub_source:
        return "本文末の関連記事ブロック"
    if funnel_next:
        return "結びの直前"
    if source.get("theme") and source.get("theme") == candidate.get("theme"):
        return "該当する論点の段落直後"
    return "本文末の関連記事ブロック"


def recommend(conn, source_id, limit=3, include_existing=False):
    """source_id の記事に対する関連記事候補をスコア順に返す。"""
    source = repository.get_article(conn, source_id)
    if source is None:
        raise ValueError(f"記事 {source_id} が見つかりません")
    hubs = repository.list_hubs(conn)
    source_hubs = [h for h in hubs if h.get("hub_article_id") == source_id]
    source_terms = _article_terms(source, hubs)
    hub_topics = set()
    for hub in source_hubs:
        hub_topics |= set(split_tags(hub.get("related_topics")))
    existing = {l["target_article_id"] for l in repository.list_links(conn, source_id=source_id)}

    results = []
    for cand in repository.list_articles(conn):
        if cand["article_id"] == source_id:
            continue
        if not include_existing and cand["article_id"] in existing:
            continue
        # 実記事からサンプル記事へのリンクは推薦しない
        if source["data_kind"] == "real" and cand["data_kind"] == "sample":
            continue
        cand_terms = set(split_tags(cand.get("topic_tags")))
        score, factors = 0.0, []
        if source.get("theme") and source.get("theme") == cand.get("theme"):
            score += WEIGHTS["theme"]
            factors.append(f"テーマが同じ（{cand['theme']}）")
        shared = source_terms & cand_terms
        union = source_terms | cand_terms
        if shared:
            score += WEIGHTS["tag"] * len(shared) / len(union)
            factors.append("共通タグ: " + "、".join(sorted(shared)))
        hub_match = hub_topics & cand_terms
        if hub_match:
            score += WEIGHTS["hub_topic"]
            factors.append("ハブの関連テーマに該当: " + "、".join(sorted(hub_match)))
        si, ci = _funnel_index(source.get("funnel_stage")), _funnel_index(cand.get("funnel_stage"))
        funnel_next = si is not None and ci is not None and ci == si + 1
        if funnel_next:
            score += WEIGHTS["funnel_next"]
            factors.append(f"読者の次の段階へつなぐ（{source['funnel_stage']}→{cand['funnel_stage']}）")
        elif si is not None and si == ci:
            score += WEIGHTS["funnel_same"]
        if score <= 0 or not (shared or hub_match or factors):
            continue
        basis = "本文確認済みの記事情報" if cand["content_reviewed"] and source["content_reviewed"] \
            else "タイトル・タグからのルール推定（本文未確認）"
        results.append({
            "target_article_id": cand["article_id"],
            "target_title": cand["title"],
            "score": round(score, 2),
            "reason": " / ".join(factors),
            "reader_value": READER_VALUE_BY_PURPOSE.get(
                cand.get("primary_purpose"), "関連する論点を別の角度から深められる"),
            "anchor_text": anchor_text(source_terms, cand),
            "insert_position": _insert_position(source, cand, bool(source_hubs), funnel_next),
            "url_status": cand["url_status"],
            "relevance_basis": basis,
            "hub_id": source_hubs[0]["hub_id"] if source_hubs else None,
            "approval_status": "未登録（提案前）",
        })
    results.sort(key=lambda r: (-r["score"], r["target_article_id"]))
    return results[:limit]


def save_recommendations(conn, source_id, recommendations, actor):
    """推薦をリンク提案（状態: 提案）として登録する。重複は登録しない。"""
    created, skipped = [], []
    for rec in recommendations:
        issues = repository.check_link_candidate(conn, source_id, rec["target_article_id"])
        blocking = [i for i in issues if not i.startswith("不正URL")]
        if blocking:
            skipped.append((rec["target_article_id"], blocking))
            continue
        created.append(repository.create_link(
            conn, source_id, rec["target_article_id"], actor,
            reason=rec["reason"], reader_value=rec["reader_value"], anchor_text=rec["anchor_text"],
            insert_position=rec["insert_position"],
            evidence=f"{ENGINE_NAME}: score={rec['score']}（{rec['relevance_basis']}）",
            hub_id=rec.get("hub_id"), score=rec["score"], proposed_by=ENGINE_NAME,
        ))
    return created, skipped

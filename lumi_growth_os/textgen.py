"""note貼り付け用の関連記事案内文を生成する。

実際のnote編集・公開は人間が行う。本システムはテキストを作るだけで、外部へ送信しない。
URLが確認できていないリンクには実URLを出さず、貼り付け防止のプレースホルダーを入れる。
"""

from . import codes, repository
from .validation import split_tags

URL_PLACEHOLDER = "［URL未確認：このまま貼り付けないでください］"

LEAD_BY_THEME = {
    "AI": "AIに仕事を任せることを、もう少し具体的に考えたい方へ。関連記事では、{focus}掘り下げています。",
    "ORG": "組織と責任のことを、もう一歩踏み込んで考えたい方へ。関連記事では、{focus}掘り下げています。",
    "REG": "地域の産業がこの先どうなるのか、一緒に考えたい方へ。関連記事では、{focus}掘り下げています。",
}
DEFAULT_LEAD = "このテーマをもう少し考えたい方へ。関連記事では、{focus}掘り下げています。"

FOCUS_BY_PURPOSE = {
    "認知": "全体像",
    "共感・信頼": "現場の実感",
    "経営・組織": "経営判断",
    "専門・実務": "実際の業務設計",
    "地域・活動": "地域の現場",
    "相談・仕事接続": "具体的な課題整理",
    "読者定着・世界観": "これまでの問い",
}


def _focus(source, targets):
    """案内文の「〇〇の視点」。主目的があればそれを、なければ共通タグを使う。"""
    focuses = []
    source_tags = set(split_tags(source.get("topic_tags")))
    for article in targets:
        focus = FOCUS_BY_PURPOSE.get(article.get("primary_purpose"))
        if focus is None:
            tags = split_tags(article.get("topic_tags"))
            shared = [t for t in tags if t in source_tags]
            focus = (shared or tags or [None])[0]
        if focus and focus not in focuses:
            focuses.append(focus)
    if not focuses:
        return "別の角度から"
    return "や".join(focuses[:2]) + "の視点から"


def generate_guidance(conn, source_id, link_ids=None, include_rejected=False) -> dict:
    """リンク元記事に貼る案内文を生成する。

    戻り値: {"text", "links", "warnings", "production_ready"}
    production_ready は全リンクが承認済みで、URL・本文確認がそろっている場合のみ True。
    """
    source = repository.get_article(conn, source_id)
    if source is None:
        raise ValueError(f"記事 {source_id} が見つかりません")
    links = repository.list_links(conn, source_id=source_id)
    if link_ids is not None:
        links = [l for l in links if l["link_id"] in set(link_ids)]
    if not include_rejected:
        links = [l for l in links if l["status"] != codes.LINK_REJECTED]
    if not links:
        return {"text": "", "links": [], "warnings": ["対象のリンク提案がありません"], "production_ready": False}

    targets, blocks, warnings, ready_flags = [], [], [], []
    for link in links:
        target = repository.get_article(conn, link["target_article_id"])
        targets.append(target)
        readiness = repository.link_readiness(conn, link)
        ready_flags.append(readiness["production_ready"])
        url_usable = target["url"] and target["url_status"] in codes.URL_STATUSES_USABLE \
            and target["data_kind"] == "real"
        url_line = target["url"] if url_usable else URL_PLACEHOLDER
        if not readiness["production_ready"]:
            warnings.append(f"{link['link_id']}（→{target['title']}）: {readiness['label']}"
                            + (f" — {' / '.join(readiness['blockers'])}" if readiness["blockers"] else ""))
        anchor = link.get("anchor_text")
        lines = []
        if anchor:
            lines.append(anchor)
        lines.append(f"▼{target['title']}")
        lines.append(url_line)
        blocks.append("\n".join(lines))

    lead_template = LEAD_BY_THEME.get(source.get("theme"), DEFAULT_LEAD)
    lead = lead_template.format(focus=_focus(source, targets))
    text = lead + "\n\n" + "\n\n".join(blocks)
    production_ready = all(ready_flags)
    if not production_ready:
        warnings.insert(0, "この文章は仮案です。本番のnoteへは貼り付けないでください。")
    return {"text": text, "links": links, "warnings": warnings, "production_ready": production_ready}

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import codes, repository, textgen  # noqa: E402
from lumi_growth_os.validation import ValidationError, validate_url  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("リンク承認・貼り付け文")
st.caption("状態は「提案 → 確認 → 承認 → 人間によるnote反映 → 表示確認」の順に進みます。"
           "このアプリはnoteを操作しません。note反映は人間が行い、その事実だけを記録します。")

links = common.filter_kind(repository.list_links(conn))
rows = []
for link in links:
    readiness = repository.link_readiness(conn, link)
    rows.append({**link, "readiness": readiness["label"], "blockers": " / ".join(readiness["blockers"])})

tab_list, tab_review, tab_text, tab_check = st.tabs(["提案一覧", "確認・承認", "note貼り付け文", "リンク検査"])

with tab_list:
    common.table(rows, {
        "link_id": "ID", "data_kind": "区分", "source_title": "リンク元", "target_title": "リンク先",
        "status": "承認状態", "readiness": "本番反映", "relevance_status": "関連性",
        "target_url_status": "リンク先URL", "reason": "推薦理由", "reader_value": "読者が得る価値",
        "anchor_text": "推奨リンク文", "insert_position": "挿入場所", "evidence": "根拠", "blockers": "反映できない理由",
    })

with tab_review:
    if not links:
        st.caption("リンク提案がありません")
    else:
        label_map = {f"{l['link_id']}｜{l['source_title']} → {l['target_title']}": l["link_id"] for l in links}
        chosen = st.selectbox("対象の提案", list(label_map))
        link = repository.get_link(conn, label_map[chosen])
        readiness = repository.link_readiness(conn, link)
        st.markdown(f"現在の状態：**{link['status']}**　／　本番反映：**{readiness['label']}**")
        for blocker in readiness["blockers"]:
            st.warning(blocker)

        with st.form("link_content"):
            st.markdown("**提案内容の修正**")
            reason = st.text_area("推薦理由", link["reason"] or "")
            reader_value = st.text_input("読者が次に得られる価値", link["reader_value"] or "")
            anchor = st.text_input("推奨リンク文", link["anchor_text"] or "")
            position = st.selectbox("推奨挿入場所", codes.INSERT_POSITIONS,
                                    index=codes.INSERT_POSITIONS.index(link["insert_position"])
                                    if link["insert_position"] in codes.INSERT_POSITIONS else 0)
            evidence = st.text_input("根拠", link["evidence"] or "")
            if st.form_submit_button("内容を保存"):
                actor = common.actor_or_warn()
                if actor:
                    repository.update_link_content(conn, link["link_id"], {
                        "reason": reason, "reader_value": reader_value, "anchor_text": anchor,
                        "insert_position": position, "evidence": evidence}, actor)
                    st.success("保存しました")

        nexts = repository.allowed_transitions(link["status"])
        if nexts:
            with st.form("link_transition"):
                st.markdown("**状態の変更**")
                new_status = st.selectbox("次の状態", nexts)
                approver = st.text_input("承認者（「承認」に必須）")
                comment = st.text_input("変更内容・コメント")
                if new_status == "note反映":
                    st.info("noteの編集画面で人間がリンクを設置した後に記録してください。")
                if st.form_submit_button("状態を変更", type="primary"):
                    actor = common.actor_or_warn()
                    if actor:
                        try:
                            repository.transition_link(conn, link["link_id"], new_status, actor,
                                                       approver=approver, comment=comment)
                            st.success(f"{new_status} に変更しました")
                        except ValidationError as exc:
                            st.error(str(exc))
        st.markdown("**この提案の操作履歴**")
        common.table(repository.list_audit(conn, entity_type="link", entity_id=link["link_id"]),
                     {"at": "日時", "actor": "担当者", "action": "操作", "approver": "承認者", "comment": "コメント"})

with tab_text:
    sources = sorted({l["source_article_id"] for l in links})
    if not sources:
        st.caption("リンク提案がありません")
    else:
        source_id = st.selectbox(
            "案内文を作る記事（リンク元）", sources,
            format_func=lambda a: f"{a}｜{repository.get_article(conn, a)['title']}")
        source_links = [l for l in links if l["source_article_id"] == source_id and l["status"] != codes.LINK_REJECTED]
        picked = st.multiselect("含めるリンク", [l["link_id"] for l in source_links],
                                default=[l["link_id"] for l in source_links])
        result = textgen.generate_guidance(conn, source_id, link_ids=picked)
        if result["production_ready"]:
            st.success("全リンクが承認済みで、URL・本文確認がそろっています。noteへの反映は人間が行ってください。")
        for warning in result["warnings"]:
            st.warning(warning)
        if result["text"]:
            st.markdown("右上のアイコンでコピーできます。")
            st.code(result["text"], language=None, wrap_lines=True)

with tab_check:
    st.markdown("**全リンク提案と記事URLの検査**（不正URL・重複リンク・自己リンク・不在記事）")
    issues = []
    for article in repository.list_articles(conn):
        kind, _, message = validate_url(article["url"])
        if kind == "invalid" or article["url_status"] == "不正":
            issues.append({"対象": article["article_id"], "種類": "不正URL", "内容": f"{article['url']}：{message}"})
        elif kind == "note_article" and "作成者ID" in message:
            issues.append({"対象": article["article_id"], "種類": "要確認URL", "内容": message})
    seen = set()
    for link in repository.list_links(conn):
        pair = (link["source_article_id"], link["target_article_id"])
        if pair[0] == pair[1]:
            issues.append({"対象": link["link_id"], "種類": "自己リンク", "内容": f"{pair[0]} → 自分自身"})
        if pair in seen:
            issues.append({"対象": link["link_id"], "種類": "重複リンク", "内容": f"{pair[0]} → {pair[1]}"})
        seen.add(pair)
    if issues:
        st.dataframe(issues, hide_index=True, width="stretch")
    else:
        st.success("問題は見つかりませんでした")

    st.markdown("**登録前の個別チェック**")
    options = common.article_options(conn)
    c1, c2 = st.columns(2)
    src = c1.selectbox("リンク元", list(options), key="check_src")
    tgt = c2.selectbox("リンク先", list(options), key="check_tgt")
    found = repository.check_link_candidate(conn, options[src], options[tgt])
    if found:
        for f in found:
            st.error(f)
    else:
        st.success("登録可能です")

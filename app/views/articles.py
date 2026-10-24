import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import codes, metrics, repository  # noqa: E402
from lumi_growth_os.validation import ValidationError  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("記事資産台帳")
st.caption("欠損は「未計測」と表示し、0と区別します。未確認のURLは推測で生成しません。")

articles = common.filter_kind(repository.list_articles(conn))
f1, f2, f3 = st.columns(3)
theme_filter = f1.multiselect("テーマ", list(codes.THEMES))
url_filter = f2.multiselect("URL確認状態", codes.URL_STATUSES)
hub_only = f3.toggle("ハブ記事のみ")
hub_article_ids = {h["hub_article_id"]: h["hub_id"] for h in repository.list_hubs(conn) if h["hub_article_id"]}
if theme_filter:
    articles = [a for a in articles if a["theme"] in theme_filter]
if url_filter:
    articles = [a for a in articles if a["url_status"] in url_filter]
if hub_only:
    articles = [a for a in articles if a["article_id"] in hub_article_ids]


def latest_metric(article_id):
    rows = repository.list_metrics(conn, article_id)
    return rows[-1] if rows else None


tab_list, tab_edit, tab_new = st.tabs(["一覧・一括編集", "詳細編集", "新規登録"])

with tab_list:
    st.markdown("表のセルを直接編集し「変更を保存」を押すと、検証のうえ保存し操作履歴に記録します。")
    records = []
    for a in articles:
        m = latest_metric(a["article_id"])
        links = repository.list_links(conn, source_id=a["article_id"])
        records.append({
            "記事ID": a["article_id"], "区分": common.kind_label(a["data_kind"]), "タイトル": a["title"],
            "タイトル状態": a["title_status"], "URL状態": a["url_status"],
            "ハブ": hub_article_ids.get(a["article_id"], ""),
            "テーマ": a["theme"] or "", "主目的": a["primary_purpose"] or "",
            "タイトル構造": a["title_structure"] or "", "Human": a["human_code"] or "",
            "Perspective": a["perspective_code"] or "", "Specificity": a["specificity_code"] or "",
            "導線段階": a["funnel_stage"] or "", "本文確認済み": bool(a["content_reviewed"]),
            "最新計測": f"{m['measured_at']}（{m['window_type']}）" if m else common.MISSING,
            "スキ": common.fmt_count(m["likes"]) if m else common.MISSING,
            "PV": common.fmt_count(m["pv"]) if m else common.MISSING,
            "関連記事数": len(links), "確認状態": a["verification_status"],
        })
    if records:
        original = pd.DataFrame(records)
        edited = st.data_editor(
            original, hide_index=True, width="stretch", key="article_editor",
            disabled=["記事ID", "区分", "タイトル状態", "URL状態", "ハブ", "最新計測", "スキ", "PV", "関連記事数",
                      "確認状態"],
            column_config={
                "テーマ": st.column_config.SelectboxColumn(options=common.code_options(codes.THEMES)),
                "主目的": st.column_config.SelectboxColumn(options=[""] + codes.PURPOSES),
                "Human": st.column_config.SelectboxColumn(options=common.code_options(codes.HUMAN_CODES)),
                "Perspective": st.column_config.SelectboxColumn(options=common.code_options(codes.PERSPECTIVE_CODES)),
                "Specificity": st.column_config.SelectboxColumn(options=common.code_options(codes.SPECIFICITY_CODES)),
                "導線段階": st.column_config.SelectboxColumn(options=common.stage_options()),
                "タイトル構造": st.column_config.TextColumn(help="T01〜T10をカンマ区切りで複数指定可"),
            },
        )
        field_map = {"タイトル": "title", "テーマ": "theme", "主目的": "primary_purpose",
                     "タイトル構造": "title_structure", "Human": "human_code", "Perspective": "perspective_code",
                     "Specificity": "specificity_code", "導線段階": "funnel_stage", "本文確認済み": "content_reviewed"}
        if st.button("変更を保存", type="primary"):
            name = common.actor_or_warn()
            if name:
                saved, errors = 0, []
                for (_, before), (_, after) in zip(original.iterrows(), edited.iterrows()):
                    changes = {field_map[c]: after[c] for c in field_map if before[c] != after[c]}
                    if not changes:
                        continue
                    try:
                        repository.update_article(conn, before["記事ID"], changes, name, comment="一覧から編集")
                        saved += 1
                    except ValidationError as exc:
                        errors.append(f"{before['記事ID']}: {exc}")
                if saved:
                    st.success(f"{saved}件を保存しました")
                for e in errors:
                    st.error(e)
    else:
        st.caption("該当する記事がありません")

with tab_edit:
    options = common.article_options(conn)
    if options:
        label = st.selectbox("編集する記事", list(options))
        a = repository.get_article(conn, options[label])
        if a["data_kind"] == "sample":
            st.warning("サンプル記事です（実績ではありません）")
        with st.form("edit_article"):
            title = st.text_input("記事タイトル", a["title"])
            c1, c2 = st.columns(2)
            title_status = c1.selectbox("タイトル確認状態", codes.TITLE_STATUSES,
                                        index=codes.TITLE_STATUSES.index(a["title_status"]))
            url = c2.text_input("記事URL（確認できたもののみ。推測で入力しない）", a["url"] or "")
            url_status = c1.selectbox("URL確認状態", codes.URL_STATUSES[:3],
                                      index=codes.URL_STATUSES[:3].index(a["url_status"])
                                      if a["url_status"] in codes.URL_STATUSES[:3] else 0)
            published_at = c2.text_input("公開日時（YYYY-MM-DD HH:MM）", a["published_at"] or "")
            theme = c1.selectbox("テーマ", common.code_options(codes.THEMES),
                                 index=common.code_options(codes.THEMES).index(a["theme"] or ""))
            purpose = c2.selectbox("主目的", [""] + codes.PURPOSES,
                                   index=([""] + codes.PURPOSES).index(a["primary_purpose"] or ""))
            target_reader = st.text_input("想定読者", a["target_reader"] or "")
            core_claim = st.text_area("記事の中心主張", a["core_claim"] or "")
            c3, c4, c5, c6 = st.columns(4)
            title_structure = c3.text_input("タイトル構造（T01,T02…）", a["title_structure"] or "")
            human = c4.selectbox("Human", common.code_options(codes.HUMAN_CODES),
                                 index=common.code_options(codes.HUMAN_CODES).index(a["human_code"] or ""))
            perspective = c5.selectbox("Perspective", common.code_options(codes.PERSPECTIVE_CODES),
                                       index=common.code_options(codes.PERSPECTIVE_CODES).index(a["perspective_code"] or ""))
            specificity = c6.selectbox("Specificity", common.code_options(codes.SPECIFICITY_CODES),
                                       index=common.code_options(codes.SPECIFICITY_CODES).index(a["specificity_code"] or ""))
            topic_tags = st.text_input("関連テーマタグ（カンマ区切り・推薦に使用）", a["topic_tags"] or "")
            c7, c8 = st.columns(2)
            funnel = c7.selectbox("つなぐ導線段階", common.stage_options(),
                                  index=common.stage_options().index(a["funnel_stage"] or ""))
            revenue_path = c8.text_input("収益導線（例：メンバーシップ案内）", a["revenue_path"] or "")
            content_reviewed = st.checkbox("本文内容を人間が確認した（関連性判断の前提）", bool(a["content_reviewed"]))
            pre_hypothesis = st.text_input("公開前仮説", a["pre_hypothesis"] or "")
            verdict = st.selectbox("仮説判定", [""] + codes.HYPOTHESIS_VERDICTS,
                                   index=([""] + codes.HYPOTHESIS_VERDICTS).index(a["hypothesis_verdict"] or ""))
            source = st.text_input("情報の出典", a["source"] or "")
            verification = st.selectbox("確認状態", codes.VERIFICATION_STATUSES,
                                        index=codes.VERIFICATION_STATUSES.index(a["verification_status"]))
            notes = st.text_area("メモ", a["notes"] or "")
            submitted = st.form_submit_button("保存", type="primary")
        if submitted:
            name = common.actor_or_warn()
            if name:
                try:
                    repository.update_article(conn, a["article_id"], {
                        "title": title, "title_status": title_status, "url": url, "url_status": url_status,
                        "published_at": published_at, "theme": theme, "primary_purpose": purpose,
                        "target_reader": target_reader, "core_claim": core_claim,
                        "title_structure": title_structure, "human_code": human, "perspective_code": perspective,
                        "specificity_code": specificity, "topic_tags": topic_tags, "funnel_stage": funnel,
                        "revenue_path": revenue_path, "content_reviewed": content_reviewed,
                        "pre_hypothesis": pre_hypothesis, "hypothesis_verdict": verdict, "source": source,
                        "verification_status": verification, "notes": notes,
                    }, name)
                    st.success("保存しました")
                except ValidationError as exc:
                    st.error(str(exc))
        st.markdown("**計測履歴**")
        rows = repository.list_metrics(conn, a["article_id"])
        for r in rows:
            r.update(metrics.compute_proxies(r))
        common.table([{**r, **{k: common.fmt_count(r[k]) for k in repository.METRIC_FIELDS},
                       "warn": " / ".join(metrics.row_warnings(r))} for r in rows], {
            "measured_at": "計測日時", "window_type": "区分", "hours_since_publish": "経過時間",
            "imp": "IMP", "pv": "PV", "likes": "スキ", "comments": "コメント",
            "meaningful_comments": "有意味コメント", "source": "出典", "warn": "注意",
        })
        if a["legacy_json"]:
            with st.expander("旧台帳から保全した原文"):
                st.json(a["legacy_json"])

with tab_new:
    with st.form("new_article", clear_on_submit=False):
        c1, c2 = st.columns(2)
        article_id = c1.text_input("記事ID（例：LS-A010）")
        data_kind = c2.selectbox("データ区分", list(codes.DATA_KINDS), format_func=lambda k: codes.DATA_KINDS[k])
        title = st.text_input("記事タイトル")
        title_status = c1.selectbox("タイトル確認状態", codes.TITLE_STATUSES, key="new_ts")
        url = c2.text_input("記事URL（確認できない場合は空欄）")
        theme = c1.selectbox("テーマ", common.code_options(codes.THEMES), key="new_theme")
        published_at = c2.text_input("公開日時（YYYY-MM-DD HH:MM）")
        topic_tags = st.text_input("関連テーマタグ（カンマ区切り）")
        source = st.text_input("情報の出典")
        submitted = st.form_submit_button("登録", type="primary")
    if submitted:
        name = common.actor_or_warn()
        if name:
            try:
                repository.create_article(conn, {
                    "article_id": article_id, "title": title, "title_status": title_status, "url": url,
                    "theme": theme, "published_at": published_at, "topic_tags": topic_tags, "source": source,
                    "data_kind": data_kind,
                }, name)
                st.success(f"{article_id} を登録しました")
            except ValidationError as exc:
                st.error(str(exc))

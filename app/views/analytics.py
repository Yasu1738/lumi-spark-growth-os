import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import codes, metrics, repository  # noqa: E402
from lumi_growth_os.validation import ValidationError  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("記事分析")
st.info(metrics.PROXY_DISCLAIMER)

tab_article, tab_entry, tab_structure, tab_account, tab_ranking, tab_insight = st.tabs(
    ["記事別実績", "実績を登録", "構造分析（Ver.6.1）", "アカウント全体", "ランキング", "読者理解"])

with tab_article:
    window = st.radio("計測区分（同じ区分同士で比較）", list(codes.WINDOW_TYPES),
                      format_func=lambda w: codes.WINDOW_TYPES[w], horizontal=True)
    rows = common.filter_kind(repository.list_metrics(conn, window_type=window))
    for r in rows:
        r.update(metrics.compute_proxies(r))
    for w in metrics.comparability_warnings(rows):
        st.warning(w)
    display = []
    for r in rows:
        display.append({
            "記事": f"{r['article_id']}｜{r['title']}", "区分": common.kind_label(r["data_kind"]),
            "計測日時": r["measured_at"],
            "公開後経過(h)": r["hours_since_publish"] if r["hours_since_publish"] is not None else "不明",
            **{repository.METRIC_LABELS[k]: common.fmt_count(r[k]) for k in repository.METRIC_FIELDS},
            "IMP→PV Proxy": common.fmt_proxy(r["imp_pv_proxy"]),
            "スキ/PV Proxy": common.fmt_proxy(r["like_pv_proxy"]),
            "コメント/PV Proxy": common.fmt_proxy(r["comment_pv_proxy"]),
            "注意": " / ".join(metrics.row_warnings(r)), "出典": r["source"],
        })
    if display:
        st.dataframe(display, hide_index=True, width="stretch")
    else:
        st.caption(f"{codes.WINDOW_TYPES[window]}の登録はまだありません。24h/72h値がない場合、累積値で埋めません。")

with tab_entry:
    options = common.article_options(conn)
    with st.form("metric_entry"):
        label = st.selectbox("記事", list(options))
        c1, c2, c3 = st.columns(3)
        measured_at = c1.text_input("計測日時（YYYY-MM-DD HH:MM）")
        window = c2.selectbox("計測区分", list(codes.WINDOW_TYPES), format_func=lambda w: codes.WINDOW_TYPES[w])
        source = c3.text_input("出典（例：note管理画面 記事別アクセス）")
        st.caption("未計測の項目は空欄のままにしてください。空欄は0として保存されません。")
        cols = st.columns(4)
        values = {}
        for i, field in enumerate(repository.METRIC_FIELDS):
            values[field] = cols[i % 4].text_input(repository.METRIC_LABELS[field], key=f"m_{field}")
        condition = st.text_input("計測条件メモ（母集団・画面・期間など）")
        if st.form_submit_button("登録", type="primary"):
            actor = common.actor_or_warn()
            if actor:
                try:
                    repository.add_metric(conn, options[label], measured_at, window, values, source, actor,
                                          condition_note=condition)
                    st.success("登録しました")
                except ValidationError as exc:
                    st.error(str(exc))

with tab_structure:
    st.markdown("構造コードと反応の関係を**仮説として**見ます。因果関係は断定しません。")
    window = st.radio("比較に使う区分", ["72h", "24h"], horizontal=True, key="structure_window")
    articles = {a["article_id"]: a for a in common.filter_kind(repository.list_articles(conn))}
    latest = {}
    for r in repository.list_metrics(conn, window_type=window):
        if r["article_id"] in articles:
            latest[r["article_id"]] = {**articles[r["article_id"]], **r, **metrics.compute_proxies(r)}
    rows = list(latest.values())
    if any(r["data_kind"] == "sample" for r in rows):
        st.warning("サンプルデータを含みます。サイドバーでサンプル表示を切ると実データのみで集計します。")
    st.markdown("**初期仮説の状態**")
    st.dataframe(metrics.hypothesis_status(rows), hide_index=True, width="stretch")
    for code_field, title in (("specificity_code", "Specificity × IMP→PV Proxy"),):
        st.markdown(f"**{title}**")
        st.dataframe(metrics.summarize_by_code(rows, code_field, "imp_pv_proxy"), hide_index=True, width="stretch")
    st.markdown("**Perspective Shift × スキ/PV Proxy**")
    st.dataframe(metrics.summarize_by_code(rows, "perspective_code", "like_pv_proxy"), hide_index=True, width="stretch")
    st.markdown("**タイトル構造 × コメント/PV Proxy**")
    st.dataframe(metrics.summarize_by_code(rows, "title_structure", "comment_pv_proxy"), hide_index=True, width="stretch")
    st.markdown("**Human × コメント/PV Proxy**")
    st.dataframe(metrics.summarize_by_code(rows, "human_code", "comment_pv_proxy"), hide_index=True, width="stretch")
    st.caption(f"記事数が{codes.MIN_ARTICLES_FOR_HYPOTHESIS}本未満のコードは判断しません。構造コード未設定の実記事は集計に入りません。")

with tab_account:
    st.markdown("アカウント全体の実績です。**記事ごとの実績とは混同しないでください。**")
    snaps = common.filter_kind(repository.list_account_snapshots(conn))
    display = []
    for s in snaps:
        display.append({
            "集計日時": s["measured_at"], "対象期間": f"{s['period_start'] or '?'}〜{s['period_end'] or '?'}",
            "期間メモ": s["period_note"], "IMP": common.fmt_count(s["imp"]), "PV": common.fmt_count(s["pv"]),
            "スキ": common.fmt_count(s["likes"]), "コメント": common.fmt_count(s["comments"]),
            "フォロー増": common.fmt_count(s["follows"]), "投稿数": common.fmt_count(s["posts"]),
            "スキ/PV Proxy": common.fmt_proxy(metrics.proxy(s["likes"], s["pv"])),
            "出典": s["source"], "メモ": s["notes"],
        })
    st.dataframe(display, hide_index=True, width="stretch")
    st.caption("集計期間が異なる行同士は比較できません。")
    with st.expander("アカウント実績を登録"):
        with st.form("account_entry"):
            c1, c2, c3 = st.columns(3)
            data = {"measured_at": c1.text_input("集計日時"), "period_start": c2.text_input("対象期間開始"),
                    "period_end": c3.text_input("対象期間終了")}
            cols = st.columns(6)
            for i, (k, lbl) in enumerate([("imp", "IMP"), ("pv", "PV"), ("likes", "スキ"), ("comments", "コメント"),
                                          ("follows", "フォロー増(正確値)"), ("posts", "投稿数")]):
                data[k] = cols[i].text_input(lbl, key=f"acc_{k}")
            data["source"] = st.text_input("出典")
            data["notes"] = st.text_input("メモ")
            if st.form_submit_button("登録"):
                actor = common.actor_or_warn()
                if actor:
                    try:
                        repository.add_account_snapshot(conn, data, actor)
                        st.success("登録しました")
                    except ValidationError as exc:
                        st.error(str(exc))

with tab_ranking:
    for snap in repository.list_rankings(conn):
        st.markdown(f"**{snap['captured_at']} 時点：{snap['metric']}**")
        st.warning(snap["period_note"])
        st.dataframe([{
            "順位": e["position"], "値": e["value"], "記事": e["article_title"] or e["title_text"] or "（記事名未確認）",
            "照合状態": e["match_status"],
        } for e in snap["entries"]], hide_index=True, width="stretch")
        st.caption(f"出典：{snap['source']}。{snap['notes'] or ''}")

with tab_insight:
    st.markdown("読者コメントから得た課題・関心を要約で残します。**個人名・アカウント名は記録しません。**")
    insights = common.filter_kind(repository.list_reader_insights(conn))
    common.table(insights, {"observed_at": "確認日", "article_id": "記事", "tags": "タグ", "summary": "要約",
                            "hypothesis_impact": "元仮説への影響", "derived_candidate": "派生候補",
                            "data_kind": "区分"})
    options = common.article_options(conn, include_none=True)
    with st.form("insight_entry"):
        label = st.selectbox("記事", list(options))
        tags = st.multiselect("コメントタグ", codes.COMMENT_TAGS)
        summary = st.text_area("要約（個人を特定できる情報は書かない）")
        impact = st.selectbox("元仮説への影響", [""] + codes.HYPOTHESIS_IMPACTS)
        derived = st.text_input("潜在派生候補（新しい論点・問い）")
        if st.form_submit_button("記録"):
            actor = common.actor_or_warn()
            if actor:
                try:
                    repository.add_reader_insight(conn, {"article_id": options[label], "tags": tags,
                                                         "summary": summary, "hypothesis_impact": impact,
                                                         "derived_candidate": derived}, actor)
                    st.success("記録しました")
                except ValidationError as exc:
                    st.error(str(exc))

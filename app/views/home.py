import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import codes, repository  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("Lumi Spark Growth OS")
st.caption("記事を公開するほど、知識と読者との関係が蓄積していく成長基盤（ローカルMVP Ver.1.0）")

st.markdown(
    "**循環**：記事公開 → 新しい読者 → ハブから関連記事へ → 信頼が深まる → コメント・議論 → "
    "読者の課題を把握 → メンバーシップへ自然に → 共同研究・実践 → 実践成果が新しい記事に"
)

articles = repository.list_articles(conn)
real = [a for a in articles if a["data_kind"] == "real"]
sample = [a for a in articles if a["data_kind"] == "sample"]
links = repository.list_links(conn)
real_links = [l for l in links if l["data_kind"] == "real"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("実データの記事", len(real))
c2.metric("サンプル記事（実績ではない）", len(sample))
c3.metric("実記事のリンク提案", len(real_links))
c4.metric("本番反映可能なリンク", sum(1 for l in real_links if repository.link_readiness(conn, l)["production_ready"]))

st.subheader("ハブ")
for hub in repository.list_hubs(conn):
    hub_article = repository.get_article(conn, hub["hub_article_id"]) if hub["hub_article_id"] else None
    steps = repository.list_path_steps(conn, hub["hub_id"])
    path = " → ".join([hub["name"]] + [s["label"] for s in steps])
    with st.container(border=True):
        st.markdown(f"**{hub['hub_id']}｜{hub['name']}**　`{hub['status']}`")
        st.caption(path)
        if hub_article:
            st.write(f"ハブ記事：{hub_article['title']}（URL: {hub_article['url_status']}／本文: "
                     f"{'確認済み' if hub_article['content_reviewed'] else '未確認'}）")

st.subheader("人間の確認・承認が必要な事項")
pending = repository.pending_human_items(conn)
for label, items in pending.items():
    with st.expander(f"{label}：{len(items)}件", expanded=False):
        if label == "承認待ちのリンク提案":
            common.table(items, {"link_id": "ID", "source_title": "リンク元", "target_title": "リンク先",
                                 "status": "状態"})
        else:
            common.table(items, {"article_id": "ID", "title": "タイトル", "url_status": "URL",
                                 "title_status": "タイトル"})

st.subheader("運用ルール（要点）")
st.markdown(
    "- 実測値・確認済み事実・推定・仮説を区別する。空欄は「未計測」であり0ではない。\n"
    "- 記事ごとの実績とアカウント全体の実績を混同しない。\n"
    "- 24h/72h値がない場合、後から取得した累積値で埋めない。\n"
    "- AIの推薦は提案にすぎない。リンク提案は「提案→確認→承認→人間によるnote反映→表示確認」の順で進む。\n"
    f"- 構造コード（{', '.join(codes.TITLE_STRUCTURES)}、H/V/C）と反応の関係は仮説として検証する。"
)

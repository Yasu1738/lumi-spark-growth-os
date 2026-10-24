import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import recommend, repository  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("関連記事推薦")
st.caption("タグ・テーマ・ハブ・導線段階に基づくルール推薦です（LLM APIは使いません）。"
           "本文を確認していない記事の関連性は「ルール推定」と表示し、確認済みとはしません。")

options = common.article_options(conn)
label = st.selectbox("推薦の元にする記事（リンク元）", list(options))
limit = st.radio("件数", [2, 3], index=1, horizontal=True)
source_id = options[label]
source = repository.get_article(conn, source_id)
st.caption(f"タグ：{source['topic_tags'] or '（未設定：推薦精度が下がります）'}")

recs = recommend.recommend(conn, source_id, limit=limit)
if not recs:
    st.info("候補が見つかりません。記事のテーマ・タグを設定するか、既存の提案を確認してください。")
for i, rec in enumerate(recs, start=1):
    with st.container(border=True):
        st.markdown(f"**{i}. {rec['target_title']}**（{rec['target_article_id']}／スコア {rec['score']}）")
        st.write(f"推薦理由：{rec['reason']}")
        st.write(f"読者が次に得られる価値：{rec['reader_value']}")
        st.write(f"推奨リンク文：{rec['anchor_text']}")
        st.write(f"推奨挿入場所：{rec['insert_position']}")
        st.write(f"URLの確認状態：{rec['url_status']}　／　関連性の根拠：{rec['relevance_basis']}")
        st.write(f"承認状態：{rec['approval_status']}")

if recs:
    chosen = st.multiselect("リンク提案として登録する候補", [r["target_article_id"] for r in recs],
                            default=[r["target_article_id"] for r in recs])
    if st.button("選択した候補を「提案」として登録", type="primary"):
        actor = common.actor_or_warn()
        if actor:
            created, skipped = recommend.save_recommendations(
                conn, source_id, [r for r in recs if r["target_article_id"] in chosen], actor)
            st.success(f"{len(created)}件を登録しました（状態：提案）。承認は「リンク承認」画面で行います。")
            for target, reasons in skipped:
                st.warning(f"{target}: {' / '.join(reasons)}")

st.subheader("登録済みの提案")
common.table(repository.list_links(conn, source_id=source_id),
             {"link_id": "ID", "target_title": "リンク先", "status": "状態", "relevance_status": "関連性",
              "target_url_status": "URL", "proposed_by": "提案者"})

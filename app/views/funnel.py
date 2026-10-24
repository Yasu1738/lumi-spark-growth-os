import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import codes, repository  # noqa: E402
from lumi_growth_os.validation import ValidationError  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("収益導線")
st.caption("noteの既存メンバーシップ機能を活用する前提です。独自決済は作りません。会員の個人情報は扱いません。")
st.markdown(" → ".join(f"**{s}**" for s in codes.FUNNEL_STAGES))

articles = common.filter_kind(repository.list_articles(conn))
observations = common.filter_kind(repository.list_funnel_observations(conn))
hubs = repository.list_hubs(conn)

st.subheader("段階ごとの記事と実績")
cols = st.columns(len(codes.FUNNEL_STAGES))
for col, stage in zip(cols, codes.FUNNEL_STAGES):
    stage_articles = [a for a in articles if a["funnel_stage"] == stage]
    stage_obs = [o for o in observations if o["stage"] == stage]
    with col:
        st.markdown(f"**{stage}**")
        st.metric("担当記事", len(stage_articles))
        if stage_obs:
            last = stage_obs[-1]
            st.metric("確認済み実績", f"{last['value']}{last['unit']}",
                      help=f"{last['observed_at']}／出典：{last['source']}"
                           + ("（サンプル）" if last["data_kind"] == "sample" else ""))
        else:
            st.caption("実績：未計測")
        for a in stage_articles:
            st.caption(("【S】" if a["data_kind"] == "sample" else "・") + a["title"][:24])

unassigned = [a for a in articles if not a["funnel_stage"]]
if unassigned:
    st.info(f"導線段階が未設定の記事：{len(unassigned)}件（記事資産台帳で設定できます）")

st.subheader("ハブごとの導線ステップ")
for hub in hubs:
    steps = repository.list_path_steps(conn, hub["hub_id"])
    st.write(f"**{hub['name']}**：" + " → ".join(f"{s['label']}［{s['funnel_stage'] or '-'}］" for s in steps))

st.subheader("記事ごとに、つなぐ段階を設定")
options = common.article_options(conn)
with st.form("set_stage"):
    label = st.selectbox("記事", list(options))
    stage = st.selectbox("つなぐ段階", common.stage_options())
    revenue_path = st.text_input("収益導線の内容（例：メンバーシップ紹介記事へのリンク）")
    if st.form_submit_button("保存"):
        actor = common.actor_or_warn()
        if actor:
            try:
                changes = {"funnel_stage": stage}
                if revenue_path:
                    changes["revenue_path"] = revenue_path
                repository.update_article(conn, options[label], changes, actor)
                st.success("保存しました")
            except ValidationError as exc:
                st.error(str(exc))

st.subheader("確認できた実績の記録")
st.caption("会員数・参加率・収益は、確認できる数値のみ出典つきで記録します。推定値は登録できません。")
common.table(observations, {"observed_at": "確認日時", "stage": "段階", "value": "値", "unit": "単位",
                            "source": "出典", "data_kind": "区分", "notes": "メモ"})
with st.form("funnel_obs"):
    c1, c2, c3, c4 = st.columns(4)
    observed_at = c1.text_input("確認日時")
    stage = c2.selectbox("段階", codes.FUNNEL_STAGES)
    value = c3.text_input("値（整数）")
    unit = c4.text_input("単位", "件")
    source = st.text_input("出典（例：noteメンバーシップ管理画面）")
    notes = st.text_input("メモ（個人情報は書かない）")
    if st.form_submit_button("記録"):
        actor = common.actor_or_warn()
        if actor:
            try:
                repository.add_funnel_observation(conn, {"observed_at": observed_at, "stage": stage, "value": value,
                                                         "unit": unit, "source": source, "notes": notes}, actor)
                st.success("記録しました")
            except ValidationError as exc:
                st.error(str(exc))

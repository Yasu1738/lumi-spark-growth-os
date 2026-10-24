import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import repository  # noqa: E402
from lumi_growth_os.validation import ValidationError  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("ハブ構造")
st.caption("人気記事をハブとして関連記事へつなぐハブ＆スポーク構造。編集は一覧から、図は確認用の補助です。")


def _dot_escape(text, width=11, max_lines=2):
    """図のノード名。長いタイトルは折り返し、図が縮小しすぎないようにする。"""
    text = (text or "").replace('"', "'").replace("\\n", " ")
    lines = [text[i:i + width] for i in range(0, len(text), width)][:max_lines]
    if len(text) > width * max_lines:
        lines[-1] = lines[-1][:-1] + "…"
    return "\\n".join(lines)


def hub_graph(hub, steps, links):
    lines = ['digraph G {', 'rankdir=TB;', 'nodesep=0.25;', 'node [shape=box, style="rounded,filled", fillcolor="#f5f5f5", fontsize=16];']
    lines.append(f'hub [label="{_dot_escape(hub["name"])}", fillcolor="#ffe8a3"];')
    previous = "hub"
    for step in steps:
        node = f"s{step['step_id']}"
        label = _dot_escape(step["label"]) + (f"\\n[{step['funnel_stage']}]" if step["funnel_stage"] else "")
        lines.append(f'{node} [label="{label}"];')
        lines.append(f"{previous} -> {node};")
        previous = node
    for link in links:
        node = f"l{link['link_id'].replace('-', '_')}"
        color = "#c8e6c9" if link["status"] in ("承認", "note反映", "表示確認") else "#ffffff"
        style = "solid" if link["status"] in ("承認", "note反映", "表示確認") else "dashed"
        lines.append(f'{node} [label="{_dot_escape(link["target_title"])}\\n（{link["status"]}）", fillcolor="{color}"];')
        lines.append(f'hub -> {node} [style={style}, color="#888888"];')
    lines.append("}")
    return "\n".join(lines)


article_opts = common.article_options(conn, include_none=True)
article_labels = list(article_opts)

for hub in repository.list_hubs(conn):
    steps = repository.list_path_steps(conn, hub["hub_id"])
    links = repository.list_links(conn, source_id=hub["hub_article_id"]) if hub["hub_article_id"] else []
    links = common.filter_kind(links)
    st.subheader(f"{hub['hub_id']}｜{hub['name']}")
    st.caption(" → ".join([hub["name"]] + [s["label"] for s in steps]))
    if "仮" in (hub["status"] or ""):
        st.warning(f"状態：{hub['status']}。ハブ記事の記事名・URLは未照合です。")

    left, right = st.columns([1, 1])
    with left:
        with st.form(f"hub_{hub['hub_id']}"):
            name = st.text_input("ハブ名", hub["name"])
            current = next((k for k, v in article_opts.items() if v == hub["hub_article_id"]), "（未設定）")
            hub_article_label = st.selectbox("ハブ記事", article_labels, index=article_labels.index(current)
                                             if current in article_labels else 0)
            related = st.text_input("関連テーマ（カンマ区切り）", hub["related_topics"] or "")
            status = st.text_input("状態", hub["status"])
            description = st.text_area("説明", hub["description"] or "")
            if st.form_submit_button("ハブ情報を保存"):
                actor = common.actor_or_warn()
                if actor:
                    try:
                        repository.update_hub(conn, hub["hub_id"], {
                            "name": name, "hub_article_id": article_opts[hub_article_label],
                            "related_topics": related, "status": status, "description": description,
                        }, actor)
                        st.success("保存しました")
                    except ValidationError as exc:
                        st.error(str(exc))

        st.markdown("**導線ステップ（一覧で編集）**")
        id_to_label = {v: k for k, v in article_opts.items()}
        frame = pd.DataFrame([{
            "順番": s["step_order"], "ステップ": s["label"], "導線段階": s["funnel_stage"] or "",
            "割当記事": id_to_label.get(s["article_id"], "（未設定）"), "メモ": s["notes"] or "",
        } for s in steps] or [{"順番": 1, "ステップ": "", "導線段階": "", "割当記事": "（未設定）", "メモ": ""}])
        edited = st.data_editor(
            frame, num_rows="dynamic", hide_index=True, width="stretch", key=f"steps_{hub['hub_id']}",
            column_config={
                "順番": st.column_config.NumberColumn(min_value=1, step=1),
                "導線段階": st.column_config.SelectboxColumn(options=common.stage_options()),
                "割当記事": st.column_config.SelectboxColumn(options=article_labels),
            },
        )
        if st.button("導線ステップを保存", key=f"save_steps_{hub['hub_id']}"):
            actor = common.actor_or_warn()
            if actor:
                ordered = edited.sort_values("順番", na_position="last")
                try:
                    repository.replace_path_steps(conn, hub["hub_id"], [{
                        "label": row["ステップ"], "funnel_stage": row["導線段階"] or None,
                        "article_id": article_opts.get(row["割当記事"]), "notes": row["メモ"],
                    } for _, row in ordered.iterrows()], actor)
                    st.success("保存しました")
                except ValidationError as exc:
                    st.error(str(exc))
    with right:
        st.graphviz_chart(hub_graph(hub, steps, links))
        st.caption("実線=承認以降、破線=提案・確認段階（仮案を含む）")
        common.table(links, {"link_id": "ID", "target_title": "関連記事", "status": "状態",
                             "target_url_status": "URL"})
    st.divider()

with st.expander("ハブを追加"):
    with st.form("new_hub"):
        hub_id = st.text_input("ハブID（例：HUB-MKT）")
        name = st.text_input("ハブ名")
        hub_article_label = st.selectbox("ハブ記事", article_labels)
        related = st.text_input("関連テーマ（カンマ区切り）")
        if st.form_submit_button("追加"):
            actor = common.actor_or_warn()
            if actor:
                try:
                    repository.create_hub(conn, {"hub_id": hub_id, "name": name,
                                                 "hub_article_id": article_opts[hub_article_label],
                                                 "related_topics": related, "sort_order": 99}, actor)
                    st.success("追加しました")
                except ValidationError as exc:
                    st.error(str(exc))

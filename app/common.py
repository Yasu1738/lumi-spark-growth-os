"""画面共通の部品。データ操作は lumi_growth_os に任せ、ここでは表示だけを扱う。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from lumi_growth_os import codes, config, db, seed  # noqa: E402

MISSING = "未計測"
NOT_COMPUTABLE = "計算不能"


@st.cache_resource
def _connection(path: str):
    conn = db.connect(path)
    db.init_db(conn)
    if not seed.is_seeded(conn) and conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0:
        seed.seed_all(conn, include_samples=True)
    return conn


def get_conn():
    return _connection(str(config.db_path()))


def sidebar():
    st.sidebar.text_input("担当者名（操作履歴に記録）", key="actor", placeholder="例：西冨")
    st.sidebar.toggle("サンプルデータを表示", value=True, key="show_samples",
                      help="サンプルは画面確認用で、実績ではありません")
    st.sidebar.caption(f"DB: `{config.db_path()}`")
    st.sidebar.info("このアプリはnoteへの投稿・編集・データ取得、決済、会員操作を一切行いません。"
                    "提案はすべて人間の承認で止まります。")


def actor() -> str:
    return (st.session_state.get("actor") or "").strip()


def actor_or_warn():
    name = actor()
    if not name:
        st.warning("書き込みの前に、左のサイドバーで担当者名を入力してください。")
    return name


def show_samples() -> bool:
    return bool(st.session_state.get("show_samples", True))


def filter_kind(rows):
    return rows if show_samples() else [r for r in rows if r.get("data_kind") != "sample"]


def kind_label(kind):
    return "サンプル" if kind == "sample" else "実データ"


def fmt_count(value):
    return MISSING if value is None else f"{value:,}"


def fmt_proxy(value):
    return NOT_COMPUTABLE if value is None else f"{value:.2f}"


def table(rows, columns: dict):
    """columns: {元キー: 表示名}。行がなければ空表示。"""
    if not rows:
        st.caption("（データなし）")
        return
    frame = pd.DataFrame([{label: row.get(key) for key, label in columns.items()} for row in rows])
    st.dataframe(frame, hide_index=True, width="stretch")


def article_options(conn, include_none=False, real_only=False):
    from lumi_growth_os import repository

    rows = filter_kind(repository.list_articles(conn, "real" if real_only else None))
    options = {f"{a['article_id']}｜{a['title']}": a["article_id"] for a in rows}
    if include_none:
        options = {"（未設定）": None, **options}
    return options


def code_options(mapping):
    return [""] + list(mapping)


def stage_options():
    return [""] + codes.FUNNEL_STAGES

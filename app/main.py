"""Lumi Spark Growth OS — Streamlit エントリーポイント。

起動: streamlit run app/main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Lumi Spark Growth OS", page_icon="✨", layout="wide")

VIEWS = Path(__file__).resolve().parent / "views"

navigation = st.navigation({
    "全体": [
        st.Page(VIEWS / "home.py", title="ホーム", icon="🏠", default=True),
    ],
    "記事資産": [
        st.Page(VIEWS / "articles.py", title="記事資産台帳", icon="📚"),
        st.Page(VIEWS / "hubs.py", title="ハブ構造", icon="🕸️"),
        st.Page(VIEWS / "recommend.py", title="関連記事推薦", icon="🔎"),
        st.Page(VIEWS / "links.py", title="リンク承認・貼り付け文", icon="✅"),
    ],
    "分析と導線": [
        st.Page(VIEWS / "analytics.py", title="記事分析", icon="📈"),
        st.Page(VIEWS / "funnel.py", title="収益導線", icon="🪜"),
    ],
    "管理": [
        st.Page(VIEWS / "data.py", title="取込・バックアップ・履歴", icon="🗄️"),
    ],
})
navigation.run()

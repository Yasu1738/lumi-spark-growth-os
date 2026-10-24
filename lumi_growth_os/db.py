"""SQLiteスキーマと接続。

設計原則:
- 欠損値は NULL。0 は「計測した結果が0」の意味でのみ使う。
- data_kind で実データ（real）とサンプル（sample）を区別する。
- 記事別の実績（article_metrics）とアカウント全体の実績（account_snapshots）は別テーブル。
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    article_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_status TEXT NOT NULL DEFAULT '未確認',
    url TEXT,
    url_status TEXT NOT NULL DEFAULT '未確認',
    published_at TEXT,
    theme TEXT,
    primary_purpose TEXT,
    secondary_purpose TEXT,
    target_reader TEXT,
    core_claim TEXT,
    title_structure TEXT,
    human_code TEXT,
    perspective_code TEXT,
    specificity_code TEXT,
    emotion_temp TEXT,
    funnel_stage TEXT,
    revenue_path TEXT,
    topic_tags TEXT,
    content_reviewed INTEGER NOT NULL DEFAULT 0 CHECK (content_reviewed IN (0, 1)),
    pre_hypothesis TEXT,
    hypothesis_verdict TEXT,
    source TEXT,
    verification_status TEXT NOT NULL DEFAULT '未確認',
    data_kind TEXT NOT NULL DEFAULT 'real' CHECK (data_kind IN ('real', 'sample')),
    notes TEXT,
    legacy_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hubs (
    hub_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    hub_article_id TEXT REFERENCES articles(article_id) ON DELETE SET NULL,
    related_topics TEXT,
    status TEXT NOT NULL DEFAULT '候補',
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hub_path_steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hub_id TEXT NOT NULL REFERENCES hubs(hub_id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    label TEXT NOT NULL,
    funnel_stage TEXT,
    article_id TEXT REFERENCES articles(article_id) ON DELETE SET NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS link_proposals (
    link_id TEXT PRIMARY KEY,
    source_article_id TEXT NOT NULL REFERENCES articles(article_id),
    target_article_id TEXT NOT NULL REFERENCES articles(article_id),
    hub_id TEXT REFERENCES hubs(hub_id) ON DELETE SET NULL,
    reason TEXT,
    reader_value TEXT,
    anchor_text TEXT,
    insert_position TEXT,
    evidence TEXT,
    score REAL,
    proposed_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '提案',
    relevance_status TEXT NOT NULL DEFAULT '未確認',
    data_kind TEXT NOT NULL DEFAULT 'real' CHECK (data_kind IN ('real', 'sample')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source_article_id, target_article_id),
    CHECK (source_article_id <> target_article_id)
);

CREATE TABLE IF NOT EXISTS article_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    measured_at TEXT NOT NULL,
    window_type TEXT NOT NULL CHECK (window_type IN ('24h', '72h', 'cumulative')),
    hours_since_publish REAL,
    imp INTEGER,
    pv INTEGER,
    likes INTEGER,
    comments INTEGER,
    meaningful_comments INTEGER,
    follows INTEGER,
    consultations INTEGER,
    membership_joins INTEGER,
    source TEXT NOT NULL,
    condition_note TEXT,
    data_kind TEXT NOT NULL DEFAULT 'real' CHECK (data_kind IN ('real', 'sample')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    measured_at TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    imp INTEGER,
    pv INTEGER,
    likes INTEGER,
    comments INTEGER,
    follows INTEGER,
    posts INTEGER,
    period_note TEXT,
    source TEXT NOT NULL,
    notes TEXT,
    data_kind TEXT NOT NULL DEFAULT 'real' CHECK (data_kind IN ('real', 'sample')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL,
    metric TEXT NOT NULL,
    period_note TEXT,
    source TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ranking_entries (
    snapshot_id TEXT NOT NULL REFERENCES ranking_snapshots(snapshot_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    value INTEGER,
    article_id TEXT REFERENCES articles(article_id) ON DELETE SET NULL,
    title_text TEXT,
    match_status TEXT NOT NULL DEFAULT '未照合',
    PRIMARY KEY (snapshot_id, position)
);

CREATE TABLE IF NOT EXISTS funnel_observations (
    obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    stage TEXT NOT NULL,
    value INTEGER NOT NULL CHECK (value >= 0),
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    data_kind TEXT NOT NULL DEFAULT 'real' CHECK (data_kind IN ('real', 'sample')),
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reader_insights (
    insight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT REFERENCES articles(article_id) ON DELETE SET NULL,
    observed_at TEXT NOT NULL,
    tags TEXT,
    summary TEXT NOT NULL,
    hypothesis_impact TEXT,
    derived_candidate TEXT,
    data_kind TEXT NOT NULL DEFAULT 'real' CHECK (data_kind IN ('real', 'sample')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    before_json TEXT,
    after_json TEXT,
    approver TEXT,
    comment TEXT
);

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    detected_format TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    rows_read INTEGER NOT NULL,
    rows_inserted INTEGER NOT NULL,
    rows_skipped INTEGER NOT NULL,
    report_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_metrics_article ON article_metrics(article_id, window_type);
CREATE INDEX IF NOT EXISTS idx_links_source ON link_proposals(source_article_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
"""

REQUIRED_TABLES = {
    "meta", "articles", "hubs", "hub_path_steps", "link_proposals",
    "article_metrics", "account_snapshots", "ranking_snapshots",
    "ranking_entries", "funnel_observations", "reader_insights",
    "audit_log", "import_batches",
}


class LumiConnection(sqlite3.Connection):
    """defer_commit > 0 の間、repository はコミットしない（インポートの一括ロールバック用）。"""

    defer_commit = 0


def connect(path) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, factory=LumiConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()


def table_names(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}

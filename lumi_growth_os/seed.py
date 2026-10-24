"""初期データ投入。

実データ（data_kind='real'）は出典のある情報だけを登録する。
- 指示書（2026-10-24）に記載のハブ候補3記事とランキング画像の値
- 執筆基準Ver.6.1（Ver.5.8追加層7）に記載の2026-08-23時点の記事別実測6件
- note記事運用台帳 Ver.0.1「日次アカウント」シートの1行（読み取りのみで転記）

推定を含む項目（テーマ・タグ）は notes に「タイトルからの推定」と明記する。
構造コード（T/H/V/C）は筆者の判断が必要なため、実記事には設定しない。

サンプル（data_kind='sample'）は画面確認用であり、実績ではない。
"""

from . import recommend, repository

SEED_ACTOR = "system-seed"
SRC_INSTRUCTION = "Lumi Spark Growth OS 実装指示書（2026-10-24）"
SRC_RANKING = "noteランキング画像（2026-10-24 11:51時点、指示書に記載）"
SRC_V61 = "note_prompt_Ver6.1_reading_structure_experiment_20260921.txt（Ver.5.8追加層7）"
SRC_SHEET = "Google Sheets『note記事運用台帳 Ver.0.1』日次アカウント2行目（2026-10-24読み取り）"
ESTIMATE_NOTE = "テーマ・タグはタイトルからの推定（本文未確認）。"

REAL_ARTICLES = [
    {
        "article_id": "LS-A001",
        "title": "プロンプトが上手い人より、『AIに仕事を渡せる人』が強くなる",
        "title_status": "確認済み", "url": "https://note.com/lumispark/n/n3466216b81dc",
        "url_status": "オーナー提示", "theme": "AI", "funnel_stage": "認知",
        "topic_tags": "AI活用,AIエージェント,業務改善,経営者のAI活用,判断と権限,業務設計,製造現場のDX",
        "verification_status": "一部確認", "source": SRC_INSTRUCTION,
        "notes": "HUB-AIのハブ記事（オーナー指定）。タグは指示書の関連記事方向性から設定。本文は未確認。",
    },
    {
        "article_id": "LS-A002",
        "title": "事業承継は、親子関…（以降未確認）",
        "title_status": "一部のみ", "url": "https://note.com/lumispark/n/n2277389a2429",
        "url_status": "オーナー提示", "theme": "ORG",
        "funnel_stage": "認知",
        "topic_tags": "事業承継,継承,リーダーシップ,組織づくり,権限と責任,人材育成,中小企業経営",
        "verification_status": "仮登録", "source": SRC_RANKING + "／URL: オーナー提示（2026-10-24 チャット）",
        "notes": "HUB-ORGの仮登録。URLはオーナーが2026-10-24に提示（共有用パラメータ ?sub_rt=share_b を除去）。"
                 "ランキング画像の記事と同一である前提で登録しているが、正式タイトルは未確認。",
    },
    {
        "article_id": "LS-A003",
        "title": "100年後も、造園屋は造園屋なのだろうか",
        "title_status": "確認済み", "url": "https://note.com/lumispark/n/nac0e0138fc86",
        "url_status": "オーナー提示", "theme": "REG", "funnel_stage": "認知",
        "topic_tags": "地域産業,町工場,産業の未来,新規事業,地域企業の連携,技能の継承,継承,中小企業経営",
        "verification_status": "一部確認", "source": SRC_INSTRUCTION,
        "notes": "HUB-REGのハブ記事（オーナー指定）。本文は未確認。",
    },
    {
        "article_id": "LS-A004", "title": "LINEとCodexをつないだら…（以降未確認）",
        "title_status": "一部のみ", "theme": "AI",
        "topic_tags": "AI活用,業務改善,自動化", "verification_status": "一部確認", "source": SRC_V61,
        "notes": ESTIMATE_NOTE + "原典でタイトルが省略されている。URL未確認。",
    },
    {
        "article_id": "LS-A005", "title": "『みんなでやる』が、なぜ動かなくなるのか",
        "title_status": "確認済み", "theme": "ORG",
        "topic_tags": "組織づくり,権限と責任,役割分担", "verification_status": "一部確認", "source": SRC_V61,
        "notes": ESTIMATE_NOTE + "URL未確認。",
    },
    {
        "article_id": "LS-A006", "title": "情報は、欲しがる人ではなく『使ってくれる人』に集まる",
        "title_status": "確認済み", "theme": "ORG",
        "topic_tags": "情報共有,組織づくり,業務設計", "verification_status": "一部確認", "source": SRC_V61,
        "notes": ESTIMATE_NOTE + "URL未確認。",
    },
    {
        "article_id": "LS-A007", "title": "社長がいなくなったら、会社は何日もつのか",
        "title_status": "確認済み", "theme": "ORG",
        "topic_tags": "事業承継,経営者依存,権限と責任,判断と権限,中小企業経営",
        "verification_status": "一部確認", "source": SRC_V61, "notes": ESTIMATE_NOTE + "URL未確認。",
    },
    {
        "article_id": "LS-A008", "title": "ローカル・ゼブラ企業×シビックテック",
        "title_status": "確認済み", "theme": "REG",
        "topic_tags": "地域企業の連携,地域産業,新規事業,シビックテック",
        "verification_status": "一部確認", "source": SRC_V61, "notes": ESTIMATE_NOTE + "URL未確認。",
    },
    {
        "article_id": "LS-A009", "title": "良いリーダーは、先頭を歩く人なのか…（以降未確認）",
        "title_status": "一部のみ", "theme": "ORG",
        "topic_tags": "リーダーシップ,人材育成,組織づくり", "verification_status": "一部確認",
        "source": SRC_V61, "notes": ESTIMATE_NOTE + "原典でタイトルが省略されている。URL未確認。",
    },
]

# 2026-08-23 時点の記事別実測（原典の「ビュー」をPVとして登録）
V61_METRICS = [
    ("LS-A004", 479, 30), ("LS-A005", 418, 25), ("LS-A006", 399, 19),
    ("LS-A007", 391, 18), ("LS-A008", 390, 14), ("LS-A009", 389, 44),
]

RANKING_VALUES = [88, 66, 65, 46, 46, 46, 45, 43, 40, 40]

HUBS = [
    {
        "hub_id": "HUB-AI", "name": "AIと仕事の未来", "hub_article_id": "LS-A001", "sort_order": 1,
        "status": "候補（オーナー指定）",
        "related_topics": "業務改善,AIエージェント,経営者のAI活用,判断と権限,製造現場のDX",
        "description": "AIに仕事を渡す力を軸に、業務設計・権限設計・現場DXへつなぐ。",
        "steps": [("AIエージェント", "信頼"), ("業務設計", "信頼"), ("実践事例", "信頼"),
                  ("読者との議論", "対話"), ("メンバーシップ", "参加意向")],
    },
    {
        "hub_id": "HUB-ORG", "name": "経営・組織・事業承継", "hub_article_id": "LS-A002", "sort_order": 2,
        "status": "仮登録（URLはオーナー提示・正式タイトル未確認）",
        "related_topics": "リーダーシップ,組織づくり,権限と責任,事業承継,人材育成,中小企業経営",
        "description": "事業承継を入口に、権限と責任・人材育成・中小企業経営へつなぐ。",
        "steps": [("リーダーシップ", "信頼"), ("権限と責任", "信頼"), ("事業承継", "信頼"),
                  ("人材育成", "信頼"), ("読者との議論", "対話"), ("メンバーシップ", "参加意向")],
    },
    {
        "hub_id": "HUB-REG", "name": "地域産業の未来", "hub_article_id": "LS-A003", "sort_order": 3,
        "status": "候補（オーナー指定）",
        "related_topics": "地域産業,町工場,産業の未来,新規事業,地域企業の連携,技能の継承",
        "description": "地域の産業の行く末を問い、町工場・地域企業の連携・新規事業へつなぐ。",
        "steps": [("地域産業", "信頼"), ("町工場", "信頼"), ("地域企業の連携", "信頼"),
                  ("新規事業", "信頼"), ("読者との議論", "対話"), ("メンバーシップ", "参加意向")],
    },
]

SAMPLE_ARTICLES = [
    {"article_id": "SMP-001", "title": "【サンプル】AIエージェントに任せる業務の切り出し方", "theme": "AI",
     "primary_purpose": "専門・実務", "funnel_stage": "信頼", "title_structure": "T01,T09",
     "human_code": "H2", "perspective_code": "V2", "specificity_code": "C2",
     "topic_tags": "AIエージェント,業務設計,業務改善", "published_at": "2026-10-01 07:00"},
    {"article_id": "SMP-002", "title": "【サンプル】製造現場のDX、最初の一歩は紙の棚卸し", "theme": "AI",
     "primary_purpose": "専門・実務", "funnel_stage": "信頼", "title_structure": "T10",
     "human_code": "H2", "perspective_code": "V3", "specificity_code": "C3",
     "topic_tags": "製造現場のDX,業務改善,町工場", "published_at": "2026-10-03 07:00"},
    {"article_id": "SMP-003", "title": "【サンプル】権限を渡せない社長は、何を恐れているのか", "theme": "ORG",
     "primary_purpose": "経営・組織", "funnel_stage": "信頼", "title_structure": "T01,T05",
     "human_code": "H3", "perspective_code": "V3", "specificity_code": "C2",
     "topic_tags": "権限と責任,判断と権限,事業承継", "published_at": "2026-10-05 07:00"},
    {"article_id": "SMP-004", "title": "【サンプル】町工場どうしの共同受注は、何を変えるか", "theme": "REG",
     "primary_purpose": "地域・活動", "funnel_stage": "信頼", "title_structure": "T01",
     "human_code": "H1", "perspective_code": "V1", "specificity_code": "C1",
     "topic_tags": "地域企業の連携,町工場,新規事業", "published_at": "2026-10-07 07:00"},
    {"article_id": "SMP-005", "title": "【サンプル】読者と考える：AIに渡した仕事、戻ってきた仕事", "theme": "AI",
     "primary_purpose": "読者定着・世界観", "funnel_stage": "対話", "title_structure": "T02,T05",
     "human_code": "H3", "perspective_code": "V2", "specificity_code": "C2",
     "topic_tags": "AIエージェント,読者との議論,業務設計", "published_at": "2026-10-09 07:00"},
    {"article_id": "SMP-006", "title": "【サンプル】共同研究会の実践レポート（第1回）", "theme": "META",
     "primary_purpose": "相談・仕事接続", "funnel_stage": "参加意向", "title_structure": "T08",
     "human_code": "H2", "perspective_code": "V1", "specificity_code": "C3",
     "topic_tags": "実践成果,読者との議論,メンバーシップ", "published_at": "2026-10-11 07:00"},
]

# (article_id, window, 経過時間, imp, pv, likes, comments, meaningful)
SAMPLE_METRICS = [
    ("SMP-001", "24h", 24, 2100, 160, 14, 2, 1), ("SMP-001", "72h", 72, 4300, 290, 24, 3, 2),
    ("SMP-002", "24h", 24, 2500, 230, 21, 3, 2), ("SMP-002", "72h", 72, 5200, 410, 39, 5, 3),
    ("SMP-003", "24h", 25, 1900, 150, 18, 6, 4), ("SMP-003", "72h", 73, 3900, 270, 33, 9, 6),
    ("SMP-004", "24h", 24, 1500, 90, 6, 0, 0), ("SMP-004", "72h", 72, 2800, 150, 10, None, None),
    ("SMP-005", "24h", 23, 1700, 120, 13, 7, 5), ("SMP-005", "72h", 71, 3300, 210, 22, 11, 8),
    ("SMP-006", "24h", 24, 1200, 80, 7, 1, 1),
]


def _hours_later(published, hours):
    from datetime import datetime, timedelta

    base = datetime.strptime(published, "%Y-%m-%d %H:%M")
    return (base + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")


def is_seeded(conn) -> bool:
    return conn.execute("SELECT 1 FROM meta WHERE key = 'seeded_at'").fetchone() is not None


def seed_real(conn):
    for data in REAL_ARTICLES:
        repository.create_article(conn, {**data, "data_kind": "real"}, SEED_ACTOR)
    for article_id, pv, likes in V61_METRICS:
        repository.add_metric(
            conn, article_id, "2026-08-23", "cumulative", {"pv": pv, "likes": likes}, SRC_V61, SEED_ACTOR,
            condition_note="2026-08-23確認時点の累積値。原典の表記は『ビュー』。公開日・時刻不明のため経過時間不明",
        )
    for article_id, likes in (("LS-A001", 88), ("LS-A002", 66), ("LS-A003", 46)):
        repository.add_metric(
            conn, article_id, "2026-10-24 11:51", "cumulative", {"likes": likes}, SRC_RANKING, SEED_ACTOR,
            condition_note="ランキング画像の累積スキ数。公開後期間は記事ごとに異なる",
        )
    ts = repository.now_iso()
    conn.execute(
        "INSERT INTO ranking_snapshots(snapshot_id, captured_at, metric, period_note, source, notes, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        ("RANK-20261024-1151", "2026-10-24 11:51", "スキ（累積）",
         "累積値。各記事の公開後経過期間は異なり、同条件の比較ではない", SRC_RANKING,
         "上位10記事。記事名・URLの照合は3件のみ（うち1件は部分一致）", ts),
    )
    matches = {
        1: ("LS-A001", "照合済み（タイトル一致・オーナー提示）", None),
        2: ("LS-A002", "部分一致（タイトル途中まで）", "事業承継は、親子関…"),
        4: ("LS-A003", "照合済み（同数46スキ3件のうち1件。同数内の順位は未確認）", None),
    }
    for position, value in enumerate(RANKING_VALUES, start=1):
        article_id, status, title_text = matches.get(position, (None, "未照合（記事名未確認）", None))
        conn.execute(
            "INSERT INTO ranking_entries(snapshot_id, position, value, article_id, title_text, match_status)"
            " VALUES (?,?,?,?,?,?)",
            ("RANK-20261024-1151", position, value, article_id, title_text, status),
        )
    repository.log_action(conn, SEED_ACTOR, "ランキング登録", "ranking", "RANK-20261024-1151",
                          after={"values": RANKING_VALUES})
    repository.add_account_snapshot(conn, {
        "measured_at": "2026-09-09 20:09", "period_start": "2026-08-13", "period_end": "2026-09-09",
        "imp": 152901, "pv": 3370, "likes": 1968, "comments": 97, "follows": None, "posts": 72,
        "period_note": "28日窓", "source": SRC_SHEET,
        "notes": "フォロー増は画面表示『100+人』で正確値不明のため空欄（台帳の記載どおり）",
    }, SEED_ACTOR)
    repository.add_account_snapshot(conn, {
        "measured_at": "2026-08-23", "imp": None, "pv": 5343, "likes": 338, "comments": 6,
        "period_note": "対象期間不明（原典に記載なし）", "source": SRC_V61,
        "notes": "原典の『全体ビュー』をPVとして登録。全体スキ率6.33%は原典記載値",
    }, SEED_ACTOR)
    for hub in HUBS:
        repository.create_hub(conn, {k: v for k, v in hub.items() if k != "steps"}, SEED_ACTOR)
        repository.replace_path_steps(
            conn, hub["hub_id"], [{"label": l, "funnel_stage": s} for l, s in hub["steps"]], SEED_ACTOR)
    for hub in HUBS:
        recs = recommend.recommend(conn, hub["hub_article_id"], limit=3)
        recommend.save_recommendations(conn, hub["hub_article_id"], recs, SEED_ACTOR)


def seed_samples(conn):
    for data in SAMPLE_ARTICLES:
        repository.create_article(conn, {
            **data, "data_kind": "sample", "title_status": "確認済み", "verification_status": "未確認",
            "source": "サンプルデータ（画面確認用・実績ではない）",
            "notes": "サンプル。実在の記事ではありません。",
        }, SEED_ACTOR)
    for article_id, window, hours, imp, pv, likes, comments, meaningful in SAMPLE_METRICS:
        published = next(a["published_at"] for a in SAMPLE_ARTICLES if a["article_id"] == article_id)
        repository.add_metric(
            conn, article_id, _hours_later(published, hours), window,
            {"imp": imp, "pv": pv, "likes": likes, "comments": comments, "meaningful_comments": meaningful},
            "サンプルデータ", SEED_ACTOR, condition_note="サンプル（実績ではない）",
        )
    for source_id in ("SMP-001", "SMP-003"):
        recs = recommend.recommend(conn, source_id, limit=2)
        recommend.save_recommendations(conn, source_id, recs, SEED_ACTOR)
    repository.add_funnel_observation(conn, {
        "observed_at": "2026-10-20", "stage": "参加意向", "value": 3, "unit": "件",
        "source": "サンプルデータ", "data_kind": "sample", "notes": "サンプル（実績ではない）",
    }, SEED_ACTOR)
    repository.add_reader_insight(conn, {
        "article_id": "SMP-005", "observed_at": "2026-10-10", "tags": ["経験", "新仮説"],
        "summary": "【サンプル】AIに渡した仕事のうち、例外処理が人に戻ってくるという経験談",
        "hypothesis_impact": "拡張", "derived_candidate": "例外処理を誰が持つかという権限設計の記事",
        "data_kind": "sample",
    }, SEED_ACTOR)


def seed_all(conn, include_samples=True):
    if is_seeded(conn):
        return False
    seed_real(conn)
    if include_samples:
        seed_samples(conn)
    conn.execute("INSERT INTO meta(key, value) VALUES ('seeded_at', ?)", (repository.now_iso(),))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('samples_included', ?)",
                 ("1" if include_samples else "0",))
    conn.commit()
    return True

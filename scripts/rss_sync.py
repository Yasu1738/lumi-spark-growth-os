"""noteの公式RSSから、記事のタイトル・URL・公開日時を取り込む。

オーナー承認（2026-10-24）に基づき、取得するのはRSS（https://note.com/lumispark/rss）のみ。
記事ページの読み取り・ログイン・非公式APIは使わない。

  python scripts/rss_sync.py --local --actor 西冨              パソコン版のDBへ反映
  python scripts/rss_sync.py --local --actor 西冨 --dry-run    反映内容の確認だけ
  python scripts/rss_sync.py --mobile-dir <記事JSONのフォルダ（versions.json を含む）> --out <出力フォルダ>
                                                               スマホ版へ書き込むためのファイルを作る
  --file <保存済みRSS.xml> を付けると、通信せずにそのファイルを使う
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lumi_growth_os import config, db, repository, rss  # noqa: E402


def fetch_feed(url=rss.FEED_URL) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "LumiSparkGrowthOS/1.0 (RSS reader)"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def mobile_writes(planned, out_dir: Path, actor: str):
    """スマホ版（claude.aiのページのデータベース）への書き込み内容をファイルにする。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    # スマホ版の記録は日本時間で表示しているため、作業環境の時刻（UTCの場合がある）ではなく日本時間にそろえる
    now = datetime.now(rss.JST).strftime("%Y-%m-%d %H:%M")
    writes = []
    for x in planned:
        if x["action"] == "update":
            data = {**x["changes"], "updated_at": now}
            op = "update"
        elif x["action"] == "new":
            data = {"id": x["id"], "title": x["title"], "title_status": "確認済み", "url": x["url"],
                    "url_status": "オーナー提示", "published_at": x["published_at"], "content_reviewed": False,
                    "data_kind": "real", "verification_status": "一部確認", "theme": None, "topic_tags": None,
                    "source": f"noteのRSS（{rss.FEED_URL}）", "notes": "RSSから登録。テーマ・タグは未設定。",
                    "created_at": now, "updated_at": now}
            op = "set"
        else:
            continue
        path = out_dir / f"{x['id']}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        entry = {"op": op, "collection": "articles", "doc_id": x["id"], "file_path": str(path)}
        if op == "update" and x.get("version"):
            entry["if_version"] = x["version"]  # 他の画面で同時に編集されていたら上書きしない
        writes.append(entry)
        audit = out_dir / f"audit-{x['id']}.json"
        audit.write_text(json.dumps({"at": now, "actor": actor, "action": "noteのRSSから" + ("更新" if op == "update" else "登録"),
                                     "entity": "article", "entity_id": x["id"], "before": x.get("before"),
                                     "after": data if op == "set" else x["changes"], "approver": None, "comment": None},
                                    ensure_ascii=False), encoding="utf-8")
        writes.append({"op": "set", "collection": "audit", "doc_id": f"rss-{now.replace(' ', 'T').replace(':', '')}-{x['id']}",
                       "file_path": str(audit)})
    (out_dir / "writes.json").write_text(json.dumps(writes, ensure_ascii=False, indent=1), encoding="utf-8")
    return writes


def main(argv=None):
    parser = argparse.ArgumentParser(description="noteのRSSから記事情報を取り込む")
    parser.add_argument("--actor", default="rss-sync")
    parser.add_argument("--file", help="保存済みのRSSファイル（指定すると通信しない）")
    parser.add_argument("--local", action="store_true", help="パソコン版のDBへ反映")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mobile-dir", help="スマホ版から書き出した記事JSONのフォルダ（articles/*.json）")
    parser.add_argument("--out", help="スマホ版への書き込みファイルの出力先")
    args = parser.parse_args(argv)

    xml_text = Path(args.file).read_text(encoding="utf-8") if args.file else fetch_feed()
    items = rss.parse_rss(xml_text)
    print(f"RSSの記事: {len(items)}件")

    if args.local:
        conn = db.connect(config.db_path())
        db.init_db(conn)
        planned = rss.plan(items, repository.list_articles(conn))
        if not args.dry_run:
            print(rss.apply_local(conn, planned, args.actor))
    elif args.mobile_dir:
        docs = []
        # versions.json: {記事ID: 版番号}。読み出し時の版番号を渡し、同時編集を上書きしないようにする
        versions_file = Path(args.mobile_dir) / "versions.json"
        known_versions = json.loads(versions_file.read_text(encoding="utf-8")) if versions_file.exists() else {}
        for path in sorted(Path(args.mobile_dir).rglob("*.json")):
            if path.name == "versions.json":
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            body = raw.get("data", raw)
            doc_id = body.get("id") or path.stem
            docs.append({**body, "id": doc_id, "version": raw.get("version") or known_versions.get(doc_id)})
        planned = rss.plan(items, docs)
        versions = {d["id"]: d.get("version") for d in docs}
        for x in planned:
            x["version"] = versions.get(x.get("id"))
        writes = mobile_writes(planned, Path(args.out), args.actor)
        print(f"書き込み: {len(writes)}件 → {Path(args.out) / 'writes.json'}")
    else:
        parser.error("--local か --mobile-dir を指定してください")

    for x in planned:
        mark = {"update": "更新", "new": "追加", "same": "変更なし", "skip": "読み取れず"}[x["action"]]
        print(f"[{mark}] {x.get('id', '-')}  {x['title']}  {x.get('changes', '')}")


if __name__ == "__main__":
    main()

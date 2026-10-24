import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import common  # noqa: E402
from lumi_growth_os import backup, config, importer, repository  # noqa: E402
from lumi_growth_os.validation import ValidationError  # noqa: E402

common.sidebar()
conn = common.get_conn()

st.title("取込・バックアップ・履歴")

tab_import, tab_backup, tab_export, tab_audit = st.tabs(["CSV・Excel取込", "バックアップと復旧", "書き出し", "操作履歴"])

with tab_import:
    st.markdown(
        "元ファイルは読み取りのみで、変更しません（取込前後のSHA-256で確認）。既存の記事IDは上書きしません。"
        "空欄は0ではなく未計測として取り込みます。\n\n"
        "対応形式：旧台帳『記事台帳』（38列）／『日次アカウント』／本システム形式（記事・実績・リンク）。"
        "Google Sheetsは「ファイル → ダウンロード → .xlsx / .csv」で保存したものを取り込んでください。"
    )
    uploaded = st.file_uploader("ファイルを選択", type=["csv", "xlsx", "xlsm"])
    if uploaded is not None:
        workdir = Path(tempfile.mkdtemp(prefix="lumi_import_"))
        temp_path = workdir / uploaded.name
        temp_path.write_bytes(uploaded.getvalue())
        sheet = None
        if temp_path.suffix.lower() in (".xlsx", ".xlsm"):
            sheets = importer.list_sheets(temp_path)
            sheet = st.selectbox("シート", sheets,
                                 index=sheets.index("記事台帳") if "記事台帳" in sheets else 0)
        as_sample = st.checkbox("記事をサンプル（実績ではない）として登録する",
                                help="タイトルが【サンプル】で始まる記事は自動でサンプル扱いになります")
        c1, c2 = st.columns(2)
        run_dry = c1.button("試し取込（DBは変更しない）")
        run_real = c2.button("取込を実行", type="primary")
        if run_dry or run_real:
            actor = common.actor_or_warn()
            if actor:
                try:
                    if run_real:
                        backup.create_backup(config.db_path(), config.backup_dir(), label="pre-import")
                    report = importer.import_file(conn, temp_path, actor, sheet=sheet, dry_run=run_dry,
                                                  display_name=uploaded.name, as_sample=as_sample)
                    st.write(f"判定形式：`{report['format']}`　読込行：{report['rows_read']}　"
                             f"登録：{report['inserted']}　実績：{report['metrics_inserted']}　"
                             f"スキップ：{len(report['skipped'])}　エラー：{len(report['errors'])}")
                    (st.success if report["source_unchanged"] else st.error)(
                        "元ファイルは変更されていません" if report["source_unchanged"] else "元ファイルのハッシュが変化しました")
                    if report["dry_run"]:
                        st.info("試し取込のため、DBは変更していません。")
                    for key, fn in (("errors", st.error), ("skipped", st.warning), ("warnings", st.info)):
                        for msg in report[key][:200]:
                            fn(msg)
                except ValidationError as exc:
                    st.error(str(exc))

with tab_backup:
    st.markdown("復旧の前には、現在のDBを自動で退避します（pre-restore）。")
    if st.button("今すぐバックアップ", type="primary"):
        path = backup.create_backup(config.db_path(), config.backup_dir(), label="manual")
        repository.log_action(conn, common.actor() or "unknown", "バックアップ作成", "backup", path.name)
        conn.commit()
        st.success(f"作成しました：{path}")
    items = backup.list_backups(config.backup_dir())
    st.dataframe([{"ファイル": i["path"].name, "作成日時": i.get("created_at"), "ラベル": i.get("label"),
                   "記事数": (i.get("counts") or {}).get("articles"),
                   "リンク提案数": (i.get("counts") or {}).get("link_proposals")} for i in items],
                 hide_index=True, width="stretch")
    if items:
        chosen = st.selectbox("復旧に使うバックアップ", [i["path"].name for i in items])
        problems = backup.verify_backup(config.backup_dir() / chosen)
        if problems:
            for p in problems:
                st.error(p)
        confirm = st.checkbox("現在のDBをこのバックアップの内容に置き換えることを理解しました")
        if st.button("復旧する", disabled=not confirm or bool(problems)):
            actor = common.actor_or_warn()
            if actor:
                pre = backup.restore_backup(config.backup_dir() / chosen, config.db_path(), config.backup_dir())
                repository.log_action(conn, actor, "バックアップから復旧", "backup", chosen,
                                      after={"pre_restore": pre.name if pre else None})
                conn.commit()
                st.success(f"復旧しました。復旧前の状態は {pre.name if pre else '（なし）'} に退避済みです。")

with tab_export:
    st.markdown("全テーブルを1つのExcelに書き出します（既存台帳とは別の新しいファイル）。")
    if st.button("Excelを作成"):
        out = Path(tempfile.mkdtemp(prefix="lumi_export_")) / f"lumi_export_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        backup.export_excel(conn, out)
        st.download_button("ダウンロード", out.read_bytes(), file_name=out.name,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_audit:
    logs = repository.list_audit(conn, limit=1000)
    st.dataframe([{"日時": l["at"], "担当者": l["actor"], "操作": l["action"], "対象": f"{l['entity_type']}:{l['entity_id']}",
                   "承認者": l["approver"], "コメント": l["comment"], "変更前": l["before_json"], "変更後": l["after_json"]}
                  for l in logs], hide_index=True, width="stretch")

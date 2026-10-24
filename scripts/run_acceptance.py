"""受入テストを実行し、docs/受入テスト結果.md を生成する。

  python scripts/run_acceptance.py
"""

import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CRITERIA = {
    1: "記事10件以上を管理できる",
    2: "3ハブを表示・編集できる",
    3: "関連記事リンク案を合計9件以上登録できる",
    4: "各リンク案の根拠・承認状態が記録できる",
    5: "note貼り付け用文章を生成できる",
    6: "Excel・CSVを非破壊で取り込める",
    7: "未確認URLを未確認として管理できる",
    8: "欠損値と0を区別できる",
    9: "計測日時付きの実績を保存できる",
    10: "Proxy指標が正しく計算される",
    11: "不正URL、重複リンク、自己リンクを検出できる",
    12: "バックアップから復旧できる",
    13: "APIキーなしで基本機能が動作する",
    14: "noteへの外部操作が発生しない",
}

# 自動テストでは確認できない範囲（未検証として明記する）
NOT_VERIFIED = {
    3: "9件はすべて仮案。URL・本文が未確認のため本番反映可能なリンクは0件。",
    6: "実物の『note記事運用台帳 Ver.0.1』をダウンロードした.xlsxでの取込は未実施（同じ38列ヘッダーで再現したファイルで検証）。"
       "『note記事学習台帳_Ver5.6_20260724.xlsx』は所在未確認のため未検証。",
    12: "利用者のPC（Windows/Mac）での復旧操作は未検証（Linuxで検証）。",
    14: "Streamlit本体の通信はconfig.tomlで利用統計を無効化し、localhostのみで待受。ブラウザが読み込む外部リソースの有無は未監査。",
}


def main():
    xml_path = ROOT / "tests" / ".acceptance.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml_path}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    tree = ET.parse(xml_path)
    xml_path.unlink()
    by_criterion = defaultdict(list)
    others = []
    for case in tree.iter("testcase"):
        name = case.get("name")
        failed = case.find("failure") is not None or case.find("error") is not None
        skipped = case.find("skipped") is not None
        status = "不合格" if failed else ("未検証" if skipped else "合格")
        if name.startswith("test_ac"):
            number = int(name[7:9])
            by_criterion[number].append((name, status))
        else:
            others.append((name, status))

    lines = [
        "# 受入テスト結果",
        "",
        f"- 実行日時: {datetime.now():%Y-%m-%d %H:%M}",
        f"- 実行環境: Python {sys.version.split()[0]} / {sys.platform}",
        "- 実行コマンド: `python scripts/run_acceptance.py`（内部で `pytest` を実行）",
        "",
        "判定は「合格（自動テストで確認）／不合格／未検証（テストなし、または自動テストの範囲外）」の3区分です。",
        "技術的な合格は、読者回遊の改善や収益化の成功を意味しません。",
        "",
        "| No | 受入条件 | 判定 | テスト数 | 補足（未検証の範囲） |",
        "|---|---|---|---|---|",
    ]
    for number, title in CRITERIA.items():
        cases = by_criterion.get(number, [])
        if not cases:
            verdict = "未検証"
        elif any(s == "不合格" for _, s in cases):
            verdict = "不合格"
        else:
            verdict = "合格"
        lines.append(f"| {number} | {title} | {verdict} | {len(cases)} | {NOT_VERIFIED.get(number, '')} |")
    lines += ["", "## テストケース一覧", ""]
    for number in CRITERIA:
        for name, status in by_criterion.get(number, []):
            lines.append(f"- [{status}] AC{number:02d} `{name}`")
    lines += ["", "## その他のテスト（画面描画・内部ロジック）", ""]
    lines += [f"- [{status}] `{name}`" for name, status in others]
    total = sum(len(v) for v in by_criterion.values()) + len(others)
    failed = sum(1 for v in list(by_criterion.values()) + [others] for _, s in v if s == "不合格")
    lines += ["", f"合計 {total} 件、不合格 {failed} 件。", "", "```", proc.stdout.strip().splitlines()[-1], "```", ""]
    out = ROOT / "docs" / "受入テスト結果.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    print(proc.stdout.strip().splitlines()[-1])
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())

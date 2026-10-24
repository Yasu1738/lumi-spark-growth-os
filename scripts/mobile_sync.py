"""スマホ版の毎日の自動更新（RSS取込・タグ推定の反映・関連記事の自動提案）の書き込み内容を作る。

  python scripts/mobile_sync.py --dump <スマホ版から読み出したフォルダ> --out <出力フォルダ> \
      [--estimates <推定JSON>] [--rss-file <保存済みRSS>] [--actor 名前]

<読み出したフォルダ> には articles/ links/ hubs/ と versions.json（{記事ID: 版番号}）を置く。
推定JSON は {記事ID: {"theme": "ORG", "topic_tags": "組織づくり,リーダーシップ"}}。
出力された batch_*.json を ArtifactData の batch でスマホ版に書き込む。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lumi_growth_os import mobile_sync, rss  # noqa: E402
from rss_sync import fetch_feed  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--estimates")
    parser.add_argument("--rss-file")
    parser.add_argument("--actor", default="毎日の自動更新")
    args = parser.parse_args(argv)

    xml_text = Path(args.rss_file).read_text(encoding="utf-8") if args.rss_file else fetch_feed()
    estimates = json.loads(Path(args.estimates).read_text(encoding="utf-8")) if args.estimates else {}
    now = datetime.now(rss.JST).strftime("%Y-%m-%d %H:%M")
    writes, summary = mobile_sync.build_plan(mobile_sync.load_dump(args.dump), rss.parse_rss(xml_text), estimates, now, args.actor)
    files = mobile_sync.write_batches(writes, args.out)
    print(json.dumps({"batches": [str(f) for f in files], **summary}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

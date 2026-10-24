"""Ver.6.1 代理指標（Proxy）と比較可能性の警告。

Proxy は厳密なクリック率・読了率・転換率ではない。
同じ計測条件の記事同士を比較するための運用指標として扱う。
"""

import statistics

from . import codes

PROXY_DEFINITIONS = {
    "imp_pv_proxy": ("IMP→PV Proxy", "pv", "imp"),
    "like_pv_proxy": ("スキ/PV Proxy", "likes", "pv"),
    "comment_pv_proxy": ("コメント/PV Proxy", "comments", "pv"),
}

PROXY_DISCLAIMER = (
    "Proxyは厳密なCTR・読了率・反応率ではありません。note上の各指標は同一母集団・"
    "同一計測条件とは限らないため、同条件の記事同士の比較にのみ使ってください。"
)


def proxy(numerator, denominator):
    """分子÷分母×100。どちらかが欠損、または分母が0なら None（計算不能）。"""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


def compute_proxies(row: dict) -> dict:
    return {key: proxy(row.get(num), row.get(den)) for key, (_, num, den) in PROXY_DEFINITIONS.items()}


def row_warnings(row: dict) -> list:
    warnings = []
    p = compute_proxies(row)
    if p["like_pv_proxy"] is not None and p["like_pv_proxy"] > 100:
        warnings.append("スキがPVを上回っています（PVとスキは同一母集団ではない可能性）")
    if p["imp_pv_proxy"] is not None and p["imp_pv_proxy"] > 100:
        warnings.append("PVがIMPを上回っています（計測条件を確認）")
    if row.get("window_type") == "cumulative":
        warnings.append(f"累積値（{row.get('measured_at')} 時点）。公開後経過時間が異なる記事とは比較不可")
    if row.get("data_kind") == "sample":
        warnings.append("サンプルデータ（実績ではない）")
    return warnings


def comparability_warnings(rows: list) -> list:
    """複数の計測値を並べて比較するときの警告。"""
    warnings = []
    if len(rows) < 2:
        return warnings
    windows = {r.get("window_type") for r in rows}
    if len(windows) > 1:
        warnings.append(f"計測区分が混在しています（{', '.join(sorted(map(str, windows)))}）。同じ区分同士で比較してください")
    if "cumulative" in windows:
        measured = {r.get("measured_at") for r in rows if r.get("window_type") == "cumulative"}
        hours = [r.get("hours_since_publish") for r in rows if r.get("window_type") == "cumulative"]
        if len(measured) > 1:
            warnings.append("累積値の計測日時が異なります。計測時点が違う累積値は比較できません")
        if any(h is None for h in hours) or (hours and max(hours) - min(hours) > 24):
            warnings.append("累積値は公開後の経過時間（母集団の期間）が記事ごとに異なります。人気順の比較は参考扱いにしてください")
    for window, (low, high) in codes.WINDOW_TOLERANCE_HOURS.items():
        hours = [r.get("hours_since_publish") for r in rows if r.get("window_type") == window]
        if len(hours) > 1 and None not in hours and max(hours) - min(hours) > 6:
            warnings.append(f"{window} 値の実際の経過時間に6時間超の差があります（{min(hours)}〜{max(hours)}時間）")
    kinds = {r.get("data_kind") for r in rows}
    if len(kinds) > 1:
        warnings.append("実データとサンプルデータが混在しています。サンプルは実績ではありません")
    sources = {r.get("source") for r in rows}
    if len(sources) > 1:
        warnings.append("出典（取得元の画面・資料）が異なる値を比較しています。計測条件をそろえてください")
    return warnings


def summarize_by_code(rows: list, code_field: str, value_field: str) -> list:
    """構造コード別の中央値。n が少ない場合は判定しない旨を付ける。"""
    groups = {}
    for row in rows:
        value = row.get(value_field)
        code_values = row.get(code_field)
        if value is None or not code_values:
            continue
        for code in str(code_values).split(","):
            groups.setdefault(code, []).append(value)
    result = []
    for code, values in sorted(groups.items()):
        n = len(values)
        result.append({
            "コード": code,
            "記事数(n)": n,
            "中央値": round(statistics.median(values), 2),
            "判定": "判定可（仮説として）" if n >= codes.MIN_ARTICLES_FOR_HYPOTHESIS
                    else f"データ不足（n<{codes.MIN_ARTICLES_FOR_HYPOTHESIS}）・判断しない",
        })
    return result


def hypothesis_status(rows: list) -> list:
    """Ver.6.1 初期仮説 H1〜H3 のデータ充足状況。因果判定は行わない。"""
    def count(predicate):
        return sum(1 for r in rows if predicate(r))

    has = lambda r, f: r.get(f) is not None  # noqa: E731
    h1_n = count(lambda r: r.get("specificity_code") and r.get("imp_pv_proxy") is not None)
    h2_n = count(lambda r: r.get("perspective_code") and r.get("like_pv_proxy") is not None)
    h3_n = count(lambda r: (r.get("title_structure") or r.get("human_code")) and has(r, "comments"))
    out = []
    for key, n in (("H1", h1_n), ("H2", h2_n), ("H3", h3_n)):
        enough = n >= codes.MIN_ARTICLES_FOR_HYPOTHESIS * 2
        out.append({
            "仮説": key,
            "内容": codes.INITIAL_HYPOTHESES[key],
            "比較可能な記事数": n,
            "状態": "比較材料あり（人間が判定）" if enough else "未判定（データ不足）",
        })
    return out

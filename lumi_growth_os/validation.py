"""入力値の検証と正規化。

- 欠損（空欄・None）は None のまま返し、0 に置き換えない。
- 「100+」のような非数値は推測で数値化せず、ValidationError にする。
- URLは形式だけを検証する。実在確認（アクセス）は行わない。
"""

import re
from datetime import date, datetime

from . import codes


class ValidationError(ValueError):
    pass


NOTE_ARTICLE_URL = re.compile(r"^https://note\.com/(?P<creator>[A-Za-z0-9_\-]+)/n/n[0-9a-f]{12}$")
OWN_CREATOR_ID = "lumispark"
ARTICLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,39}$")

_DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
]
_DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d"]


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    return isinstance(value, str) and value.strip() == ""


def clean_text(value):
    if is_blank(value):
        return None
    return str(value).strip()


def parse_count(value, field: str = "値"):
    """件数を int に正規化する。欠損は None。0 は 0 のまま。"""
    if is_blank(value):
        return None
    if isinstance(value, bool):
        raise ValidationError(f"{field}: 真偽値は件数として扱えません")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValidationError(f"{field}: 件数は整数で入力してください（{value}）")
        number = int(value)
    else:
        text = str(value).strip().replace(",", "")
        if not re.fullmatch(r"-?\d+(\.0+)?", text):
            raise ValidationError(
                f"{field}: 「{value}」は正確な数値ではありません。推定で数値化せず空欄にしてください"
            )
        number = int(float(text))
    if number < 0:
        raise ValidationError(f"{field}: 負の値は登録できません（{number}）")
    return number


def parse_datetime(value, field: str = "日時"):
    """日時を 'YYYY-MM-DD HH:MM' または日付のみ 'YYYY-MM-DD' に正規化する。"""
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValidationError(f"{field}: 日時の形式を解釈できません（{value}）")


def has_time(value) -> bool:
    return value is not None and len(value) > 10


def to_datetime(value):
    if value is None:
        return None
    if has_time(value):
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    return datetime.strptime(value, "%Y-%m-%d")


def validate_url(url):
    """URL形式を検証する。戻り値: (区分, 正規化URL, メッセージ)

    区分: 'empty' | 'note_article' | 'other_https' | 'invalid'
    """
    if is_blank(url):
        return "empty", None, "URLなし"
    text = str(url).strip()
    if any(ch.isspace() for ch in text):
        return "invalid", None, "URLに空白が含まれています"
    if not text.startswith("https://"):
        return "invalid", None, "https:// で始まるURLではありません"
    match = NOTE_ARTICLE_URL.match(text)
    if match:
        if match.group("creator") != OWN_CREATOR_ID:
            return "note_article", text, f"note記事URLですが作成者IDが {OWN_CREATOR_ID} ではありません（要確認）"
        return "note_article", text, "note記事URLの形式です（実在は未確認）"
    if text.startswith("https://note.com/"):
        return "invalid", None, "note.com のURLですが記事URLの形式（/ユーザー名/n/nXXXXXXXXXXXX）ではありません"
    if re.fullmatch(r"https://[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(/\S*)?", text):
        return "other_https", text, "note記事以外のURLです（要確認）"
    return "invalid", None, "URLの形式が不正です"


def check_code(value, allowed, field: str):
    value = clean_text(value)
    if value is None:
        return None
    if value not in allowed:
        raise ValidationError(f"{field}: 「{value}」は定義外のコードです（許可: {', '.join(allowed)}）")
    return value


def check_title_structure(value):
    """複数付与可（カンマ区切り）。"""
    value = clean_text(value)
    if value is None:
        return None
    parts = [p.strip().upper() for p in re.split(r"[,、\s]+", value) if p.strip()]
    for p in parts:
        if p not in codes.TITLE_STRUCTURES:
            raise ValidationError(f"タイトル構造: 「{p}」は定義外のコードです（T01〜T10）")
    return ",".join(dict.fromkeys(parts))


def split_tags(value):
    if is_blank(value):
        return []
    return [t.strip() for t in re.split(r"[,、]", str(value)) if t.strip()]


def check_article_id(value):
    value = clean_text(value)
    if value is None or not ARTICLE_ID_PATTERN.match(value):
        raise ValidationError(f"記事ID「{value}」は英数字・ハイフン・アンダースコアの1〜40文字で指定してください")
    return value

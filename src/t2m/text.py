"""Small text helpers."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str) -> str:
    """'Tìm kiếm thông minh!' -> 'tim-kiem-thong-minh' (đ becomes d)."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def words(text: str) -> list[str]:
    return text.split()

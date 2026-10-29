"""Automatic checks of a script before anything is rendered. Pure, except the optional item lookup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal

from . import templates
from .schema import CHANNELS, Script

Level = Literal["error", "warn"]

# The only refund sentence the owner confirmed (29/10/2026): registered and the class does not open -> refund.
REFUND_RE = re.compile(r"hoàn\s+(tiền|lại\s+tiền|phí)", re.IGNORECASE)
REFUND_OK_RE = re.compile(r"lớp\s+(học\s+)?(không|chưa)\s+(được\s+)?mở", re.IGNORECASE)
# "rẻ hơn" is promised only as "bằng hoặc rẻ hơn (giá) tại trường".
CHEAPER_RE = re.compile(r"rẻ\s+hơn", re.IGNORECASE)
CHEAPER_OK_RE = re.compile(r"bằng\s+hoặc\s+rẻ\s+hơn", re.IGNORECASE)
ABSOLUTES = ("rẻ nhất", "tốt nhất", "số 1", "duy nhất", "100%", "cam kết", "đảm bảo", "chắc chắn")
# Brand spellings: anything that reads like the word but is not written exactly so.
BRAND_RULES = (
    ("anyPoint", re.compile(r"\bany\s*-?\s*points?\b", re.IGNORECASE)),
    ("Leo Xu", re.compile(r"\bleo\s*-?\s*xu\b", re.IGNORECASE)),
    ("anyLEARN", re.compile(r"\bany\s*-?\s*learn\b", re.IGNORECASE)),
)
URL_RE = re.compile(r"(https?://\S+|\b[\w.-]+\.vn\S*|/\S+)")


@dataclass(frozen=True)
class Problem:
    level: Level
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]


def check_text(where: str, text: str) -> list[Problem]:
    out: list[Problem] = []
    plain = URL_RE.sub(" ", text)
    for correct, rule in BRAND_RULES:
        for m in rule.finditer(plain):
            if m.group(0) != correct:
                out.append(Problem("error", where, f'viết "{correct}", không viết "{m.group(0)}"'))
    if re.search(r"\d[\d.,]*\s*điểm\b(?!\s+(mới|nổi|danh|khác|chính|cần|hay))", plain, re.IGNORECASE):
        out.append(Problem("error", where, 'tiền thưởng viết "anyPoint", không viết "điểm"'))
    for sentence in _sentences(plain):
        if REFUND_RE.search(sentence) and not REFUND_OK_RE.search(sentence):
            out.append(Problem("error", where, f'chỉ được hứa hoàn tiền khi lớp không mở: "{sentence.strip()}"'))
        if CHEAPER_RE.search(sentence) and not CHEAPER_OK_RE.search(sentence):
            out.append(Problem("error", where, f'giá chỉ nói "bằng hoặc rẻ hơn tại trường": "{sentence.strip()}"'))
    low = plain.lower()
    for word in ABSOLUTES:
        if word in low:
            out.append(Problem("warn", where, f'câu tuyệt đối "{word}": kiểm tra có đúng và được phép nói không'))
    return out


def check_script(script: Script, seconds: int | None = None) -> list[Problem]:
    out: list[Problem] = []
    template = templates.get(script.template)
    lo, hi = templates.word_range(seconds or template.seconds)
    words = script.narration_words()
    if not lo <= words <= hi:
        out.append(Problem("error", "lời đọc", f"{words} chữ, cần {lo} đến {hi} cho {seconds or template.seconds}s"))
    if not script.scenes:
        out.append(Problem("error", "cảnh", "không có cảnh nào"))
    elif len(script.scenes[0].narration.split()) > 20:
        out.append(Problem("warn", f"cảnh {script.scenes[0].id}", "câu mở dài hơn 20 chữ, người xem lướt qua mất"))
    for scene in script.scenes:
        where = f"cảnh {scene.id}"
        if not scene.narration.strip():
            out.append(Problem("error", where, "chưa có lời đọc"))
        if scene.visual.kind not in template.visuals:
            out.append(Problem("error", where, f"template {template.key} không có hình kiểu {scene.visual.kind}"))
        if scene.visual.kind == "screen" and scene.visual.shot not in script.shots:
            out.append(Problem("error", where, f"shot '{scene.visual.shot}' không có trong brief"))
        if scene.visual.kind == "card" and not scene.visual.heading:
            out.append(Problem("warn", where, "card chưa có chữ to"))
        out += check_text(where, scene.narration)
        for text in (scene.on_screen, scene.visual.heading, scene.visual.sub):
            if text:
                out += check_text(where, text)
    out += check_text("câu mở", script.hook)
    out += check_text("lời kêu gọi", script.cta.text)
    if not script.cta.link.startswith("/"):
        out.append(Problem("error", "lời kêu gọi", "link phải là đường dẫn trên anylearn.vn, bắt đầu bằng /"))
    for channel in CHANNELS:
        caption = script.captions.get(channel, "")
        if not caption.strip():
            out.append(Problem("warn", f"caption {channel}", "chưa có"))
        else:
            out += check_text(f"caption {channel}", caption)
    return out


def check_items(script: Script, fetch: Callable[[int], dict | None]) -> list[Problem]:
    """Course names and prices in the script must match the API (`fetch(id)` -> the item, or None)."""
    out: list[Problem] = []
    for ref in script.items:
        live = fetch(ref.id)
        where = f"khóa {ref.id}"
        if not live:
            out.append(Problem("error", where, "không đọc được từ API (đã ẩn hoặc sai id)"))
            continue
        if (live.get("title") or "").strip() != ref.title.strip():
            out.append(Problem("error", where, f'tên trên site là "{live.get("title")}", kịch bản ghi "{ref.title}"'))
        if ref.price is not None and live.get("price") is not None and int(live["price"]) != ref.price:
            out.append(Problem("error", where, f"giá trên site là {int(live['price']):,}đ, kịch bản ghi {ref.price:,}đ"))
    return out


def has_errors(problems: list[Problem]) -> bool:
    return any(p.level == "error" for p in problems)

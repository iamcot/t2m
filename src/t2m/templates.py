"""Video templates: length, default voice and what the AI is told about the genre."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    key: str
    label: str
    seconds: int
    narrator_profile: str
    visuals: tuple[str, ...]
    guide: str


FEATURE_TOUR = Template(
    key="feature_tour",
    label="Giới thiệu tính năng",
    seconds=45,
    narrator_profile="ro_rang",
    visuals=("card", "screen"),
    guide="""Video quay màn hình điện thoại giới thiệu một tính năng của anyLEARN cho phụ huynh.
- Cảnh 1 (card, có Leo): câu mở là nỗi lo hoặc câu hỏi của phụ huynh, không nhắc tên tính năng ngay.
- Các cảnh giữa (screen): mỗi cảnh dùng một shot trong brief, theo đúng thứ tự thao tác; lời đọc nói phụ huynh được gì, không đọc tên nút.
- on_screen của cảnh screen: 2 đến 6 chữ, tóm điều đang thấy.
- Cảnh cuối (card): lời kêu gọi ngắn, nhắc link.
- Giọng: rõ ràng, thân thiện, xưng "bạn" hoặc "ba mẹ"; câu ngắn, dễ nghe.""",
)

TEMPLATES: dict[str, Template] = {t.key: t for t in (FEATURE_TOUR,)}


def get(key: str) -> Template:
    try:
        return TEMPLATES[key]
    except KeyError:
        raise KeyError(f"Không có template '{key}'. Có: {', '.join(TEMPLATES)}") from None


def word_range(seconds: int) -> tuple[int, int]:
    """140 to 170 words for 60 s of Vietnamese voice, scaled to the length."""
    return round(seconds * 140 / 60), round(seconds * 170 / 60)

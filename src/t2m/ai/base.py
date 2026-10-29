"""Shared part of the AI writers: the prompt, validation and one retry with the errors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from .. import checks, templates
from ..schema import AiScript, Brief, Script
from ..store import Store

SYSTEM = """Bạn viết kịch bản video ngắn dọc (9:16) cho anyLEARN, nền tảng tìm và đăng ký lớp học cho trẻ em ở Việt Nam.
Người xem là phụ huynh 25 đến 45 tuổi, lướt nhanh trên Facebook, TikTok, YouTube Shorts.

Quy tắc bắt buộc:
- Tiếng Việt tự nhiên, câu ngắn, đọc thành tiếng nghe rõ. Viết số bằng chữ số khi là giá, tuổi, giờ.
- Viết đúng: "anyLEARN", "anyPoint" (không viết "điểm" cho anyPoint), "Leo" (linh vật), "Leo Xu" (tiền trong game).
- Lời hứa chỉ được nói đúng như sau: giá bằng hoặc rẻ hơn tại trường; đăng ký mà lớp không mở thì được hoàn tiền; mọi lịch học một nơi; hỗ trợ qua Zalo. Không hứa gì thêm, không nói "rẻ nhất", "tốt nhất", "cam kết", "100%".
- So sánh khóa học chỉ nói "đặt cạnh nhau bằng số liệu, AI đọc mô tả giúp", không nói AI chọn khóa tốt nhất.
- Không bịa tên khóa, giá, số liệu. Chỉ nhắc khóa có trong brief, đúng tên và giá.
- Captions: facebook (mở bằng nỗi lo của phụ huynh, 2 đến 4 câu, có link), tiktok và youtube (1 đến 2 câu), zalo (1 câu thân mật), explore (1 câu cho Khám phá trong app). Viết link dạng anylearn.vn{link}.
"""


class ScriptWriter(Protocol):
    mode: str

    def ask(self, system: str, prompt: str, schema: dict) -> tuple[dict, "Usage"]: ...


@dataclass
class Usage:
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def build_prompt(brief: Brief) -> str:
    template = templates.get(brief.template)
    seconds = brief.seconds or template.seconds
    lo, hi = templates.word_range(seconds)
    parts = [
        f"Template: {template.label} ({template.key}), dài khoảng {seconds} giây.",
        template.guide,
        f"Tổng lời đọc của mọi cảnh: {lo} đến {hi} chữ (đếm theo khoảng trắng).",
        f"Chủ đề: {brief.topic}",
    ]
    if brief.angle:
        parts.append(f"Góc nói: {brief.angle}")
    parts.append(f"Link cuối video (cta.link): {brief.link}")
    if brief.notes:
        parts.append(f"Ghi chú của người làm: {brief.notes}")
    if brief.shots:
        parts.append("Các shot quay màn hình có sẵn (cảnh screen dùng visual.shot = id, mỗi shot dùng tối đa 1 lần):")
        parts += [f"- {sid}: {shot.description}" for sid, shot in brief.shots.items()]
    if brief.voices:
        parts.append("Nhân vật có giọng riêng (scene.voice): " + ", ".join(brief.voices))
    if brief.items:
        parts.append("Khóa học được nhắc (đúng tên, đúng giá):")
        parts += [f"- {i.title}" + (f", {i.price:,}đ".replace(",", ".") if i.price else "") for i in brief.items]
    return "\n\n".join(parts)


def _parse(raw: dict, brief: Brief) -> Script:
    return AiScript.model_validate(raw).to_script(brief)


def write_script(writer: ScriptWriter, brief: Brief, store: Store | None = None, job_id: str | None = None,
                 retries: int = 1) -> tuple[Script, list[checks.Problem]]:
    """Asks for a script; on invalid JSON or check errors asks once more with the list of problems."""
    schema = AiScript.model_json_schema()
    prompt = build_prompt(brief)
    last_error = ""
    for attempt in range(retries + 1):
        ask = prompt if not last_error else f"{prompt}\n\nBản trước có lỗi, sửa hết rồi viết lại toàn bộ:\n{last_error}"
        try:
            raw, usage = writer.ask(SYSTEM, ask, schema)
        except Exception as e:  # noqa: BLE001 - logged, then raised
            if store:
                store.record_ai(job_id, "script", writer.mode, None, None, None, None, False, str(e))
            raise
        if store:
            store.record_ai(job_id, "script", writer.mode, usage.model, usage.input_tokens, usage.output_tokens,
                            usage.cost_usd, True)
        try:
            script = _parse(raw, brief)
        except ValidationError as e:
            last_error = str(e)
            continue
        problems = checks.check_script(script, brief.seconds)
        if not checks.has_errors(problems) or attempt == retries:
            return script, problems
        last_error = "\n".join(str(p) for p in problems if p.level == "error")
    raise RuntimeError(f"AI trả về kịch bản không hợp lệ:\n{last_error}")


def extract_json(text: str) -> dict:
    """The JSON object inside a free text answer (a ```json block, else the outermost braces)."""
    if "```" in text:
        for block in text.split("```")[1::2]:
            block = block.removeprefix("json").strip()
            if block.startswith("{"):
                return json.loads(block)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("không thấy JSON trong câu trả lời")
    return json.loads(text[start:end + 1])

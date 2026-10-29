"""`--ai claude-code`: runs `claude -p` (the Claude plan already on the Mac) and reads the JSON in its answer."""

from __future__ import annotations

import json
import subprocess

from ..settings import Settings
from .base import Usage, extract_json


class ClaudeCodeWriter:
    mode = "claude-code"

    def __init__(self, settings: Settings, run=subprocess.run):
        self.bin = settings.claude_bin
        self.run = run

    def ask(self, system: str, prompt: str, schema: dict) -> tuple[dict, Usage]:
        full = (f"{system}\n\n{prompt}\n\nChỉ trả lời bằng một object JSON đúng schema sau, không thêm chữ nào khác, "
                f"không dùng công cụ:\n{json.dumps(schema, ensure_ascii=False)}")
        proc = self.run([self.bin, "-p", "--output-format", "json"], input=full, capture_output=True, text=True,
                        timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p lỗi ({proc.returncode}): {proc.stderr.strip()[:300]}")
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude -p báo lỗi: {str(envelope.get('result'))[:300]}")
        usage = envelope.get("usage") or {}
        model = next(iter(envelope.get("modelUsage") or {}), None)
        return extract_json(envelope.get("result") or ""), Usage(
            model,
            (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0),
            usage.get("output_tokens"),
            envelope.get("total_cost_usd"),
        )

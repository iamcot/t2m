"""`--ai api`: Anthropic API with a forced tool call, so the answer is always JSON of the schema."""

from __future__ import annotations

from ..settings import Settings
from .base import Usage


class ApiWriter:
    mode = "api"

    def __init__(self, settings: Settings, client=None):
        if client is None:
            if not settings.anthropic_api_key:
                raise RuntimeError("Thiếu ANTHROPIC_API_KEY (hoặc dùng --ai claude-code)")
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.client = client
        self.model = settings.ai_model

    def ask(self, system: str, prompt: str, schema: dict) -> tuple[dict, Usage]:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[{"name": "write_script", "description": "Ghi kịch bản video", "input_schema": schema}],
            tool_choice={"type": "tool", "name": "write_script"},
        )
        block = next(b for b in msg.content if getattr(b, "type", "") == "tool_use")
        return dict(block.input), Usage(self.model, msg.usage.input_tokens, msg.usage.output_tokens)

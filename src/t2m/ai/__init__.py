"""The AI step: write a script from a brief, through the Anthropic API or Claude Code (`claude -p`)."""

from __future__ import annotations

from ..schema import Brief, Script
from ..settings import Settings
from ..store import Store
from .base import ScriptWriter, write_script


def writer(mode: str, settings: Settings) -> ScriptWriter:
    if mode == "api":
        from .api import ApiWriter
        return ApiWriter(settings)
    if mode == "claude-code":
        from .claude_code import ClaudeCodeWriter
        return ClaudeCodeWriter(settings)
    raise ValueError(f"--ai phải là api hoặc claude-code, không phải '{mode}'")


__all__ = ["Brief", "Script", "Store", "ScriptWriter", "writer", "write_script"]

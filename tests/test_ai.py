import json
from types import SimpleNamespace

import pytest

from t2m.ai.api import ApiWriter
from t2m.ai.base import SYSTEM, Usage, build_prompt, extract_json, write_script
from t2m.ai.claude_code import ClaudeCodeWriter
from t2m.settings import Settings
from t2m.store import Store


class FakeWriter:
    mode = "fake"

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def ask(self, system, prompt, schema):
        self.prompts.append(prompt)
        return self.answers.pop(0), Usage("m", 10, 20)


def test_prompt_lists_shots_and_word_range(brief):
    prompt = build_prompt(brief)
    assert "105 đến 128 chữ" in prompt
    assert "- loc-tuoi: Chạm chip tên bé" in prompt
    assert "Link cuối video (cta.link): /search" in prompt
    assert "anyPoint" in SYSTEM and "lớp không mở" in SYSTEM


def test_write_script_retries_with_problems(brief, ai_raw, tmp_path):
    bad = json.loads(json.dumps(ai_raw))
    bad["scenes"][1]["narration"] += " Rẻ hơn ở trường."
    writer = FakeWriter([bad, ai_raw])
    store = Store(tmp_path / "t.db", tmp_path / "jobs")
    script, problems = write_script(writer, brief, store, "job1")
    assert problems == []
    assert "Bản trước có lỗi" in writer.prompts[1] and "rẻ hơn" in writer.prompts[1]
    assert script.shots.keys() == brief.shots.keys()  # copied from the brief, not written by the AI
    rows = store.db.execute("SELECT COUNT(*), SUM(output_tokens) FROM ai_usage WHERE job_id='job1'").fetchone()
    assert tuple(rows) == (2, 40)


def test_write_script_invalid_json_twice_fails(brief):
    with pytest.raises(RuntimeError):
        write_script(FakeWriter([{"title": "x"}, {"title": "y"}]), brief)


def test_extract_json():
    assert extract_json('Đây:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('ok {"a": {"b": 2}} xong') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        extract_json("không có")


def test_claude_code_writer_reads_envelope(ai_raw):
    calls = []

    def run(args, **kw):
        calls.append((args, kw))
        out = {"type": "result", "is_error": False, "result": "```json\n" + json.dumps(ai_raw) + "\n```",
               "total_cost_usd": 0.05, "usage": {"input_tokens": 100, "cache_read_input_tokens": 50, "output_tokens": 900},
               "modelUsage": {"claude-x": {}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out), stderr="")

    raw, usage = ClaudeCodeWriter(Settings(), run=run).ask("sys", "prompt", {"type": "object"})
    assert raw["title"] == ai_raw["title"]
    assert usage == Usage("claude-x", 150, 900, 0.05)
    assert calls[0][0] == ["claude", "-p", "--output-format", "json"]
    assert "prompt" in calls[0][1]["input"]


def test_api_writer_forces_tool(ai_raw):
    seen = {}

    class Messages:
        def create(self, **kw):
            seen.update(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=ai_raw)],
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=2))

    raw, usage = ApiWriter(Settings(), client=SimpleNamespace(messages=Messages())).ask("s", "p", {"type": "object"})
    assert raw == ai_raw and usage.output_tokens == 2
    assert seen["tool_choice"] == {"type": "tool", "name": "write_script"}

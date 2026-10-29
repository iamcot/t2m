import json
from pathlib import Path

import pytest

from t2m.schema import AiScript, Brief

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def brief() -> Brief:
    return Brief.load(ROOT / "briefs" / "2026-11-04-tim-kiem.toml")


@pytest.fixture
def ai_raw() -> dict:
    return json.loads((ROOT / "examples" / "tim-kiem.script.json").read_text(encoding="utf-8"))


@pytest.fixture
def script(brief, ai_raw):
    return AiScript.model_validate(ai_raw).to_script(brief)

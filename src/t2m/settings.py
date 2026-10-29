"""Settings: `t2m.toml` (copy `t2m.example.toml`) with secrets from the environment."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
REPO_DIR = PACKAGE_DIR.parent.parent


@dataclass
class Settings:
    site_url: str = "https://anylearn.vn"
    api_url: str = ""  # default: site_url + /v2/api
    jobs_dir: Path = Path("jobs")
    db_path: Path = Path("t2m.db")
    voices_file: Path = REPO_DIR / "config" / "voices.toml"
    music_dir: Path = REPO_DIR / "assets" / "music"
    ai_mode: str = "claude-code"  # api | claude-code
    ai_model: str = "claude-sonnet-5-5"
    claude_bin: str = "claude"
    encoder: str = "auto"  # auto | h264_videotoolbox | libx264
    music_volume: float = 0.18
    chromium_path: str = ""  # empty = the browser of `playwright install chromium`
    # Accounts: phone in the toml, passwords only in the environment.
    demo_phone: str = ""
    studio_phone: str = ""
    anthropic_api_key: str = field(default="", repr=False)
    demo_password: str = field(default="", repr=False)
    studio_password: str = field(default="", repr=False)

    @property
    def api(self) -> str:
        return (self.api_url or self.site_url.rstrip("/") + "/v2/api").rstrip("/")


def load(path: Path | None = None) -> Settings:
    path = path or Path(os.environ.get("T2M_CONFIG", "t2m.toml"))
    data: dict = {}
    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    s = Settings()
    for key, value in data.items():
        if not hasattr(s, key) or key.endswith("password") or key == "anthropic_api_key":
            continue
        current = getattr(s, key)
        setattr(s, key, Path(value) if isinstance(current, Path) else value)
    s.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    s.demo_password = os.environ.get("T2M_DEMO_PASSWORD", "")
    s.studio_password = os.environ.get("T2M_STUDIO_PASSWORD", "")
    s.demo_phone = os.environ.get("T2M_DEMO_PHONE", s.demo_phone)
    s.studio_phone = os.environ.get("T2M_STUDIO_PHONE", s.studio_phone)
    s.chromium_path = os.environ.get("T2M_CHROMIUM", s.chromium_path)
    return s

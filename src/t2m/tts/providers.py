"""Providers. `say` = macOS voices (free, on the Mac), `fpt` = FPT.AI, `silent` = timing only (tests, drafts)."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx

from .. import media
from .base import VoiceProfile


class SayProvider:
    """macOS `say`. Vietnamese voice: Linh (install in System Settings > Accessibility > Spoken Content)."""

    name = "say"

    def synthesize(self, text: str, profile: VoiceProfile, out: Path) -> Path:
        out = out.with_suffix(".aiff")
        args = ["say", "-o", str(out)]
        if profile.voice:
            args += ["-v", profile.voice]
        if rate := profile.options.get("rate"):
            args += ["-r", str(rate)]
        subprocess.run([*args, text], check=True)
        return out


class SilentProvider:
    """Silence as long as the text would take to read (`wps` words per second). For tests and timing drafts."""

    name = "silent"

    def synthesize(self, text: str, profile: VoiceProfile, out: Path) -> Path:
        out = out.with_suffix(".wav")
        seconds = max(0.6, len(text.split()) / float(profile.options.get("wps", 2.6)))
        media.run(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}", str(out)])
        return out


class FptProvider:
    """FPT.AI TTS v5 (key `FPT_TTS_API_KEY`). Voices: banmai, thuminh, leminh, myan, lannhi, linhsan, minhquang..."""

    name = "fpt"
    URL = "https://api.fpt.ai/hmi/tts/v5"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None, poll_seconds: float = 2.0):
        self.client = client or httpx.Client(timeout=60)
        self.api_key = api_key if api_key is not None else os.environ.get("FPT_TTS_API_KEY", "")
        self.poll_seconds = poll_seconds

    def synthesize(self, text: str, profile: VoiceProfile, out: Path) -> Path:
        if not self.api_key:
            raise RuntimeError("Thiếu FPT_TTS_API_KEY")
        headers = {"api-key": self.api_key, "voice": profile.voice or "banmai",
                   "speed": str(profile.options.get("speed", "")), "format": "mp3"}
        res = self.client.post(self.URL, content=text.encode("utf-8"), headers=headers)
        res.raise_for_status()
        body = res.json()
        if body.get("error") not in (0, None) or not body.get("async"):
            raise RuntimeError(f"FPT.AI lỗi: {body.get('message')}")
        out = out.with_suffix(".mp3")
        # The file is ready a few seconds later at the async link.
        for _ in range(30):
            got = self.client.get(body["async"])
            if got.status_code == 200 and got.content:
                out.write_bytes(got.content)
                return out
            time.sleep(self.poll_seconds)
        raise RuntimeError("FPT.AI chưa trả file sau 60 giây")


PROVIDERS = {"say": SayProvider, "silent": SilentProvider, "fpt": FptProvider}


def provider(name: str):
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise KeyError(f"Không có nhà TTS '{name}'. Có: {', '.join(PROVIDERS)}") from None

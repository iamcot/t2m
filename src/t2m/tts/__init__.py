"""Voices: profiles from `config/voices.toml`, one per genre, plus voices per character."""

from __future__ import annotations

import tomllib
from pathlib import Path

from .. import media, templates
from ..schema import Script
from .base import Speech, TtsProvider, VoiceProfile, WordTime
from .providers import provider


def load_profiles(path: Path) -> dict[str, VoiceProfile]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out = {}
    for key, p in data.get("profiles", {}).items():
        p = dict(p)
        out[key] = VoiceProfile(key=key, label=p.pop("label", key), provider=p.pop("provider"), voice=p.pop("voice", ""),
                                speed=float(p.pop("speed", 1.0)), pitch=float(p.pop("pitch", 0.0)), options=p)
    return out


def profile_key(script: Script, character: str) -> str:
    """Brief's voice for the character, else the template's narrator voice."""
    if character in script.voices:
        return script.voices[character]
    return templates.get(script.template).narrator_profile


def post_filter(profile: VoiceProfile) -> str:
    """ffmpeg filter for the profile's pitch (semitones) and speed, same for every provider."""
    parts = []
    if profile.pitch:
        ratio = 2 ** (profile.pitch / 12)
        parts += [f"asetrate={48000 * ratio:.0f}", "aresample=48000", f"atempo={1 / ratio:.5f}"]
    if profile.speed != 1.0:
        parts.append(f"atempo={profile.speed:.4f}")
    return ",".join(parts) or "anull"


def speak(text: str, profile: VoiceProfile, out: Path, tts: TtsProvider | None = None) -> Speech:
    """Synthesizes `text` into `out` (.wav, 48 kHz mono) with the profile's pitch and speed."""
    tts = tts or provider(profile.provider)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = tts.synthesize(text, profile, out.with_name(out.stem + "-raw"))
    wav = out.with_suffix(".wav")
    media.run(["-i", str(raw), "-af", f"aresample=48000,{post_filter(profile)}", "-ac", "1", "-ar", "48000", str(wav)])
    raw.unlink(missing_ok=True)
    return Speech(wav, media.duration(wav))


__all__ = ["Speech", "TtsProvider", "VoiceProfile", "WordTime", "load_profiles", "profile_key", "speak", "provider"]

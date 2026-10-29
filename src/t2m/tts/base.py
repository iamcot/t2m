"""Text to speech: one interface, providers can be swapped without touching the rest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class WordTime:
    word: str
    start: float
    end: float


@dataclass
class Speech:
    path: Path  # 48 kHz mono wav
    duration: float
    words: list[WordTime] | None = None  # when the provider gives word timings


@dataclass(frozen=True)
class VoiceProfile:
    key: str
    label: str
    provider: str
    voice: str = ""
    speed: float = 1.0  # applied after synthesis (atempo), same for every provider
    pitch: float = 0.0  # semitones, applied after synthesis
    options: dict = field(default_factory=dict)  # passed to the provider as is


class TtsProvider(Protocol):
    name: str

    def synthesize(self, text: str, profile: VoiceProfile, out: Path) -> Path:
        """Writes the raw voice to `out` (any format ffmpeg reads) and returns the written path."""
        ...

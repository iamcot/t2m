"""Word timings for the karaoke subtitles: the TTS's own, Whisper on the Mac, else spread by word length."""

from __future__ import annotations

from pathlib import Path

from .tts.base import WordTime


def proportional(text: str, start: float, end: float) -> list[WordTime]:
    """Spreads the words over [start, end] by their length (a long word takes longer to say)."""
    words = text.split()
    if not words:
        return []
    weights = [len(w) + 2 for w in words]
    total, t, out = sum(weights), start, []
    for w, weight in zip(words, weights):
        d = (end - start) * weight / total
        out.append(WordTime(w, round(t, 3), round(t + d, 3)))
        t += d
    return out


def fit(text: str, heard: list[WordTime], duration: float) -> list[WordTime]:
    """Script words with the heard timings: one to one when the counts match, else spread over the heard span."""
    words = text.split()
    if heard and len(heard) == len(words):
        return [WordTime(w, h.start, h.end) for w, h in zip(words, heard)]
    if heard:
        return proportional(text, heard[0].start, heard[-1].end)
    return proportional(text, min(0.05, duration), max(0.05, duration - 0.1))


def whisper_words(path: Path) -> list[WordTime] | None:
    """Word timings from mlx-whisper (Apple Silicon, `pip install t2m[whisper]`); None when not installed."""
    try:
        import mlx_whisper  # type: ignore
    except ImportError:
        return None
    result = mlx_whisper.transcribe(str(path), language="vi", word_timestamps=True)
    return [WordTime(w["word"].strip(), float(w["start"]), float(w["end"]))
            for seg in result.get("segments", []) for w in seg.get("words", [])]

"""The whole render of a job: voices, recordings, scene pictures, clips, subtitles, final video, poster."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import align, layout, media, subtitles
from ..schema import Script
from ..settings import ASSETS_DIR, Settings
from ..tts import VoiceProfile, WordTime, profile_key, speak
from ..tts.base import TtsProvider
from . import ffmpeg
from .html import Painter, browser

FONTS_DIR = ASSETS_DIR / "fonts"
RecordFn = Callable[[dict, Path], dict[str, Path]]  # (shots, out dir) -> {shot id: mp4}


@dataclass
class Voiced:
    path: Path
    seconds: float
    words: list[WordTime]  # relative to the start of the voice


@dataclass
class RenderResult:
    video: Path
    poster: Path
    seconds: float
    scenes: list[tuple[str, float]]


def _key(*parts: object) -> str:
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


def voice_scenes(script: Script, profiles: dict[str, VoiceProfile], audio_dir: Path,
                 tts: TtsProvider | None = None, use_whisper: bool = True) -> dict[str, Voiced]:
    """One wav per scene. A wav is kept while its text and voice profile do not change (`*.key` next to it)."""
    out = {}
    for scene in script.scenes:
        key = profile_key(script, scene.voice)
        if key not in profiles:
            raise KeyError(f"Cảnh {scene.id}: không có hồ sơ giọng '{key}' trong config/voices.toml")
        profile = profiles[key]
        wav = audio_dir / f"{scene.id}.wav"
        stamp = audio_dir / f"{scene.id}.key"
        cache = _key(scene.narration, profile, tts.name if tts else None)
        if not (wav.exists() and stamp.exists() and stamp.read_text() == cache):
            speak(scene.narration, profile, wav, tts)
            stamp.write_text(cache)
        seconds = media.duration(wav)
        heard = align.whisper_words(wav) if use_whisper else None
        out[scene.id] = Voiced(wav, seconds, align.fit(scene.narration, heard or [], seconds))
    return out


def pick_music(music_dir: Path, seed: str) -> Path | None:
    tracks = sorted(p for p in music_dir.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac"))
    return random.Random(seed).choice(tracks) if tracks else None


def render(job_dir: Path, script: Script, settings: Settings, profiles: dict[str, VoiceProfile],
           record: RecordFn | None = None, tts: TtsProvider | None = None, use_whisper: bool = True,
           music: Path | None | bool = True) -> RenderResult:
    audio_dir, frames_dir, clips_dir, rec_dir = (job_dir / d for d in ("audio", "frames", "clips", "recordings"))
    for d in (audio_dir, frames_dir, clips_dir, rec_dir):
        d.mkdir(parents=True, exist_ok=True)

    voiced = voice_scenes(script, profiles, audio_dir, tts, use_whisper)
    seconds = [ffmpeg.scene_seconds(voiced[s.id].seconds, s.min_seconds) for s in script.scenes]

    needed = {s.visual.shot for s in script.scenes if s.visual.kind == "screen"}
    missing = {sid: script.shots[sid] for sid in needed if not (rec_dir / f"{sid}.mp4").exists()}
    if missing:
        if record is None:
            raise RuntimeError(f"Chưa quay các shot: {', '.join(sorted(missing))} (chạy t2m record)")
        record(missing, rec_dir)

    parts: list[ffmpeg.Part] = []
    with browser(settings.chromium_path) as b:
        painter = Painter(b, frames_dir)
        bezel = painter.bezel(frames_dir / "bezel.png")
        for i, scene in enumerate(script.scenes):
            v = scene.visual
            clip = clips_dir / f"{i:02d}-{scene.id}.mp4"
            length = seconds[i] + (ffmpeg.FADE if i < len(script.scenes) - 1 else 0)
            if v.kind == "card":
                heading = v.heading or (script.hook if i == 0 else None)
                png = painter.card(frames_dir / f"{i:02d}-{scene.id}.png", heading, v.sub, v.leo)
                media.run(ffmpeg.card_clip(png, length, clip))
            else:
                bg = painter.screen_background(frames_dir / f"{i:02d}-{scene.id}.png", scene.on_screen)
                rec = rec_dir / f"{v.shot}.mp4"
                media.run(ffmpeg.screen_clip(bg, rec, bezel, media.duration(rec), length, clip))
            parts.append(ffmpeg.Part(clip, voiced[scene.id].path, seconds[i]))
        poster_png = painter.card(frames_dir / "poster.png", script.hook, None, True)

    starts = ffmpeg.starts(parts)
    words = [WordTime(w.word, round(w.start + t + ffmpeg.LEAD, 3), round(w.end + t + ffmpeg.LEAD, 3))
             for scene, t in zip(script.scenes, starts) for w in voiced[scene.id].words]
    ass = job_dir / "subtitles.ass"
    ass.write_text(subtitles.build_ass(words, style=subtitles.SubStyle(margin_v=layout.SUB_MARGIN_V)), encoding="utf-8")
    (job_dir / "subtitles.srt").write_text(subtitles.build_srt(words), encoding="utf-8")

    track = pick_music(settings.music_dir, job_dir.name) if music is True else (music or None)
    video = job_dir / "final.mp4"
    media.run(ffmpeg.final(parts, ass, FONTS_DIR, video, media.video_codec_args(settings.encoder), track,
                           settings.music_volume))
    poster = job_dir / "poster.jpg"
    media.run(ffmpeg.poster(poster_png, poster))

    carousel = job_dir / "carousel"
    shutil.rmtree(carousel, ignore_errors=True)
    shots = [s.visual.shot for s in script.scenes if s.visual.kind == "screen"]
    if shots:
        carousel.mkdir()
        for n, sid in enumerate(dict.fromkeys(shots), 1):
            if (rec_dir / f"{sid}.png").exists():
                shutil.copy(rec_dir / f"{sid}.png", carousel / f"{n:02d}-{sid}.png")
    return RenderResult(video, poster, media.duration(video), [(s.id, d) for s, d in zip(script.scenes, seconds)])

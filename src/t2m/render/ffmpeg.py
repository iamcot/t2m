"""ffmpeg arguments for scene clips and the final video. Pure: they return argument lists, `media.run` runs them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import layout

FADE = 0.3  # cross fade between scenes
LEAD = 0.25  # the voice starts this long after its scene starts
TAIL = 0.45  # quiet time after the voice before the next scene


def scene_seconds(speech: float, min_seconds: float) -> float:
    return round(max(min_seconds, LEAD + speech + TAIL), 3)


def card_clip(png: Path, seconds: float, out: Path) -> list[str]:
    """A still card with a slow push in (zoompan on a 2x image, so the motion is smooth)."""
    frames = round(seconds * layout.FPS)
    vf = (f"scale={layout.W * 2}:{layout.H * 2},"
          f"zoompan=z='min(1+0.0005*on,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
          f"s={layout.W}x{layout.H}:fps={layout.FPS},format=yuv420p")
    return ["-loop", "1", "-framerate", str(layout.FPS), "-i", str(png), "-vf", vf, "-frames:v", str(frames),
            "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(out)]


def fit_recording(rec_seconds: float, seconds: float) -> str:
    """Fits a recording into the scene: speeds up a little, else cuts; a short one holds its last frame."""
    if rec_seconds > seconds:
        ratio = seconds / rec_seconds
        return f"setpts={ratio:.4f}*PTS" if ratio >= 0.65 else f"trim=duration={seconds:.3f},setpts=PTS-STARTPTS"
    return f"tpad=stop_mode=clone:stop_duration={seconds - rec_seconds + 0.2:.3f}"


def screen_clip(background: Path, recording: Path, bezel: Path, rec_seconds: float, seconds: float,
                out: Path) -> list[str]:
    s = layout.SCREEN
    frames = round(seconds * layout.FPS)
    graph = (f"[1:v]{fit_recording(rec_seconds, seconds)},scale={s.w}:{s.h},fps={layout.FPS}[rec];"
             f"[0:v][rec]overlay={s.x}:{s.y}:shortest=0[a];[a][2:v]overlay=0:0,format=yuv420p[v]")
    return ["-loop", "1", "-framerate", str(layout.FPS), "-i", str(background), "-i", str(recording),
            "-loop", "1", "-framerate", str(layout.FPS), "-i", str(bezel), "-filter_complex", graph, "-map", "[v]",
            "-frames:v", str(frames), "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(out)]


@dataclass(frozen=True)
class Part:
    clip: Path
    voice: Path
    seconds: float  # scene length D (without the fade overlap)


def starts(parts: list[Part]) -> list[float]:
    """Scene k starts at the sum of the earlier scene lengths (each clip is rendered FADE longer to overlap)."""
    out, t = [], 0.0
    for p in parts:
        out.append(round(t, 3))
        t += p.seconds
    return out


def clip_seconds(parts: list[Part], i: int) -> float:
    return parts[i].seconds + (FADE if i < len(parts) - 1 else 0)


def final(parts: list[Part], ass: Path, fonts_dir: Path, out: Path, codec: list[str], music: Path | None = None,
          music_volume: float = 0.18) -> list[str]:
    """Scenes with cross fades, voices at their scene start, music ducked under the voice, loudness for social."""
    n = len(parts)
    at = starts(parts)
    total = round(sum(p.seconds for p in parts), 3)
    args: list[str] = []
    for p in parts:
        args += ["-i", str(p.clip)]
    for p in parts:
        args += ["-i", str(p.voice)]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
    g: list[str] = []
    last = "[0:v]"
    for k in range(1, n):
        label = f"[x{k}]"
        g.append(f"{last}[{k}:v]xfade=transition=fade:duration={FADE}:offset={at[k]:.3f}{label}")
        last = label
    sub = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fonts = str(fonts_dir).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    g.append(f"{last}ass='{sub}':fontsdir='{fonts}',format=yuv420p[v]")
    for i in range(n):
        delay = round((at[i] + LEAD) * 1000)
        g.append(f"[{n + i}:a]aresample=48000,adelay={delay}:all=1[a{i}]")
    g.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,"
             f"apad=whole_dur={total}[voice]")
    if music:
        g.append("[voice]asplit=2[vo][key]")
        g.append(f"[{2 * n}:a]aresample=48000,volume={music_volume},atrim=0:{total},"
                 f"afade=t=out:st={max(0.0, total - 1.5):.3f}:d=1.5[bed]")
        g.append("[bed][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[ducked]")
        g.append("[vo][ducked]amix=inputs=2:normalize=0[mix]")
        mix = "[mix]"
    else:
        mix = "[voice]"
    g.append(f"{mix}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    return [*args, "-filter_complex", ";".join(g), "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
            *codec, "-r", str(layout.FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]


def poster(png: Path, out: Path) -> list[str]:
    return ["-i", str(png), "-q:v", "3", str(out)]

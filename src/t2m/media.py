"""ffmpeg / ffprobe helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def run(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi: {proc.stderr.strip()[-1500:]}\nlệnh: ffmpeg {' '.join(args)}")


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


@lru_cache(maxsize=1)
def encoders() -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout


def video_codec_args(choice: str = "auto") -> list[str]:
    """h264_videotoolbox on the Mac (hardware, fast), libx264 elsewhere."""
    if choice == "auto":
        choice = "h264_videotoolbox" if sys.platform == "darwin" and "h264_videotoolbox" in encoders() else "libx264"
    if choice == "h264_videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", "10M", "-allow_sw", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p"]


def require_tools() -> list[str]:
    return [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]

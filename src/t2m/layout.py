"""Where things sit in the 1080x1920 frame. Pure numbers, shared by the HTML templates, ffmpeg and the subtitles."""

from __future__ import annotations

from dataclasses import dataclass

W, H, FPS = 1080, 1920, 30
# The phone the site is recorded in (CSS pixels, iPhone 15 size) and its scale for the recording file.
VIEWPORT = (393, 852)
RECORD_SCALE = 2


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


def _even(n: float) -> int:
    return int(round(n / 2) * 2)


SCREEN_W = 640
SCREEN = Rect(_even((W - SCREEN_W) / 2), 300, SCREEN_W, _even(SCREEN_W * VIEWPORT[1] / VIEWPORT[0]))
BEZEL = 22
PHONE = Rect(SCREEN.x - BEZEL, SCREEN.y - BEZEL, SCREEN.w + 2 * BEZEL, SCREEN.h + 2 * BEZEL)
SUB_MARGIN_V = 80  # subtitles: bottom edge of the text this far from the bottom of the frame
SAFE_BOTTOM = 330  # cards keep their content above this band (subtitles and the platforms' buttons)

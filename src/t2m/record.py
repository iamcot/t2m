"""Screen recordings of the real site in a phone frame, with the demo account (never real customer data).

One browser page records all shots of a job in one go (CDP screencast); the time marks of each shot cut it afterwards.
Each shot also leaves a screenshot (for carousels).
"""

from __future__ import annotations

import base64
import json
import shutil
import time
from pathlib import Path

from . import layout, media
from .render.html import launch_args
from .schema import Shot, Step

IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Version/18.0 Mobile/15E148 Safari/604.1")

# A soft circle where a finger taps, so viewers see what was pressed.
TAP_SCRIPT = """
window.__t2mTap = (x, y) => {
  const d = document.createElement('div');
  d.style.cssText = `position:fixed;left:${x - 28}px;top:${y - 28}px;width:56px;height:56px;border-radius:50%;
    background:rgba(0,166,81,.35);border:3px solid rgba(0,130,68,.8);z-index:2147483647;pointer-events:none;
    transition:transform .45s ease-out, opacity .45s ease-out;`;
  document.documentElement.appendChild(d);
  requestAnimationFrame(() => { d.style.transform = 'scale(1.6)'; d.style.opacity = '0'; });
  setTimeout(() => d.remove(), 600);
};
"""

SETTLE_MS = 700  # after a page load, before the shot starts


def login_script(user: dict) -> str:
    return f"try {{ localStorage.setItem('anylearn_user', {json.dumps(json.dumps(user))}); }} catch (e) {{}}"


def run_step(page, step: Step, site_url: str) -> None:
    if step.action == "goto":
        page.goto(site_url.rstrip("/") + (step.target or "/"), wait_until="load")
        page.wait_for_timeout(step.ms or 1200)
        return
    if step.action == "wait":
        page.wait_for_timeout(step.ms or 800)
        return
    if step.action == "press":
        page.keyboard.press(step.text or step.target or "Enter")
        page.wait_for_timeout(step.ms or 700)
        return
    if step.action == "scroll":
        page.evaluate("dy => window.scrollBy({top: dy, behavior: 'smooth'})", step.dy or 500)
        page.wait_for_timeout(step.ms or 1000)
        return
    loc = page.locator(step.target).first
    loc.scroll_into_view_if_needed()
    box = loc.bounding_box()
    if box:
        page.evaluate("([x, y]) => window.__t2mTap && window.__t2mTap(x, y)", [box["x"] + box["width"] / 2,
                                                                              box["y"] + box["height"] / 2])
        page.wait_for_timeout(250)
    loc.tap()
    if step.action == "type":
        page.keyboard.type(step.text or "", delay=90)
    page.wait_for_timeout(step.ms or 800)


class Screencast:
    """Frames of the page over CDP at device pixels (Playwright's own video is at CSS pixels, too blurry)."""

    def __init__(self, page, frames_dir: Path, max_w: int, max_h: int):
        self.frames: list[tuple[float, Path]] = []
        self.dir = frames_dir
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": max_w, "maxHeight": max_h,
                                               "everyNthFrame": 1})

    def _frame(self, event: dict) -> None:
        path = self.dir / f"{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((float(event["metadata"]["timestamp"]), path))
        self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

    def stop(self) -> None:
        self.cdp.send("Page.stopScreencast")


def concat_list(frames: list[tuple[float, Path]], start: float, end: float) -> str:
    """ffmpeg concat list of the frames shown between start and end (wall clock seconds). Pure.

    A screencast only sends a frame when the page changes, so each frame lasts until the next one.
    """
    shown = [f for f in frames if f[0] < end]
    before = [f for f in shown if f[0] <= start]
    picked = ([before[-1]] if before else []) + [f for f in shown if f[0] > start]
    if not picked:
        return ""
    lines = []
    for i, (t, path) in enumerate(picked):
        t0 = max(t, start)
        t1 = picked[i + 1][0] if i + 1 < len(picked) else end
        lines += [f"file '{path.resolve()}'", f"duration {max(0.001, t1 - t0):.3f}"]
    lines.append(f"file '{picked[-1][1].resolve()}'")  # the concat demuxer drops the last duration otherwise
    return "\n".join(lines) + "\n"


def record_shots(shots: dict[str, Shot], out_dir: Path, site_url: str, user: dict | None = None,
                 chromium_path: str = "") -> dict[str, Path]:
    """Records every shot; returns {shot id: mp4}. Screenshots go to `out_dir/{id}.png`."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "frames"
    shutil.rmtree(raw_dir, ignore_errors=True)
    raw_dir.mkdir()
    w, h = layout.VIEWPORT
    marks: dict[str, tuple[float, float]] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_args(chromium_path))
        context = browser.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=3, is_mobile=True, has_touch=True,
            locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh", user_agent=IPHONE_UA)
        context.add_init_script(TAP_SCRIPT)
        if user:
            context.add_init_script(login_script(user))
        page = context.new_page()
        cast = Screencast(page, raw_dir, w * layout.RECORD_SCALE, h * layout.RECORD_SCALE)
        try:
            for shot_id, shot in shots.items():
                steps = list(shot.steps)
                # Loading the first page is not part of the shot.
                while steps and steps[0].action == "goto":
                    run_step(page, steps.pop(0), site_url)
                page.wait_for_timeout(SETTLE_MS)
                start = time.time()
                for step in steps:
                    run_step(page, step, site_url)
                page.wait_for_timeout(500)
                marks[shot_id] = (start, time.time())
                page.screenshot(path=str(out_dir / f"{shot_id}.png"))
            cast.stop()
        finally:
            context.close()
            browser.close()
    out = {}
    for shot_id, (start, end) in marks.items():
        listing = concat_list(cast.frames, start, end)
        if not listing:
            raise RuntimeError(f"Shot {shot_id}: không nhận được khung hình nào")
        lst = raw_dir / f"{shot_id}.txt"
        lst.write_text(listing)
        mp4 = out_dir / f"{shot_id}.mp4"
        sw, sh = w * layout.RECORD_SCALE, h * layout.RECORD_SCALE
        media.run(["-f", "concat", "-safe", "0", "-i", str(lst), "-vf",
                   f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:0:white,"
                   f"fps={layout.FPS},format=yuv420p", "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(mp4)])
        out[shot_id] = mp4
    shutil.rmtree(raw_dir, ignore_errors=True)
    return out

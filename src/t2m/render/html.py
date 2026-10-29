"""HTML templates (assets/html) to PNG with Playwright."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import layout
from ..settings import ASSETS_DIR

ENV = Environment(loader=FileSystemLoader(ASSETS_DIR / "html"), autoescape=select_autoescape(["html"]))


def html(template: str, **ctx) -> str:
    base = dict(assets=ASSETS_DIR.as_uri(), W=layout.W, H=layout.H, PHONE=layout.PHONE, SCREEN=layout.SCREEN,
                BEZEL=layout.BEZEL, SAFE_BOTTOM=layout.SAFE_BOTTOM)
    return ENV.get_template(f"{template}.html").render(**base, **ctx)


def text_size(text: str | None, big: int, small: int, long_at: int = 28) -> int:
    """Shorter text, bigger letters."""
    n = len(text or "")
    if n <= long_at // 2:
        return big
    if n >= long_at * 2:
        return small
    return round(big - (big - small) * (n - long_at // 2) / (long_at * 1.5))


def launch_args(chromium_path: str = "") -> dict:
    return {"executable_path": chromium_path} if chromium_path else {}


@contextmanager
def browser(chromium_path: str = "") -> Iterator:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(**launch_args(chromium_path))
        try:
            yield b
        finally:
            b.close()


class Painter:
    """Renders templates to PNG files with one page reused."""

    def __init__(self, browser, work_dir: Path):
        self.page = browser.new_page(viewport={"width": layout.W, "height": layout.H}, device_scale_factor=1)
        self.work_dir = work_dir
        work_dir.mkdir(parents=True, exist_ok=True)

    def paint(self, template: str, out: Path, transparent: bool = False, **ctx) -> Path:
        src = self.work_dir / (out.stem + ".html")
        src.write_text(html(template, **ctx), encoding="utf-8")
        self.page.goto(src.resolve().as_uri())
        self.page.evaluate("document.fonts.ready.then(() => true)")
        self.page.wait_for_load_state("load")
        self.page.screenshot(path=str(out), omit_background=transparent)
        return out

    def card(self, out: Path, heading: str | None, sub: str | None, leo: bool) -> Path:
        return self.paint("card", out, heading=heading, sub=sub, leo=leo, heading_size=text_size(heading, 118, 84))

    def screen_background(self, out: Path, title: str | None) -> Path:
        return self.paint("screen_bg", out, title=title, title_size=text_size(title, 88, 64))

    def bezel(self, out: Path) -> Path:
        return self.paint("bezel", out, transparent=True)

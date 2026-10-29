"""Whole render on a fake page: silent voice, one card and one screen recording. Needs ffmpeg and Chromium."""

import http.server
import shutil
import threading
from pathlib import Path

import pytest

from t2m import media, templates
from t2m.record import record_shots
from t2m.render.compose import render
from t2m.schema import Cta, Scene, Script, Shot, Step, Visual
from t2m.settings import REPO_DIR, Settings
from t2m.tts import load_profiles


def _browser_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not _browser_ok(), reason="cần ffmpeg và Chromium")

PAGE = (Path(__file__).parent / "fixtures" / "fake_site.html").read_bytes()


@pytest.fixture
def site():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGE)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_render_short_video(tmp_path, site, monkeypatch):
    monkeypatch.setitem(templates.TEMPLATES, "test", templates.Template("test", "Test", 5, "nhap", ("card", "screen"), ""))
    shots = {"loc": Shot(description="Bật học thử", steps=[
        Step(action="goto", target="/search"), Step(action="tap", target="[aria-label='Lọc nhanh'] >> text=Học thử")])}
    script = Script(
        template="test", title="Thử", hook="Tìm lớp cho con?", campaign="t",
        scenes=[Scene(id="a", narration="Tìm lớp cho con mà lướt mãi?", visual=Visual(kind="card", leo=True)),
                Scene(id="b", narration="Bật học thử là xong.", on_screen="Lớp có học thử",
                      visual=Visual(kind="screen", shot="loc"))],
        cta=Cta(text="Thử ngay", link="/search"), captions={}, shots=shots)
    settings = Settings(site_url=site, music_dir=tmp_path / "none")
    profiles = load_profiles(REPO_DIR / "config" / "voices.toml")

    def record(missing, out_dir):
        return record_shots(missing, out_dir, site)

    result = render(tmp_path / "job", script, settings, profiles, record, use_whisper=False, music=False)
    assert result.video.exists() and result.poster.exists()
    total = sum(d for _, d in result.scenes)
    assert abs(media.duration(result.video) - total) < 0.2
    assert (tmp_path / "job" / "carousel" / "01-loc.png").exists()
    assert "Dialogue" in (tmp_path / "job" / "subtitles.ass").read_text()

"""t2m command line. Flow: new -> script -> (record) -> render -> review -> approve -> publish."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

from . import checks, settings as settings_mod, templates
from .schema import Brief, Script
from .store import Job, Store

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Làm video ngắn cho anyLEARN bằng AI.")
voices_app = typer.Typer(no_args_is_help=True, help="Hồ sơ giọng đọc.")
app.add_typer(voices_app, name="voices")


def _ctx() -> tuple[settings_mod.Settings, Store]:
    s = settings_mod.load()
    s.jobs_dir.mkdir(parents=True, exist_ok=True)
    return s, Store(s.db_path, s.jobs_dir)


def _brief(job: Job) -> Brief:
    return Brief.load(job.brief_path)


def _script(job: Job) -> Script:
    if not job.script_path.exists():
        raise typer.BadParameter(f"Job {job.id} chưa có kịch bản (chạy t2m script {job.id})")
    return Script.model_validate_json(job.script_path.read_text(encoding="utf-8"))


def _print_problems(problems: list[checks.Problem]) -> None:
    if not problems:
        typer.secho("Kiểm tra: không có lỗi.", fg="green")
    for p in problems:
        typer.secho(str(p), fg="red" if p.level == "error" else "yellow")


def _item_fetcher(s: settings_mod.Settings):
    from .anylearn import Anylearn
    api = Anylearn(s.api)
    return api.item


@app.command()
def new(brief: Path, day: str = typer.Option(None, help="Ngày đăng YYYYMMDD, đứng đầu mã job")) -> None:
    """Tạo job từ một brief (.toml, xem briefs/)."""
    s, store = _ctx()
    b = Brief.load(brief)
    templates.get(b.template)
    job = store.create(b.template, b.topic, brief.read_text(encoding="utf-8"), day)
    typer.echo(f"Đã tạo job {job.id} ở {job.dir}")


@app.command("list")
def list_jobs() -> None:
    """Liệt kê job."""
    _, store = _ctx()
    for j in store.all():
        typer.echo(f"{j.id:50} {j.status:10} {j.template:14} {j.title}")


@app.command()
def script(job_id: str, ai: str = typer.Option(None, help="api | claude-code (mặc định theo t2m.toml)"),
           from_file: Path = typer.Option(None, "--from", help="Dùng kịch bản JSON có sẵn thay vì gọi AI")) -> None:
    """Viết kịch bản bằng AI (hoặc nạp file), rồi kiểm tra."""
    from . import ai as ai_mod
    from .schema import AiScript
    s, store = _ctx()
    job = store.get(job_id)
    brief = _brief(job)
    if from_file:
        data = json.loads(from_file.read_text(encoding="utf-8"))
        result = AiScript.model_validate(data).to_script(brief)
        problems = checks.check_script(result, brief.seconds)
    else:
        result, problems = ai_mod.write_script(ai_mod.writer(ai or s.ai_mode, s), brief, store, job.id)
    job.script_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    store.set_status(job.id, "script")
    typer.echo(f"Đã ghi {job.script_path} ({result.narration_words()} chữ, {len(result.scenes)} cảnh)")
    _print_problems(problems)


@app.command()
def check(job_id: str, live: bool = typer.Option(True, help="So tên / giá khóa với API")) -> None:
    """Kiểm tra kịch bản: số chữ, cách viết anyPoint / Leo Xu, lời hứa, tên và giá khóa."""
    s, store = _ctx()
    job = store.get(job_id)
    sc = _script(job)
    problems = checks.check_script(sc, _brief(job).seconds)
    if live and sc.items:
        problems += checks.check_items(sc, _item_fetcher(s))
    _print_problems(problems)
    raise typer.Exit(1 if checks.has_errors(problems) else 0)


def _recorder(s: settings_mod.Settings, login: bool):
    from .record import record_shots
    user = None
    if login:
        from .anylearn import Anylearn
        user = Anylearn(s.api).login(s.demo_phone, s.demo_password)

    def run(shots: dict, out_dir: Path) -> dict:
        typer.echo(f"Quay {len(shots)} shot trên {s.site_url} ...")
        return record_shots(shots, out_dir, s.site_url, user, s.chromium_path)
    return run


@app.command()
def record(job_id: str, shot: list[str] = typer.Option(None, help="Chỉ quay lại shot này (lặp được)"),
           login: bool = typer.Option(True, help="Đăng nhập tài khoản demo")) -> None:
    """Quay màn hình site ở khung điện thoại theo các shot của brief."""
    s, store = _ctx()
    job = store.get(job_id)
    shots = _brief(job).shots
    if shot:
        shots = {k: v for k, v in shots.items() if k in shot}
    out = _recorder(s, login)(shots, job.dir / "recordings")
    for k, v in out.items():
        typer.echo(f"  {k}: {v}")


@app.command()
def render(job_id: str, force: bool = typer.Option(False, help="Dựng dù kiểm tra còn lỗi"),
           voice: str = typer.Option(None, help="Dùng hồ sơ giọng này cho mọi cảnh (ví dụ: nhap)"),
           login: bool = typer.Option(True, help="Đăng nhập tài khoản demo khi phải quay"),
           whisper: bool = typer.Option(True, help="Căn phụ đề bằng mlx-whisper nếu đã cài"),
           music: bool = typer.Option(True, help="Nhạc nền từ assets/music")) -> None:
    """Dựng video: giọng, quay màn hình (nếu thiếu), cảnh, phụ đề, nhạc, final.mp4 + poster.jpg."""
    from .render.compose import render as do_render
    from .tts import load_profiles
    s, store = _ctx()
    job = store.get(job_id)
    sc = _script(job)
    problems = checks.check_script(sc, _brief(job).seconds)
    if checks.has_errors(problems) and not force:
        _print_problems(problems)
        raise typer.Exit(1)
    profiles = load_profiles(s.voices_file)
    if voice:
        sc = sc.model_copy(update={"voices": {scene.voice: voice for scene in sc.scenes}})
    result = do_render(job.dir, sc, s, profiles, _recorder(s, login), use_whisper=whisper, music=music)
    store.set_status(job.id, "rendered")
    typer.echo(f"Xong: {result.video} ({result.seconds:.1f}s), poster {result.poster}")
    for sid, d in result.scenes:
        typer.echo(f"  {sid:12} {d:5.1f}s")


@app.command()
def review(job_id: str, open_video: bool = typer.Option(True, "--open/--no-open", help="Mở video để xem")) -> None:
    """Xem lại trước khi duyệt: kịch bản, lỗi kiểm tra, caption, mở video."""
    s, store = _ctx()
    job = store.get(job_id)
    sc = _script(job)
    typer.secho(f"{job.id} [{job.status}] {sc.title}", bold=True)
    typer.echo(f"Câu mở: {sc.hook}")
    for scene in sc.scenes:
        typer.echo(f"- {scene.id} ({scene.visual.kind}{':' + scene.visual.shot if scene.visual.shot else ''}): "
                   f"{scene.narration}")
    typer.echo(f"Kêu gọi: {sc.cta.text} -> {sc.cta.link}")
    for ch, text in sc.captions.items():
        typer.echo(f"[{ch}] {text}")
    _print_problems(checks.check_script(sc, _brief(job).seconds))
    if open_video and job.final_path.exists():
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.run([opener, str(job.final_path)], check=False)


@app.command()
def approve(job_id: str, by: str = typer.Option(..., help="Tên người duyệt")) -> None:
    """Người duyệt đồng ý: chỉ job đã duyệt mới được publish."""
    _, store = _ctx()
    job = store.get(job_id)
    if job.status not in ("rendered", "approved"):
        raise typer.BadParameter(f"Job đang ở trạng thái {job.status}, cần dựng xong (rendered) trước khi duyệt")
    if checks.has_errors(checks.check_script(_script(job), _brief(job).seconds)):
        raise typer.BadParameter("Kịch bản còn lỗi kiểm tra, sửa rồi dựng lại")
    from datetime import datetime
    store.set_status(job.id, "approved", approved_by=by, approved_at=datetime.now().isoformat(timespec="seconds"))
    typer.secho(f"{job.id} đã được {by} duyệt.", fg="green")


@app.command()
def publish(job_id: str, to: str = typer.Option("export", help="export (file + caption để đăng tay) | explore")) -> None:
    """Xuất file cho mạng xã hội, hoặc gửi lên Khám phá bằng tài khoản Studio (bài chờ duyệt trong back office)."""
    from . import publish as pub
    s, store = _ctx()
    job = store.get(job_id)
    if job.status not in ("approved", "published"):
        raise typer.BadParameter("Chưa duyệt: chạy t2m approve trước")
    sc = _script(job)
    if to == "export":
        out = pub.export(job, sc, s.site_url)
        typer.echo(f"Đã xuất vào {out}")
    elif to == "explore":
        from .anylearn import Anylearn
        api = Anylearn(s.api)
        api.login(s.studio_phone, s.studio_password)
        post_id = pub.to_explore(job, sc, api, on_progress=lambda a, b: typer.echo(f"  tải lên {a * 100 // b}%"))
        store.set_status(job.id, "published", explore_post_id=post_id)
        typer.secho(f"Đã gửi bài Khám phá #{post_id}, chờ duyệt trong back office.", fg="green")
    else:
        raise typer.BadParameter("--to phải là export hoặc explore")


@app.command()
def usage(days: int = 30) -> None:
    """Token AI đã dùng."""
    _, store = _ctx()
    for r in store.ai_totals(days):
        cost = f", ${r['cost']:.2f}" if r["cost"] else ""
        typer.echo(f"{r['mode']:12} {r['model'] or '?':24} {r['calls']} lần (lỗi {r['failed']}), "
                   f"vào {r['input'] or 0} / ra {r['output'] or 0} token{cost}")


@voices_app.command("list")
def voices_list() -> None:
    """Liệt kê hồ sơ giọng và template dùng giọng nào."""
    from .tts import load_profiles
    s = settings_mod.load()
    for k, p in load_profiles(s.voices_file).items():
        typer.echo(f"{k:16} {p.provider:7} {p.voice or '-':10} {p.label}")
    for t in templates.TEMPLATES.values():
        typer.echo(f"template {t.key}: người dẫn = {t.narrator_profile}")


@voices_app.command("try")
def voices_try(profile: str, text: str = "Chào ba mẹ, mình là Leo. Hôm nay mình chỉ ba mẹ cách tìm lớp cho bé.",
               out: Path = Path("voice-test.wav")) -> None:
    """Nghe thử một hồ sơ giọng."""
    from .tts import load_profiles, speak
    s = settings_mod.load()
    speech = speak(text, load_profiles(s.voices_file)[profile], out)
    typer.echo(f"{speech.path} ({speech.duration:.1f}s)")
    if sys.platform == "darwin":
        subprocess.run(["afplay", str(speech.path)], check=False)


if __name__ == "__main__":
    app()

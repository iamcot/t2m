from pathlib import Path

from t2m import layout
from t2m.render import ffmpeg


def parts(*seconds):
    return [ffmpeg.Part(Path(f"c{i}.mp4"), Path(f"v{i}.wav"), s) for i, s in enumerate(seconds)]


def test_scene_seconds():
    assert ffmpeg.scene_seconds(3.0, 2.0) == 3.7
    assert ffmpeg.scene_seconds(0.5, 2.0) == 2.0


def test_starts_and_clip_lengths():
    p = parts(3.0, 4.0, 5.0)
    assert ffmpeg.starts(p) == [0.0, 3.0, 7.0]
    assert ffmpeg.clip_seconds(p, 0) == 3.0 + ffmpeg.FADE
    assert ffmpeg.clip_seconds(p, 2) == 5.0


def test_fit_recording():
    assert ffmpeg.fit_recording(4.0, 3.0).startswith("setpts=0.75")
    assert ffmpeg.fit_recording(10.0, 3.0).startswith("trim=duration=3.000")
    assert ffmpeg.fit_recording(2.0, 3.0) == "tpad=stop_mode=clone:stop_duration=1.200"


def test_final_graph_offsets_and_voice_delays():
    args = ffmpeg.final(parts(3.0, 4.0, 5.0), Path("/j/s.ass"), Path("/f"), Path("out.mp4"), ["-c:v", "libx264"])
    graph = args[args.index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.3:offset=3.000[x1]" in graph
    assert "[x1][2:v]xfade=transition=fade:duration=0.3:offset=7.000[x2]" in graph
    assert "[3:a]aresample=48000,adelay=250:all=1[a0]" in graph
    assert "[5:a]aresample=48000,adelay=7250:all=1[a2]" in graph
    assert "sidechaincompress" not in graph
    assert args[args.index("-t") + 1] == "12.000"


def test_final_with_music_ducks():
    args = ffmpeg.final(parts(3.0, 4.0), Path("s.ass"), Path("f"), Path("o.mp4"), [], music=Path("m.mp3"))
    graph = args[args.index("-filter_complex") + 1]
    assert args[args.index("-stream_loop") + 3] == "m.mp3"
    assert "[4:a]aresample=48000,volume=0.18" in graph
    assert "[bed][key]sidechaincompress" in graph


def test_layout_fits_frame():
    s, p = layout.SCREEN, layout.PHONE
    assert s.w % 2 == 0 and s.h % 2 == 0
    assert p.x >= 0 and p.x + p.w <= layout.W
    assert p.y + p.h < layout.H - layout.SUB_MARGIN_V - 80
    assert abs(s.w / s.h - layout.VIEWPORT[0] / layout.VIEWPORT[1]) < 0.005

"""ASS subtitles, a few words per line, each word lights up when it is said (karaoke `\\k`). Pure."""

from __future__ import annotations

from dataclasses import dataclass

from .tts.base import WordTime

WHITE = "&H00FFFFFF"
YELLOW = "&H0005CAFF"  # brand yellow #ffca05 (ASS colours are &HAABBGGRR)
NAVY = "&H00331B07"  # brand navy #071b33


@dataclass(frozen=True)
class SubStyle:
    font: str = "Be Vietnam Pro ExtraBold"
    size: int = 66
    margin_v: int = 150  # from the bottom edge
    max_words: int = 4
    max_chars: int = 24


def chunk(words: list[WordTime], style: SubStyle) -> list[list[WordTime]]:
    """Lines of at most `max_words` / `max_chars`; a line also ends after . , ? !"""
    lines: list[list[WordTime]] = []
    line: list[WordTime] = []
    for w in words:
        if line and (len(line) >= style.max_words or len(" ".join(x.word for x in line + [w])) > style.max_chars):
            lines.append(line)
            line = []
        line.append(w)
        if w.word[-1:] in ".,?!:;…":
            lines.append(line)
            line = []
    if line:
        lines.append(line)
    return lines


def ts(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(word: str) -> str:
    return word.replace("\\", "").replace("{", "(").replace("}", ")")


def dialogue(line: list[WordTime], next_start: float | None) -> str:
    start = line[0].start
    # Keep the line a moment after its last word, but never over the next line.
    end = line[-1].end + 0.25
    if next_start is not None:
        end = min(end, next_start)
    parts, t = [], start
    for w in line:
        cs = max(1, round((w.end - t) * 100))  # includes the pause before the word
        parts.append(f"{{\\k{cs}}}{_escape(w.word)}")
        t = w.end
    return f"Dialogue: 0,{ts(start)},{ts(end)},Karaoke,,0,0,0,,{' '.join(parts)}"


def build_ass(words: list[WordTime], width: int = 1080, height: int = 1920, style: SubStyle = SubStyle()) -> str:
    """`words` carry absolute times in the video."""
    lines = chunk(words, style)
    events = [dialogue(line, lines[i + 1][0].start if i + 1 < len(lines) else None) for i, line in enumerate(lines)]
    return "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Karaoke,{style.font},{style.size},{YELLOW},{WHITE},{NAVY},&H80000000,0,0,0,0,100,100,0,0,1,7,2,2,60,60,"
        f"{style.margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *events,
        "",
    ])


def build_srt(words: list[WordTime], style: SubStyle = SubStyle(max_words=8, max_chars=42)) -> str:
    """Plain subtitles for the platforms that take a file (YouTube)."""
    def t(s: float) -> str:
        ms = max(0, round(s * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        sec, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
    out = []
    for i, line in enumerate(chunk(words, style), 1):
        out += [str(i), f"{t(line[0].start)} --> {t(line[-1].end + 0.2)}", " ".join(w.word for w in line), ""]
    return "\n".join(out)

from t2m import align, subtitles
from t2m.tts.base import WordTime


def test_proportional_spreads_over_span():
    words = align.proportional("một hai ba", 1.0, 4.0)
    assert [w.word for w in words] == ["một", "hai", "ba"]
    assert words[0].start == 1.0 and abs(words[-1].end - 4.0) < 0.01
    assert all(a.end <= b.start + 1e-6 for a, b in zip(words, words[1:]))


def test_fit_uses_heard_times_when_counts_match():
    heard = [WordTime("Mot", 0.2, 0.5), WordTime("hai", 0.6, 0.9)]
    assert align.fit("Một hai", heard, 1.0) == [WordTime("Một", 0.2, 0.5), WordTime("hai", 0.6, 0.9)]
    spread = align.fit("Một hai ba", heard, 1.0)
    assert spread[0].start == 0.2 and abs(spread[-1].end - 0.9) < 0.01


def test_chunk_breaks_on_length_and_punctuation():
    words = align.proportional("Ba mẹ tìm lớp, cho con mà lướt mãi không ra lớp nào hợp", 0, 6)
    lines = subtitles.chunk(words, subtitles.SubStyle(max_words=4, max_chars=24))
    texts = [" ".join(w.word for w in line) for line in lines]
    assert texts[0] == "Ba mẹ tìm lớp,"
    assert all(len(line) <= 4 for line in lines)


def test_ass_karaoke_lines():
    words = [WordTime("Xin", 1.0, 1.3), WordTime("chào", 1.3, 1.8)]
    ass = subtitles.build_ass(words)
    assert "PlayResX: 1080" in ass
    line = [l for l in ass.splitlines() if l.startswith("Dialogue")][0]
    assert line.startswith("Dialogue: 0,0:00:01.00,0:00:02.05,Karaoke")
    assert "{\\k30}Xin {\\k50}chào" in line


def test_ass_escapes_braces():
    ass = subtitles.build_ass([WordTime("{x}", 0, 1)])
    assert "(x)" in ass


def test_srt():
    srt = subtitles.build_srt([WordTime("Xin", 61.0, 61.5), WordTime("chào", 61.5, 62.0)])
    assert "00:01:01,000 --> 00:01:02,200" in srt
    assert "Xin chào" in srt

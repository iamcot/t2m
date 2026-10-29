from pathlib import Path

import pytest

from t2m import tts
from t2m.settings import REPO_DIR
from t2m.store import Store


def test_job_ids_are_unique(tmp_path):
    store = Store(tmp_path / "t.db", tmp_path / "jobs")
    a = store.create("feature_tour", "Tìm kiếm thông minh", "brief", "20261104")
    b = store.create("feature_tour", "Tìm kiếm thông minh", "brief", "20261104")
    assert a.id == "20261104-tim-kiem-thong-minh" and b.id == a.id + "-2"
    assert a.brief_path.read_text() == "brief"
    store.set_status(a.id, "rendered")
    assert store.get(a.id).status == "rendered"
    with pytest.raises(AssertionError):
        store.set_status(a.id, "lost")


def test_voice_profiles_and_template_defaults(script):
    profiles = tts.load_profiles(REPO_DIR / "config" / "voices.toml")
    assert {"ro_rang", "am_tram", "tre_nhi_nhanh", "nhap"} <= profiles.keys()
    assert profiles["ro_rang"].options == {"rate": 185}
    assert tts.profile_key(script, "narrator") == "ro_rang"
    script.voices = {"be": "tre_nhi_nhanh"}
    assert tts.profile_key(script, "be") == "tre_nhi_nhanh"


def test_post_filter():
    p = tts.VoiceProfile("k", "k", "say")
    assert tts.post_filter(p) == "anull"
    up = tts.post_filter(tts.VoiceProfile("k", "k", "say", speed=1.1, pitch=12))
    assert up == "asetrate=96000,aresample=48000,atempo=0.50000,atempo=1.1000"

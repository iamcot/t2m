import json

import httpx

from t2m import publish
from t2m.anylearn import Anylearn
from t2m.store import Store
from t2m.text import slugify


def test_slugify():
    assert slugify("Tìm kiếm thông minh: Đố vui!") == "tim-kiem-thong-minh-do-vui"


def test_utm_link():
    link = publish.utm_link("https://anylearn.vn/", "/search", "facebook", "ra-mat-v2", "job1")
    assert link == ("https://anylearn.vn/search?utm_source=facebook&utm_medium=social&utm_campaign=ra-mat-v2"
                    "&utm_content=job1")
    assert "&utm_source=" in publish.utm_link("https://x", "/a?b=1", "zalo", "", "j")


def test_caption_replaces_plain_link(script):
    text = publish.caption_for(script, "facebook", "https://anylearn.vn/search?utm_source=facebook")
    assert "anylearn.vn/search?utm_source=facebook" in text
    assert text.count("anylearn.vn/search") == 1
    assert text.endswith("#anyLEARN #timlopchocon #hocthu #phuhuynh")
    tiktok = publish.caption_for(script, "tiktok", "L")
    assert "👉 L" in tiktok
    assert "#" not in publish.caption_for(script, "zalo", "L").replace("anylearn", "")


def test_export(tmp_path, script):
    store = Store(tmp_path / "t.db", tmp_path / "jobs")
    job = store.create("feature_tour", "Tìm kiếm", "x", "20261104")
    job.final_path.write_bytes(b"mp4")
    job.poster_path.write_bytes(b"jpg")
    out = publish.export(job, script, "https://anylearn.vn")
    assert (out / f"{job.id}.mp4").read_bytes() == b"mp4"
    fb = (out / "facebook.txt").read_text()
    assert "utm_campaign=ra-mat-v2" in fb and f"utm_content={job.id}" in fb


def test_to_explore_flow(tmp_path, script):
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path, request.content))
        path = request.url.path
        if path.endswith("/creator/me"):
            return httpx.Response(200, json={"resultCode": 1, "data": {"level": "creator"}})
        if path.endswith("/creator/tags"):
            q = request.url.params["q"]
            data = [{"id": 7, "name": "Học thử"}] if q == "hocthu" else []
            return httpx.Response(200, json={"resultCode": 1, "data": data})
        if path.endswith("/video-upload"):
            return httpx.Response(200, json={"resultCode": 1, "data": {
                "endpoint": "https://video.bunnycdn.com/tusupload", "videoId": "vid", "libraryId": 5,
                "authorizationSignature": "sig", "authorizationExpire": 99, "mediaUrl": "https://cdn/vid/playlist.m3u8",
                "posterUrl": "https://cdn/vid/thumbnail.jpg"}})
        if path.endswith("/creator/posts"):
            return httpx.Response(200, json={"resultCode": 1, "data": {"id": 42, "status": "draft"}})
        if path.endswith("/posts/42/media"):
            return httpx.Response(200, json={"resultCode": 1, "data": {"ok": True}})
        if path == "/tusupload":
            assert request.headers["AuthorizationSignature"] == "sig"
            return httpx.Response(201, headers={"Location": "/tusupload/abc"})
        if path == "/tusupload/abc":
            assert request.headers["Upload-Offset"] == "0"
            return httpx.Response(204, headers={"Upload-Offset": str(len(request.content))})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = Store(tmp_path / "t.db", tmp_path / "jobs")
    job = store.create("feature_tour", "Tìm kiếm", "x")
    job.final_path.write_bytes(b"0" * 1000)
    api = Anylearn("https://anylearn.vn/v2/api", client, token="t")
    assert publish.to_explore(job, script, api, client) == 42
    post = json.loads(next(c for c in calls if c[1].endswith("/creator/posts"))[2])
    assert post["tagIds"] == [7] and post["uploading"] is True and post["kind"] == "video"
    media = json.loads(calls[-1][2])
    assert calls[-1][1].endswith("/posts/42/media") and media["mediaUrl"].endswith("playlist.m3u8")


def test_api_error_message():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"resultCode": 0, "message": "Bạn chưa được mở quyền"})))
    try:
        Anylearn("https://x/v2/api", client, token="t").creator_me()
    except Exception as e:
        assert "chưa được mở quyền" in str(e)
    else:
        raise AssertionError("expected an error")

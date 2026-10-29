"""anyLEARN API: login, course data for the checks, Khám phá creator posts and the Bunny TUS clip upload."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

TUS_CHUNK = 8 * 1024 * 1024


class ApiError(RuntimeError):
    pass


class Anylearn:
    def __init__(self, api: str, client: httpx.Client | None = None, token: str | None = None):
        self.api = api.rstrip("/")
        self.client = client or httpx.Client(timeout=60)
        self.token = token

    def _call(self, method: str, path: str, **kw):
        headers = kw.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        res = self.client.request(method, f"{self.api}{path}", headers=headers, **kw)
        if res.status_code == 401:
            raise ApiError("Hết phiên đăng nhập hoặc sai tài khoản")
        res.raise_for_status()
        body = res.json()
        if body.get("resultCode") != 1:
            raise ApiError(body.get("message") or f"{method} {path} thất bại")
        return body.get("data")

    def login(self, phone: str, password: str) -> dict:
        """The login response (the site keeps it in localStorage `anylearn_user`); sets the token for later calls."""
        if not phone or not password:
            raise ApiError("Thiếu số điện thoại hoặc mật khẩu (xem t2m.example.toml)")
        data = self._call("GET", "/login", params={"phone": phone, "password": password})
        self.token = data["jwtToken"]
        return data

    def item(self, item_id: int) -> dict | None:
        try:
            return (self._call("GET", f"/pdp/{item_id}") or {}).get("item")
        except (ApiError, httpx.HTTPStatusError):
            return None

    # Khám phá, as a creator (posts of level `creator` wait for review in the back office).

    def creator_me(self) -> dict:
        return self._call("GET", "/explore/creator/me")

    def tags(self, q: str) -> list[dict]:
        return self._call("GET", "/explore/creator/tags", params={"q": q}) or []

    def create_post(self, body: dict) -> dict:
        return self._call("POST", "/explore/creator/posts", json=body)

    def video_upload(self, title: str) -> dict:
        return self._call("POST", "/explore/creator/video-upload", json={"title": title})

    def attach_media(self, post_id: int, media_url: str, poster_url: str) -> None:
        self._call("PUT", f"/explore/creator/posts/{post_id}/media", json={"mediaUrl": media_url, "posterUrl": poster_url})

    def upload_image(self, path: Path) -> str:
        with path.open("rb") as f:
            return self._call("POST", "/explore/creator/upload", files={"image": (path.name, f, "image/jpeg")})["url"]


def tus_upload(client: httpx.Client, info: dict, path: Path, title: str, on_progress=None) -> None:
    """Bunny Stream TUS upload with the signature the backend gave (`video_upload`)."""
    size = path.stat().st_size
    meta = ",".join(f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in
                    {"filetype": "video/mp4", "title": title}.items())
    auth = {
        "AuthorizationSignature": info["authorizationSignature"],
        "AuthorizationExpire": str(info["authorizationExpire"]),
        "VideoId": info["videoId"],
        "LibraryId": str(info["libraryId"]),
        "Tus-Resumable": "1.0.0",
    }
    res = client.post(info["endpoint"], headers={**auth, "Upload-Length": str(size), "Upload-Metadata": meta})
    if res.status_code not in (200, 201):
        raise ApiError(f"Bunny không nhận tải lên ({res.status_code}): {res.text[:200]}")
    location = str(httpx.URL(info["endpoint"]).join(res.headers["Location"]))
    offset = 0
    with path.open("rb") as f:
        while offset < size:
            chunk = f.read(TUS_CHUNK)
            res = client.patch(location, content=chunk, headers={
                **auth, "Upload-Offset": str(offset), "Content-Type": "application/offset+octet-stream"})
            if res.status_code not in (200, 204):
                raise ApiError(f"Bunny dừng ở {offset}/{size} byte ({res.status_code})")
            offset = int(res.headers.get("Upload-Offset", offset + len(chunk)))
            if on_progress:
                on_progress(offset, size)

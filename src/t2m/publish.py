"""After a person approves: files + captions for each social channel, and the clip sent to Khám phá (waits for review)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import urlencode

import httpx

from .anylearn import Anylearn, tus_upload
from .schema import Script
from .store import Job
from .text import slugify

SOCIAL = ("facebook", "tiktok", "youtube", "zalo")
HASHTAG_CHANNELS = ("facebook", "tiktok", "youtube")


def explore_path(post_id: int, title: str) -> str:
    """Public link of a Khám phá post (plan 19.A3)."""
    return f"/fun/explore/{post_id}/{slugify(title)}"


def utm_link(site_url: str, path: str, channel: str, campaign: str, content: str) -> str:
    query = urlencode({"utm_source": channel, "utm_medium": "social", "utm_campaign": campaign or "t2m",
                       "utm_content": content})
    sep = "&" if "?" in path else "?"
    return f"{site_url.rstrip('/')}{path}{sep}{query}"


def caption_for(script: Script, channel: str, link: str) -> str:
    """The channel's caption with its plain anylearn.vn link replaced by the tracked one (added when missing)."""
    text = script.captions.get(channel, "").strip()
    plain = re.compile(r"(https?://)?(www\.)?anylearn\.vn" + re.escape(script.cta.link) + r"(?![\w/-])")
    text, n = plain.subn(link, text)
    if not n:
        text = f"{text}\n\n👉 {link}".strip()
    if channel in HASHTAG_CHANNELS and script.hashtags:
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in script.hashtags)
        text = f"{text}\n\n{tags}"
    return text


def export(job: Job, script: Script, site_url: str) -> Path:
    """`jobs/{id}/export/`: video, poster, subtitles, one caption file per channel (to post by hand for now)."""
    out = job.dir / "export"
    out.mkdir(exist_ok=True)
    shutil.copy(job.final_path, out / f"{job.id}.mp4")
    shutil.copy(job.poster_path, out / f"{job.id}.jpg")
    if (job.dir / "subtitles.srt").exists():
        shutil.copy(job.dir / "subtitles.srt", out / f"{job.id}.srt")
    path = explore_path(job.explore_post_id, script.title) if job.explore_post_id else script.cta.link
    for channel in SOCIAL:
        link = utm_link(site_url, path, channel, script.campaign, job.id)
        (out / f"{channel}.txt").write_text(caption_for(script, channel, link) + "\n", encoding="utf-8")
    carousel = job.dir / "carousel"
    if carousel.exists():
        shutil.copytree(carousel, out / "carousel", dirs_exist_ok=True)
    return out


def match_tags(api: Anylearn, hashtags: list[str], limit: int = 8) -> list[int]:
    """Existing tags of the dictionary whose name matches a hashtag (creators cannot create tags)."""
    ids: list[int] = []
    for tag in hashtags:
        word = tag.lstrip("#")
        for t in api.tags(word):
            if slugify(t.get("name", "")).replace("-", "") == slugify(word).replace("-", "") and t["id"] not in ids:
                ids.append(t["id"])
                break
        if len(ids) >= limit:
            break
    return ids


def to_explore(job: Job, script: Script, api: Anylearn, upload_client: httpx.Client | None = None,
               on_progress=None) -> int:
    """Creates the post as the Studio creator, uploads the clip to Bunny, attaches it. Returns the post id."""
    api.creator_me()  # fails early when the account is not a creator
    info = api.video_upload(script.title)
    item_id = script.items[0].id if script.items else None
    post = api.create_post({
        "kind": "video", "title": script.title, "body": script.captions.get("explore", ""), "mediaUrl": "",
        "posterUrl": "", "itemId": item_id, "tagIds": match_tags(api, script.hashtags), "uploading": True,
    })
    post_id = int(post["id"])
    tus_upload(upload_client or httpx.Client(timeout=300), info, job.final_path, script.title, on_progress)
    api.attach_media(post_id, info["mediaUrl"], info["posterUrl"])
    return post_id

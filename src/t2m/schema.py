"""Brief (what a person asks for) and script (what the AI writes, what the renderer reads)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CHANNELS = ("facebook", "tiktok", "youtube", "zalo", "explore")


class Step(BaseModel):
    """One action of a screen recording, run by Playwright on the real site.

    `target`: a path for `goto`, a Playwright selector (`text=Học thử`, `role=button[name='Lọc']`, css) for the others.
    """

    action: Literal["goto", "tap", "type", "scroll", "wait", "press"]
    target: str | None = None
    text: str | None = None
    ms: int | None = None
    dy: int | None = None  # scroll distance in CSS pixels


class Shot(BaseModel):
    """A named piece of screen recording, written by a person (selectors cannot be guessed by the AI)."""

    description: str
    steps: list[Step]


class ItemRef(BaseModel):
    """A course the script names: the checks compare the title and price with the live API."""

    id: int
    title: str
    price: int | None = None


class Brief(BaseModel):
    template: str
    topic: str
    angle: str = ""
    link: str = "/"
    campaign: str = ""
    notes: str = ""
    seconds: int | None = None  # overrides the template's target length
    voices: dict[str, str] = Field(default_factory=dict)  # character -> voice profile
    items: list[ItemRef] = Field(default_factory=list)
    shots: dict[str, Shot] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Brief":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


class Visual(BaseModel):
    kind: Literal["card", "screen"]
    heading: str | None = Field(None, description="Big text of a card (max ~8 words)")
    sub: str | None = Field(None, description="Small text under the heading of a card")
    shot: str | None = Field(None, description="Id of a shot from the brief, for kind=screen")
    leo: bool = Field(False, description="Show the mascot Leo on a card")


class Scene(BaseModel):
    id: str = Field(description="Short id, letters and digits, unique in the script")
    narration: str = Field(description="What the voice says in this scene, Vietnamese")
    on_screen: str | None = Field(None, description="Short title above the phone on screen scenes (max ~6 words)")
    voice: str = Field("narrator", description="Character speaking; 'narrator' unless the brief names others")
    visual: Visual
    min_seconds: float = 2.0


class Cta(BaseModel):
    text: str = Field(description="Call to action said and shown at the end")
    link: str = Field(description="Path on anylearn.vn, starts with /")


class Script(BaseModel):
    template: str
    title: str = Field(description="Internal title of the video")
    hook: str = Field(description="Text shown big in the first second, a parent's worry or a question")
    scenes: list[Scene]
    cta: Cta
    captions: dict[str, str] = Field(description="Post text per channel: facebook, tiktok, youtube, zalo, explore")
    hashtags: list[str] = Field(default_factory=list)
    # Filled from the brief by t2m, not by the AI:
    campaign: str = ""
    voices: dict[str, str] = Field(default_factory=dict)
    items: list[ItemRef] = Field(default_factory=list)
    shots: dict[str, Shot] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Script":
        ids = [s.id for s in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("scene ids must be unique")
        return self

    def narration_words(self) -> int:
        return sum(len(s.narration.split()) for s in self.scenes)


class AiScript(BaseModel):
    """The part of `Script` the AI writes (the schema of the forced tool call)."""

    title: str
    hook: str
    scenes: list[Scene]
    cta: Cta
    captions: dict[str, str]
    hashtags: list[str] = Field(default_factory=list)

    def to_script(self, brief: Brief) -> Script:
        return Script(
            template=brief.template, campaign=brief.campaign, voices=brief.voices, items=brief.items, shots=brief.shots,
            **self.model_dump(),
        )

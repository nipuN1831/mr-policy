import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_JUDGEMENT_PATTERN = re.compile(
    r"\b(?:corrupt|criminal|best|worst|honest|dishonest|incompetent|good|bad)\b",
    re.IGNORECASE,
)
HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_.]{1,40}$")
ALLOWED_PLATFORMS = ("x", "facebook", "instagram")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    url: str
    title: str
    as_of: str
    checked: bool = True
    grounded: bool = False

    @field_validator("url")
    @classmethod
    def https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("source urls must use https")
        return value

    @field_validator("as_of")
    @classmethod
    def iso_date(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("as_of must be YYYY-MM-DD")
        return value


class Fact(Strict):
    label: str
    value: str
    source: Source
    also: list[Source] = Field(default_factory=list)

    @field_validator("value", "label")
    @classmethod
    def no_judgement(cls, value: str) -> str:
        match = _JUDGEMENT_PATTERN.search(value)
        if match:
            raise ValueError(f"facts must be neutral; found {match.group()!r}")
        return value


class Helpline(Strict):
    name: str
    number: str
    hours: str = ""


class Tier(Strict):
    id: str
    name: str
    controls: list[str] = Field(min_length=1)
    note: str = ""
    source: Source


class Problem(Strict):
    id: str
    title: str
    keywords: list[str] = Field(min_length=1)
    first_body: str
    steps: list[str] = Field(min_length=1)
    helplines: list[Helpline] = Field(default_factory=list)
    portal: str = ""
    legal_basis: str = ""
    verified: bool = True
    unverified_parts: list[str] = Field(default_factory=list)
    source: Source

    @model_validator(mode="after")
    def unverified_needs_detail(self) -> "Problem":
        if not self.verified and not self.unverified_parts:
            raise ValueError(f"problem {self.id} is unverified but names no unverified parts")
        return self


class Right(Strict):
    id: str
    title: str
    summary: str
    how_to_use: str
    law: str = ""
    source: Source


class Representative(Strict):
    id: str
    name: str
    role: str
    body: str
    region: str
    constituency: str
    party: str = ""
    terms: int | None = None
    fictional: bool = True
    handles: dict[str, str] = Field(default_factory=dict)
    record: list[Fact] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("handles")
    @classmethod
    def usernames_only(cls, value: dict[str, str]) -> dict[str, str]:
        for platform, handle in value.items():
            if platform not in ALLOWED_PLATFORMS:
                raise ValueError(f"unsupported platform {platform!r}")
            if not HANDLE_PATTERN.fullmatch(handle):
                raise ValueError("handles must be bare usernames, not links or text")
        return value

    @model_validator(mode="after")
    def real_people_need_checked_sources(self) -> "Representative":
        if not self.fictional:
            if not self.record or not all(fact.source.checked or fact.source.grounded for fact in self.record):
                raise ValueError("a real person needs a record in which every fact has a checked or search-grounded source")
        return self


class Scheme(Strict):
    id: str
    name: str
    summary: str
    policy_text: str
    source: Source


class UpcomingPolicy(Strict):
    id: str
    title: str
    summary: str
    status: Literal["proposed", "passed", "in_force", "under_review"]
    expected_date: str = ""
    affects_you_if: str = ""
    projected_impacts: list[str] = Field(default_factory=list)
    source: Source


class CountryPack(Strict):
    code: str
    name: str
    disclaimer: str
    tiers: list[Tier]
    problems: list[Problem]
    rights: list[Right]
    representatives: list[Representative]
    schemes: list[Scheme] = Field(default_factory=list)
    upcoming_policies: list[UpcomingPolicy] = Field(default_factory=list)
    status: Literal["verified", "partial"] = "partial"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self) -> "CountryPack":
        for label, items in (
            ("problem", self.problems),
            ("representative", self.representatives),
            ("tier", self.tiers),
            ("right", self.rights),
        ):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} ids")
        return self

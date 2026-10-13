import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from pydantic import ValidationError

from policy_wind_tunnel.agents.llm import DEFAULT_MODEL
from policy_wind_tunnel.civic.models import ALLOWED_PLATFORMS, HANDLE_PATTERN, Fact, Representative, Source

MAX_PEOPLE = 8
MAX_BODIES = 8
MAX_FACTS = 8
NOTICE = (
    "Live web search by Gemini, not reviewed by a person. Check the sources before relying on anything. "
    "Facts only: no scores, no rankings, not an endorsement and not voting advice."
)
SENSITIVE_LABEL = re.compile(
    r"phone|mobile|address|birth|\bdob\b|e-?mail|asset|criminal|net worth|wealth|\bfir\b|salary|income|affidavit|religion|caste|family",
    re.IGNORECASE,
)
JUDGEMENT_QUESTION = re.compile(
    r"\b(corrupt\w*|best|worst|rank\w*|honest\w*|dishonest\w*|criminal\w*|incompetent|better than|vote for|should i vote|good|bad|trust\w*)\b",
    re.IGNORECASE,
)
DOMAIN = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")
LEVELS = ("local", "regional", "national")


class ResearchRefused(Exception):
    pass


@dataclass
class SearchResult:
    text: str
    sources: list[dict[str, str]] = field(default_factory=list)


class Searcher(Protocol):
    def search(self, prompt: str) -> SearchResult: ...


class GeminiSearcher:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    def search(self, prompt: str) -> SearchResult:
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=0.0,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        response = self._get_client().models.generate_content(model=self.model, contents=prompt, config=config)
        return SearchResult(response.text or "", _grounding_sources(response))


def _grounding_sources(response: Any) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for candidate in getattr(response, "candidates", None) or []:
        metadata = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(metadata, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            if web is None or not getattr(web, "uri", None):
                continue
            title = getattr(web, "title", None) or getattr(web, "domain", None) or ""
            sources.append({"url": web.uri, "title": title})
    return sources


def refuse_if_judgement(text: str) -> None:
    if JUDGEMENT_QUESTION.search(text):
        raise ResearchRefused(
            "This tool shows facts about where you live and who represents it. "
            "It does not rate, rank or comment on any person."
        )


def _clean_domain(value: str) -> str:
    return value.lower().removeprefix("www.")


def _grounded_domains(sources: list[dict[str, str]]) -> set[str]:
    domains = set()
    for source in sources:
        title = _clean_domain((source.get("title") or "").strip())
        if DOMAIN.fullmatch(title):
            domains.add(title)
    return domains


def _matching_domain(url: str, domains: set[str]) -> str:
    if not url.startswith("https://"):
        return ""
    host = _clean_domain(urlparse(url).hostname or "")
    for domain in domains:
        if host == domain or host.endswith("." + domain):
            return domain
    return ""


def _parse(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _short(value: Any, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, (str, int)) else ""


def _grounded_source(url: str, domain: str, as_of: str) -> Source:
    return Source(url=url, title=domain, as_of=as_of, checked=False, grounded=True)


def _clean_fact(raw: Any, domains: set[str], as_of: str) -> Fact | None:
    if not isinstance(raw, dict):
        return None
    label, value, url = _short(raw.get("label"), 60), _short(raw.get("value"), 300), _short(raw.get("source_url"), 500)
    if not label or not value or SENSITIVE_LABEL.search(label):
        return None
    domain = _matching_domain(url, domains)
    if not domain:
        return None
    try:
        return Fact(label=label, value=value, source=_grounded_source(url, domain, as_of))
    except ValidationError:
        return None


def _clean_handles(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        platform: handle
        for platform, handle in raw.items()
        if platform in ALLOWED_PLATFORMS and isinstance(handle, str) and HANDLE_PATTERN.fullmatch(handle)
    }


def _clean_person(raw: Any, index: int, country: str, place: str, domains: set[str], as_of: str) -> tuple[Representative | None, int]:
    if not isinstance(raw, dict) or not _short(raw.get("name"), 120):
        return None, 1
    facts_raw = raw.get("facts") if isinstance(raw.get("facts"), list) else []
    facts = [fact for fact in (_clean_fact(item, domains, as_of) for item in facts_raw[:MAX_FACTS]) if fact]
    discarded = len(facts_raw[:MAX_FACTS]) - len(facts)
    if not facts:
        return None, discarded + 1
    terms = raw.get("terms")
    rep = Representative(
        id=f"live-{index}",
        name=_short(raw.get("name"), 120),
        role=_short(raw.get("role"), 120) or "Representative",
        body=_short(raw.get("body"), 120),
        region=country,
        constituency=_short(raw.get("constituency"), 120) or place,
        party=_short(raw.get("party"), 120),
        terms=terms if isinstance(terms, int) and 0 <= terms <= 40 else None,
        fictional=False,
        handles=_clean_handles(raw.get("handles")),
        record=facts,
        links={f"Source {n}": fact.source.url for n, fact in enumerate(facts[:3], start=1)},
    )
    return rep, discarded


PERSON_PROMPT = """Use web search to find the CURRENT elected representatives for this place.
Country: {country}
Place: {place}

Return ONLY one JSON object, with no commentary, in this shape:
{{"representatives": [{{"name": "", "role": "", "body": "", "constituency": "", "party": "", "terms": 0,
 "facts": [{{"label": "", "value": "", "source_url": ""}}],
 "handles": {{"x": "", "facebook": "", "instagram": ""}}}}]}}

Rules:
- Use only what you found in official or reputable pages. Do not guess and do not fill gaps from memory.
- Every fact needs the exact page it came from in source_url. If you cannot name the page, leave the fact out.
- Facts must be neutral and checkable: offices held, committee memberships, bills introduced, earlier posts with dates, terms served.
- Do not include phone numbers, addresses, dates of birth, emails, assets, criminal cases, family details or any opinion, praise or criticism.
- handles must be bare usernames of OFFICIAL accounts only, without links or @. Leave them out if you are not sure.
- At most {limit} people. If you find nobody, return {{"representatives": []}}."""

BODY_PROMPT = """Use web search to find which government bodies decide everyday matters for this place.
Country: {country}
Place: {place}

Return ONLY one JSON object, with no commentary, in this shape:
{{"bodies": [{{"name": "", "level": "local|regional|national", "handles": ["", ""], "source_url": "", "contact_url": ""}}]}}

Rules:
- Use only what you found in official pages. Do not guess and do not fill gaps from memory.
- handles lists the everyday matters that body is responsible for, in plain words.
- source_url is the exact page that says so. If you cannot name the page, leave the body out.
- contact_url is the official page to contact them, or empty.
- Do not include opinions or ratings. At most {limit} bodies. If you find nothing, return {{"bodies": []}}."""


def lookup_representatives(searcher: Searcher, country: str, place: str, as_of: str) -> dict[str, Any]:
    result = searcher.search(PERSON_PROMPT.format(country=country, place=place, limit=MAX_PEOPLE))
    domains = _grounded_domains(result.sources)
    raw_people = _parse(result.text).get("representatives")
    raw_people = raw_people if isinstance(raw_people, list) else []
    people: list[dict[str, Any]] = []
    dropped = max(0, len(raw_people) - MAX_PEOPLE)
    for index, raw in enumerate(raw_people[:MAX_PEOPLE], start=1):
        person, discarded = _clean_person(raw, index, country, place, domains, as_of)
        dropped += discarded
        if person:
            people.append(person.model_dump())
    return {"representatives": people, "dropped": dropped, "notice": NOTICE}


def _clean_body(raw: Any, domains: set[str], as_of: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not _short(raw.get("name"), 120):
        return None
    url = _short(raw.get("source_url"), 500)
    domain = _matching_domain(url, domains)
    handles = [_short(item, 120) for item in raw.get("handles", []) if isinstance(item, str)] if isinstance(raw.get("handles"), list) else []
    if not domain or not [h for h in handles if h]:
        return None
    contact = _short(raw.get("contact_url"), 500)
    level = _short(raw.get("level"), 20).lower()
    return {
        "name": _short(raw.get("name"), 120),
        "level": level if level in LEVELS else "other",
        "handles": [h for h in handles if h][:MAX_FACTS],
        "source": _grounded_source(url, domain, as_of).model_dump(),
        "contact_url": contact if contact.startswith("https://") else "",
    }


def lookup_government(searcher: Searcher, country: str, place: str, as_of: str) -> dict[str, Any]:
    result = searcher.search(BODY_PROMPT.format(country=country, place=place, limit=MAX_BODIES))
    domains = _grounded_domains(result.sources)
    raw_bodies = _parse(result.text).get("bodies")
    raw_bodies = raw_bodies if isinstance(raw_bodies, list) else []
    bodies = [body for body in (_clean_body(raw, domains, as_of) for raw in raw_bodies[:MAX_BODIES]) if body]
    return {"bodies": bodies, "dropped": len(raw_bodies[:MAX_BODIES]) - len(bodies), "notice": NOTICE}

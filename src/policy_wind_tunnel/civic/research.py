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
    "Live web search by Gemini, not reviewed by a person. The pages listed support the person's entry as a whole, "
    "not each sentence, so open them and check before relying on anything. "
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
PRAISE = re.compile(
    r"\b(pivotal|instrumental|key role|leading (figure|voice)|credited with|transform\w*|renowned|prominent|influential|"
    r"outstanding|successful|visionary|trailblaz\w*|pioneer\w*|rising star|stalwart|veteran)\b",
    re.IGNORECASE,
)
SOCIAL_AND_AGGREGATORS = frozenset({
    "facebook.com", "instagram.com", "youtube.com", "x.com", "twitter.com", "linktr.ee", "tiktok.com", "threads.net",
    "linkedin.com", "t.me", "whatsapp.com", "indialeader.com", "indiavotekar.com", "bharatpedia.org", "kiddle.co", "gasa.org",
})
REPUTABLE = frozenset({
    "wikipedia.org", "channelnewsasia.com", "straitstimes.com", "thehindu.com", "indianexpress.com", "hindustantimes.com",
    "timesofindia.indiatimes.com", "livemint.com", "reuters.com", "bbc.com", "aninews.in", "ptinews.com", "prsindia.org",
    "myneta.info", "mothership.sg", "todayonline.com", "abc.net.au", "theguardian.com", "nas.gov.sg",
    "sansad.in", "eci.gov.in", "vidhansabha.gov.in", "ndtv.com", "theprint.in", "scroll.in", "wire.in",
    "tribuneindia.com", "deccanherald.com", "newindianexpress.com", "business-standard.com",
})
ASPIRATION = re.compile(
    r"\b(aims?|believes?|committed|dedicat\w*|passion\w*|strives?|promis\w*|vision|aspir\w*|hopes?|wants?|seeks?|"
    r"known for|widely|respected|beloved|tireless|champion\w*|advocate\w*|cares?|caring|loves?|dream\w*|mission)\b",
    re.IGNORECASE,
)
CHECKABLE = re.compile(
    r"\b(19|20)\d{2}\b|\b(elected|appointed|served|serves|chair\w*|member|minister|speaker|deputy|director|ceo|president|"
    r"secretary|advisor|adviser|head|leader|introduced|tabled|sponsored|board|committee|council)\b",
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
    supports: list[dict[str, Any]] = field(default_factory=list)


class Searcher(Protocol):
    def search(self, prompt: str) -> SearchResult: ...

    def structure(self, prompt: str) -> str: ...


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
        return SearchResult(response.text or "", _grounding_sources(response), _grounding_supports(response))

    def structure(self, prompt: str) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
        response = self._get_client().models.generate_content(model=self.model, contents=prompt, config=config)
        return response.text or ""


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


def _grounding_supports(response: Any) -> list[dict[str, Any]]:
    supports: list[dict[str, Any]] = []
    for candidate in getattr(response, "candidates", None) or []:
        metadata = getattr(candidate, "grounding_metadata", None)
        for support in getattr(metadata, "grounding_supports", None) or []:
            segment = getattr(support, "segment", None)
            start = getattr(segment, "start_index", None) or 0
            end = getattr(segment, "end_index", None)
            if end is None:
                continue
            supports.append({"start": start, "end": end, "indices": list(getattr(support, "grounding_chunk_indices", None) or [])})
    return supports


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


def _tidy(value: str, limit: int = 160) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    first = re.match(r".{20,%d}?[.!?](?=\s|$)" % limit, value)
    if first:
        return first.group(0)
    return value[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"


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


HEADING = re.compile(r"^\s*(?:#+\s*)?\**\s*\d+[.)]\s*(?P<name>[^*\n]+?)\s*\**\s*$", re.MULTILINE)
FACT_SECTIONS = {"facts": "Fact", "terms served": "Terms served", "terms": "Terms served"}
MAX_SOURCES_PER_FACT = 4
MIN_SUPPORT_OVERLAP = 20


def _blocks(text: str) -> list[tuple[str, int, int]]:
    headings = list(HEADING.finditer(text))
    return [
        (m.group("name").strip(), m.start(), headings[i + 1].start() if i + 1 < len(headings) else len(text))
        for i, m in enumerate(headings)
    ]


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 1}


def _person_block(text: str, name: str) -> tuple[int, int] | None:
    wanted = _name_tokens(name)
    best, best_score = None, 0
    for heading, start, end in _blocks(text):
        have = _name_tokens(heading)
        overlap = len(wanted & have)
        if overlap >= 2 and overlap / max(1, min(len(wanted), len(have))) >= 0.6 and overlap > best_score:
            best, best_score = (start, end), overlap
    return best


def _grounded_domain(source: dict[str, str]) -> str:
    title = _clean_domain((source.get("title") or "").strip())
    return title if DOMAIN.fullmatch(title) else ""


def _rank(source: dict[str, str]) -> int:
    domain = _grounded_domain(source)
    if domain.endswith((".gov", ".edu")) or ".gov." in domain or domain.endswith((".gov.sg", ".gov.in", ".nic.in", ".gov.au", ".go.id", ".gov.ph")):
        return 0
    if domain in REPUTABLE:
        return 1
    return 2


def _usable(source: dict[str, str]) -> bool:
    return bool(_grounded_domain(source)) and _grounded_domain(source) not in SOCIAL_AND_AGGREGATORS


def _person_sources(result: SearchResult, name: str) -> list[dict[str, str]]:
    block = _person_block(result.text, name)
    if block is None:
        return []
    start, end = block
    seen: dict[str, dict[str, str]] = {}
    for support in result.supports:
        overlap = min(support["end"], end) - max(support["start"], start)
        if overlap < MIN_SUPPORT_OVERLAP:
            continue
        for index in support["indices"]:
            if 0 <= index < len(result.sources):
                source = result.sources[index]
                if _usable(source) and source["url"] not in seen:
                    seen[source["url"]] = source
    ranked = sorted(seen.values(), key=lambda source: (_rank(source), _grounded_domain(source)))
    return ranked[:MAX_SOURCES_PER_FACT]


SECTION_LINE = re.compile(r"^(?P<indent>\s*)[*\-•]\s+\*\*(?P<title>[^*:]+?)\s*:?\*\*\s*:?\s*(?P<rest>.*)$")
BULLET_LINE = re.compile(r"^(?P<indent>\s*)[*\-•]\s+(?P<text>.+)$")


def _clean_text(value: str) -> str:
    return re.sub(r"[*_`]", "", value).strip()


def _block_bullets(text: str, sections: dict[str, str] | None = None) -> list[tuple[str, str]]:
    wanted = FACT_SECTIONS if sections is None else sections
    bullets: list[tuple[str, str]] = []
    section = ""
    for line in text.splitlines():
        top = SECTION_LINE.match(line)
        if top and len(top.group("indent")) < 4:
            section = top.group("title").strip().lower()
            rest = _clean_text(top.group("rest"))
            if rest and section in wanted:
                bullets.append((wanted[section], rest))
            continue
        nested = BULLET_LINE.match(line)
        if nested and len(nested.group("indent")) >= 4 and section in wanted:
            bullets.append((wanted[section], _clean_text(nested.group("text"))))
    return bullets


FIELD_LINE = re.compile(r"^\s*[*\-•]\s+\*\*(?P<key>[^*:]+?)\s*:?\*\*\s*:?\s*(?P<value>.+)$")
PLATFORM_WORDS = {"x": ("twitter", "x (", "x.com", " x "), "facebook": ("facebook",), "instagram": ("instagram",)}
NOT_LISTED = re.compile(r"\bnot (explicitly |officially )?(listed|available|found|provided)\b|\bnone\b|\bn/a\b|\bunknown\b", re.IGNORECASE)


def _block_text(result: SearchResult, name: str) -> str:
    block = _person_block(result.text, name)
    return result.text[block[0]:block[1]] if block else ""


def _block_field(text: str, *keys: str) -> str:
    for line in text.splitlines():
        match = FIELD_LINE.match(line)
        if match and match.group("key").strip().lower() in keys and len(line) - len(line.lstrip()) < 4:
            return _clean_text(match.group("value"))
    return ""


def _listed_platforms(text: str) -> set[str]:
    line = _block_field(text, "official social media", "social media", "official accounts").lower()
    if not line or NOT_LISTED.search(line):
        return set()
    padded = f" {line} "
    return {platform for platform, words in PLATFORM_WORDS.items() if any(word in padded for word in words)}


def _notes_facts(result: SearchResult, name: str, sources: list[dict[str, str]], as_of: str) -> list[Fact]:
    block = _person_block(result.text, name)
    if block is None or not sources:
        return []
    primary, *rest = sources
    facts: list[Fact] = []
    for label, value in _block_bullets(result.text[block[0]:block[1]]):
        if not value or SENSITIVE_LABEL.search(value[:80]) or JUDGEMENT_QUESTION.search(value):
            continue
        if ASPIRATION.search(value) or PRAISE.search(value) or not CHECKABLE.search(value):
            continue
        try:
            facts.append(Fact(
                label=label,
                value=value[:300],
                source=_grounded_source(primary["url"], _grounded_domain(primary), as_of),
                also=[_grounded_source(o["url"], _grounded_domain(o), as_of) for o in rest],
            ))
        except ValidationError:
            continue
        if len(facts) >= MAX_FACTS:
            break
    return facts


def _clean_person(raw: Any, index: int, country: str, place: str, domains: set[str], as_of: str, result: SearchResult | None = None) -> tuple[Representative | None, int]:
    if not isinstance(raw, dict) or not _short(raw.get("name"), 120):
        return None, 1
    facts_raw = raw.get("facts") if isinstance(raw.get("facts"), list) else []
    facts = [fact for fact in (_clean_fact(item, domains, as_of) for item in facts_raw[:MAX_FACTS]) if fact]
    discarded = len(facts_raw[:MAX_FACTS]) - len(facts)
    if not facts and result is not None:
        sources = _person_sources(result, _short(raw.get("name"), 120))
        facts = _notes_facts(result, _short(raw.get("name"), 120), sources, as_of)
    if not facts:
        return None, discarded + 1
    notes = _block_text(result, _short(raw.get("name"), 120)) if result is not None else ""
    listed = _listed_platforms(notes)
    handles = {platform: handle for platform, handle in _clean_handles(raw.get("handles")).items() if platform in listed}
    rep = Representative(
        id=f"live-{index}",
        name=_short(raw.get("name"), 120),
        role=_tidy(_block_field(notes, "role") or "Representative", 120),
        body=_tidy(_block_field(notes, "body"), 120),
        region=country,
        constituency=_short(raw.get("constituency"), 120) or place,
        party=_tidy(_block_field(notes, "party"), 120),
        terms=None,
        fictional=False,
        handles=handles,
        record=facts,
        links={f"Source {n}": fact.source.url for n, fact in enumerate(facts[:3], start=1)},
    )
    return rep, discarded


PERSON_SEARCH = """Using web search, find the CURRENT elected representatives for this place.
Country: {country}
Place: {place}

For India, look for:
- Member of Parliament (Lok Sabha) for the parliamentary constituency — find on sansad.in or prsindia.org/mptrack
- Member of Legislative Assembly (MLA) for the state assembly constituency — find on the state Vidhan Sabha website
- If a village or block: Sarpanch or Gram Panchayat President — find on the state panchayat portal or egramswaraj.gov.in
- If urban: Mayor or Ward Councillor — find on the municipal body website

For each person give their name, role, body, party, terms served, and up to {facts} neutral, checkable facts such as offices held,
committee memberships, bills introduced, or earlier posts with dates. Cite the official page for every fact.
Prefer sources: sansad.in, prsindia.org, myneta.info, eci.gov.in, thehindu.com, indianexpress.com, state Vidhan Sabha official sites.
Also give their official social media usernames if an official page lists them.
Use only what you find in official or reputable pages. Do not guess and do not fill gaps from memory.
Do not include phone numbers, addresses, dates of birth, emails, assets, criminal cases, family details, or any opinion, praise or criticism.
List at most {limit} people. If you find nobody, say so."""

PERSON_STRUCTURE = """Convert the research notes below into one JSON object. Add nothing that is not in the notes.

Notes:
{notes}

Pages the search actually used (the only sites you may cite): {domains}

Return ONLY JSON in this shape:
{{"representatives": [{{"name": "", "role": "", "body": "", "constituency": "", "party": "", "terms": 0,
 "facts": [{{"label": "", "value": "", "source_url": ""}}],
 "handles": {{"x": "", "facebook": "", "instagram": ""}}}}]}}

Rules:
- Do not add facts, people or links that are not in the notes. Use only the notes.
- source_url must be an https page on one of the sites listed above. If a fact has no such page, leave the fact out.
- handles are bare usernames of official accounts only, without links or @. Leave them out if unsure.
- Do not include phone numbers, addresses, dates of birth, emails, assets, criminal cases, family details or any opinion.
- If the notes name nobody, return {{"representatives": []}}."""

BODY_SEARCH = """Using web search, find which government bodies decide everyday matters for this place.
Country: {country}
Place: {place}

Number each body as a heading like **1. Name**. Under it give: Level (local, regional or national); Responsible for (one bullet per everyday matter, plain words);
Contact (bullets: Website, Phone, Hours — only those on an official page); Summary (one sentence). Cite the official page that says what it is responsible for.
Use only what you find in official pages. Do not guess and do not fill gaps from memory. Do not include opinions or ratings.
List at most {limit} bodies. If you find nothing, say so."""

BODY_STRUCTURE = """Convert the research notes below into one JSON object. Add nothing that is not in the notes.

Notes:
{notes}

Pages the search actually used (the only sites you may cite): {domains}

Return ONLY JSON in this shape:
{{"bodies": [{{"name": "", "level": "local|regional|national", "handles": ["", ""], "source_url": "", "contact_url": ""}}]}}

Rules:
- Do not add bodies or links that are not in the notes. Use only the notes.
- source_url must be an https page on one of the sites listed above. If a body has no such page, leave it out.
- contact_url is an https official page for contact, or empty.
- If the notes name no body, return {{"bodies": []}}."""


def _two_step(searcher: Searcher, search_prompt: str, structure_prompt: str) -> tuple[str, set[str], SearchResult]:
    result = searcher.search(search_prompt)
    domains = _grounded_domains(result.sources)
    if not domains:
        return "", domains, result
    notes = result.text[:12000]
    return searcher.structure(structure_prompt.format(notes=notes, domains=", ".join(sorted(domains)))), domains, result


def lookup_representatives(searcher: Searcher, country: str, place: str, as_of: str) -> dict[str, Any]:
    text, domains, result = _two_step(
        searcher,
        PERSON_SEARCH.format(country=country, place=place, limit=MAX_PEOPLE, facts=MAX_FACTS),
        PERSON_STRUCTURE,
    )
    raw_people = _parse(text).get("representatives")
    raw_people = raw_people if isinstance(raw_people, list) else []
    people: list[dict[str, Any]] = []
    left_out: list[str] = []
    dropped = max(0, len(raw_people) - MAX_PEOPLE)
    for index, raw in enumerate(raw_people[:MAX_PEOPLE], start=1):
        person, discarded = _clean_person(raw, index, country, place, domains, as_of, result)
        dropped += discarded
        if person:
            people.append(person.model_dump())
        elif isinstance(raw, dict) and _short(raw.get("name"), 120) and _person_block(result.text, _short(raw.get("name"), 120)):
            left_out.append(_short(raw.get("name"), 120))
    return {"representatives": people, "dropped": dropped, "left_out": left_out, "notice": NOTICE}


BODY_SECTIONS = {"responsible for": "handles", "responsibilities": "handles", "contact": "contact"}
PHONE = re.compile(r"[+()\d][\d\s().+-]{4,}")
URL = re.compile(r"https://[^\s)>\]]+")


def _contact_details(bullets: list[tuple[str, str]], domains: set[str], fallback_url: str) -> dict[str, str]:
    found = {"website": "", "phone": "", "hours": ""}
    for kind, text in bullets:
        if kind != "contact" or ":" not in text:
            continue
        key, value = (part.strip() for part in text.split(":", 1))
        key = key.lower()
        if key in ("phone", "telephone", "hotline", "tel") and not found["phone"]:
            if PHONE.fullmatch(value) and sum(c.isdigit() for c in value) >= 6:
                found["phone"] = value
        elif key in ("hours", "opening hours", "operating hours") and not found["hours"]:
            found["hours"] = _tidy(value, 120)
        elif key in ("website", "web", "url", "official page") and not found["website"]:
            link = URL.search(value)
            if link and _matching_domain(link.group(0), domains):
                found["website"] = link.group(0).rstrip(".,")
    if not found["website"] and fallback_url and _matching_domain(fallback_url, domains):
        found["website"] = fallback_url
    return found


def _clean_body(raw: Any, domains: set[str], as_of: str, result: SearchResult | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not _short(raw.get("name"), 120):
        return None
    name = _short(raw.get("name"), 120)
    url = _short(raw.get("source_url"), 500)
    domain = _matching_domain(url, domains)
    model_handles = [_tidy(item) for item in raw.get("handles", []) if isinstance(item, str)] if isinstance(raw.get("handles"), list) else []
    block = _block_text(result, name) if result else ""
    bullets = _block_bullets(block, BODY_SECTIONS) if block else []
    noted = [_tidy(text) for kind, text in bullets if kind == "handles" and text]
    handles = noted or model_handles
    if not domain or not [h for h in handles if h]:
        return None
    contact = _short(raw.get("contact_url"), 500)
    contact = contact if contact.startswith("https://") else ""
    level = _short(raw.get("level"), 20).lower()
    return {
        "name": name,
        "level": level if level in LEVELS else "other",
        "handles": [h for h in handles if h][:MAX_FACTS],
        "summary": _tidy(_block_field(block, "summary", "about", "description"), 240) if block else "",
        "contact": _contact_details(bullets, domains, contact),
        "source": _grounded_source(url, domain, as_of).model_dump(),
        "contact_url": contact,
    }


def lookup_government(searcher: Searcher, country: str, place: str, as_of: str) -> dict[str, Any]:
    text, domains, result = _two_step(searcher, BODY_SEARCH.format(country=country, place=place, limit=MAX_BODIES), BODY_STRUCTURE)
    raw_bodies = _parse(text).get("bodies")
    raw_bodies = raw_bodies if isinstance(raw_bodies, list) else []
    bodies = [body for body in (_clean_body(raw, domains, as_of, result) for raw in raw_bodies[:MAX_BODIES]) if body]
    return {"bodies": bodies, "dropped": len(raw_bodies[:MAX_BODIES]) - len(bodies), "notice": NOTICE}

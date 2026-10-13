import json

import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.civic.research import (
    GeminiSearcher,
    ResearchRefused,
    SearchResult,
    lookup_government,
    lookup_representatives,
    refuse_if_judgement,
)
from policy_wind_tunnel.service.app import create_app

SOURCES = [
    {"url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "title": "parliament.gov.sg"},
    {"url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/def", "title": "prsindia.org"},
]


class FakeSearcher:
    def __init__(self, text, sources=SOURCES):
        self.text, self.sources, self.prompts, self.structured = text, sources, [], []

    def search(self, prompt):
        self.prompts.append(prompt)
        return SearchResult(self.text, list(self.sources))

    def structure(self, prompt):
        self.structured.append(prompt)
        return self.text


def person(**overrides):
    base = {
        "name": "Sample Member",
        "role": "Member of Parliament",
        "body": "Parliament of Singapore",
        "constituency": "Sample GRC",
        "party": "Sample Party",
        "terms": 2,
        "facts": [
            {"label": "Committee", "value": "Finance Committee member", "source_url": "https://www.parliament.gov.sg/mps/sample"},
            {"label": "Bills introduced", "value": "3", "source_url": "https://prsindia.org/mptrack"},
        ],
        "handles": {"x": "sample_member"},
    }
    base.update(overrides)
    return base


def reply(*people):
    return "```json\n" + json.dumps({"representatives": list(people)}) + "\n```"


def lookup(text, **kwargs):
    return lookup_representatives(FakeSearcher(text, **kwargs), "Singapore", "Sample GRC", "2026-10-13")


def test_a_grounded_representative_is_returned_with_sourced_facts():
    result = lookup(reply(person()))
    rep = result["representatives"][0]
    assert rep["name"] == "Sample Member" and rep["fictional"] is False
    assert {f["label"] for f in rep["record"]} == {"Committee", "Bills introduced"}
    assert all(f["source"]["url"].startswith("https://") and f["source"]["as_of"] == "2026-10-13" for f in rep["record"])
    assert rep["handles"] == {}


def test_every_result_says_it_is_live_unreviewed_and_neutral():
    result = lookup(reply(person()))
    notice = result["notice"].lower()
    assert "web search" in notice and "not reviewed by a person" in notice and "check" in notice and "not an endorsement" in notice


def test_facts_whose_source_was_not_in_the_search_results_are_dropped():
    invented = person(facts=[
        {"label": "Committee", "value": "Finance Committee member", "source_url": "https://www.parliament.gov.sg/mps/sample"},
        {"label": "Award", "value": "Won an award", "source_url": "https://madeup.example.com/page"},
    ])
    rep = lookup(reply(invented))["representatives"][0]
    assert [f["label"] for f in rep["record"]] == ["Committee"]


def test_a_person_with_no_sourced_fact_is_dropped():
    nothing = person(facts=[{"label": "Award", "value": "x", "source_url": "https://madeup.example.com"}])
    result = lookup(reply(nothing))
    assert result["representatives"] == [] and result["dropped"] >= 1


def test_no_search_results_means_no_people():
    assert lookup(reply(person()), sources=[])["representatives"] == []


@pytest.mark.parametrize("label", ["Phone", "Home address", "Date of birth", "Email", "Declared assets", "Criminal cases", "Net worth", "FIR count"])
def test_personal_or_sensitive_labels_are_dropped(label):
    sensitive = person(facts=[
        {"label": "Committee", "value": "Finance Committee member", "source_url": "https://www.parliament.gov.sg/mps/sample"},
        {"label": label, "value": "x", "source_url": "https://www.parliament.gov.sg/mps/sample"},
    ])
    rep = lookup(reply(sensitive))["representatives"][0]
    assert [f["label"] for f in rep["record"]] == ["Committee"]


@pytest.mark.parametrize("word", ["corrupt", "best", "worst", "honest", "criminal"])
def test_judgement_words_are_dropped(word):
    loaded = person(facts=[
        {"label": "Committee", "value": "Finance Committee member", "source_url": "https://www.parliament.gov.sg/mps/sample"},
        {"label": "Note", "value": f"A {word} member", "source_url": "https://www.parliament.gov.sg/mps/sample"},
    ])
    rep = lookup(reply(loaded))["representatives"][0]
    assert all(word not in f["value"].lower() for f in rep["record"])


def test_handles_must_be_bare_usernames_on_known_platforms():
    messy = {"x": "https://x.com/sample", "tiktok": "sample", "facebook": "sample.member"}
    searcher = SupportSearcher(supported_result(), people_json_with_handles("Sample Member", messy))
    rep = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"][0]
    assert rep["handles"] == {"facebook": "sample.member"}


def test_unparseable_model_output_gives_an_empty_result_not_a_crash():
    for text in ("", "I could not find anything.", "{not json", '{"representatives": "oops"}'):
        result = lookup(text)
        assert result["representatives"] == [], text


def test_prompt_forbids_inventing_and_asks_for_sources():
    searcher = FakeSearcher(reply(person()))
    lookup_representatives(searcher, "India", "Demo Nagar", "2026-10-13")
    prompt = searcher.prompts[0].lower()
    assert "demo nagar" in prompt and "india" in prompt
    assert "cite" in prompt and "do not guess" in prompt and "do not include" in prompt
    assert "source_url" in searcher.structured[0].lower()


def test_result_count_is_capped():
    many = [person(name=f"Member {i}") for i in range(30)]
    assert len(lookup(reply(*many))["representatives"]) <= 8


def test_government_lookup_returns_bodies_with_sources():
    text = "```json\n" + json.dumps({"bodies": [{
        "name": "Sample Town Council", "level": "local", "handles": ["Estate cleaning", "Lift maintenance"],
        "source_url": "https://www.parliament.gov.sg/page", "contact_url": "https://www.parliament.gov.sg/contact"}]}) + "\n```"
    result = lookup_government(FakeSearcher(text), "Singapore", "Sample GRC", "2026-10-13")
    body = result["bodies"][0]
    assert body["name"] == "Sample Town Council" and body["handles"] == ["Estate cleaning", "Lift maintenance"]
    assert body["source"]["url"].startswith("https://") and "notice" in result


def test_government_lookup_drops_unsourced_bodies():
    text = json.dumps({"bodies": [{"name": "Ghost Council", "level": "local", "handles": ["x"], "source_url": "https://madeup.example.com"}]})
    assert lookup_government(FakeSearcher(text), "Singapore", "Sample GRC", "2026-10-13")["bodies"] == []


@pytest.mark.parametrize("question", ["is my MP corrupt", "Who is the best minister?", "rank the senators", "is he honest?", "should I vote for her"])
def test_judgement_questions_are_refused(question):
    with pytest.raises(ResearchRefused):
        refuse_if_judgement(question)


@pytest.mark.parametrize("question", ["Sample GRC", "Demo Nagar", "Marine Parade", "Pune"])
def test_place_names_are_accepted(question):
    refuse_if_judgement(question)


def test_the_gemini_searcher_reads_grounding_sources_from_the_response():
    class Web:
        def __init__(self, uri, title): self.uri, self.title = uri, title

    class Chunk:
        def __init__(self, uri, title): self.web = Web(uri, title)

    class Meta:
        grounding_chunks = [Chunk("https://r/1", "parliament.gov.sg"), Chunk("https://r/2", "")]

    class Cand:
        grounding_metadata = Meta()

    class Resp:
        text = "hello"
        candidates = [Cand()]

    class Models:
        def generate_content(self, **kwargs):
            self.kwargs = kwargs
            return Resp()

    class Client:
        models = Models()

    searcher = GeminiSearcher(model="gemini-2.5-flash")
    searcher._client = Client()
    result = searcher.search("find things")
    assert result.text == "hello"
    assert result.sources == [{"url": "https://r/1", "title": "parliament.gov.sg"}, {"url": "https://r/2", "title": ""}]
    tools = Client.models.kwargs["config"].tools
    assert tools and tools[0].google_search is not None


@pytest.fixture()
def api():
    searcher = FakeSearcher(reply(person()))
    return TestClient(create_app(llm=object(), searcher=searcher)), searcher


def test_api_reports_whether_live_lookup_is_available():
    assert TestClient(create_app(llm=None)).get("/api/civic/leaders/status").json() == {"live": False}
    assert TestClient(create_app(llm=object(), searcher=FakeSearcher(""))).get("/api/civic/leaders/status").json() == {"live": True}


def test_api_live_lookup_returns_people_and_bodies(api):
    client, _ = api
    body = client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": "Sample GRC"}).json()
    assert body["representatives"][0]["name"] == "Sample Member"
    assert "bodies" in body and "notice" in body


def test_api_refuses_when_live_lookup_is_unavailable():
    response = TestClient(create_app(llm=None)).post("/api/civic/leaders/lookup", json={"country": "sg", "place": "Sample GRC"})
    assert response.status_code == 503 and "gemini" in response.json()["detail"].lower()


def test_api_refuses_judgement_questions_and_unknown_countries(api):
    client, searcher = api
    assert client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": "is my MP corrupt"}).status_code == 422
    assert client.post("/api/civic/leaders/lookup", json={"country": "zz", "place": "Pune"}).status_code == 404
    assert client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": ""}).status_code == 422
    assert searcher.prompts == []


def test_api_can_be_switched_off_with_an_environment_flag(monkeypatch):
    monkeypatch.setenv("PWT_LIVE_LEADERS", "0")
    client = TestClient(create_app(llm=object(), searcher=FakeSearcher(reply(person()))))
    assert client.get("/api/civic/leaders/status").json() == {"live": False}
    assert client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": "Pune"}).status_code == 503


def test_api_caches_repeat_lookups(api):
    client, searcher = api
    client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": "Sample GRC"})
    after_first = len(searcher.prompts)
    assert after_first == 2
    client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": "sample   grc"})
    assert len(searcher.prompts) == after_first
    client.post("/api/civic/leaders/lookup", json={"country": "in", "place": "Sample GRC"})
    assert len(searcher.prompts) == after_first + 2


def test_nothing_the_citizen_types_is_stored_in_the_response_beyond_the_place(api):
    client, _ = api
    body = client.post("/api/civic/leaders/lookup", json={"country": "sg", "place": "Sample GRC"}).json()
    assert body["place"] == "Sample GRC"


class TwoStepSearcher:
    def __init__(self, research_text, json_text, sources=SOURCES):
        self.research_text, self.json_text, self.sources = research_text, json_text, sources
        self.search_prompts, self.structure_prompts = [], []

    def search(self, prompt):
        self.search_prompts.append(prompt)
        return SearchResult(self.research_text, list(self.sources))

    def structure(self, prompt):
        self.structure_prompts.append(prompt)
        return self.json_text


def test_two_step_lookup_uses_the_research_text_and_the_grounded_domains():
    searcher = TwoStepSearcher("Sample Member sits on the Finance Committee (parliament.gov.sg).", reply(person()))
    result = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")
    assert result["representatives"][0]["name"] == "Sample Member"
    assert len(searcher.search_prompts) == 1 and len(searcher.structure_prompts) == 1
    assert "Finance Committee" in searcher.structure_prompts[0]
    assert "parliament.gov.sg" in searcher.structure_prompts[0] and "prsindia.org" in searcher.structure_prompts[0]


def test_the_search_prompt_is_free_text_not_a_json_demand():
    searcher = TwoStepSearcher("text", reply(person()))
    lookup_representatives(searcher, "India", "Demo Nagar", "2026-10-13")
    prompt = searcher.search_prompts[0].lower()
    assert "json" not in prompt and "demo nagar" in prompt and "cite" in prompt


def test_the_structure_prompt_forbids_new_facts_and_other_domains():
    searcher = TwoStepSearcher("text", reply(person()))
    lookup_representatives(searcher, "India", "Demo Nagar", "2026-10-13")
    prompt = searcher.structure_prompts[0].lower()
    assert "only" in prompt and "do not add" in prompt and "source_url" in prompt


def test_structuring_cannot_launder_a_source_that_search_never_returned():
    laundered = person(facts=[{"label": "Committee", "value": "Finance Committee member", "source_url": "https://klamathcounty.org/x"}])
    searcher = TwoStepSearcher("text", reply(laundered), sources=[{"url": "https://r/1", "title": "parliament.gov.sg"}])
    assert lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"] == []


def test_a_search_with_no_grounded_sources_never_calls_the_structuring_step():
    searcher = TwoStepSearcher("text", reply(person()), sources=[])
    assert lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"] == []
    assert searcher.structure_prompts == []


def test_government_lookup_is_also_two_step():
    bodies = json.dumps({"bodies": [{"name": "Sample Council", "level": "local", "handles": ["Estate cleaning"], "source_url": "https://www.parliament.gov.sg/p"}]})
    searcher = TwoStepSearcher("Sample Council handles estate cleaning.", bodies)
    result = lookup_government(searcher, "Singapore", "Sample GRC", "2026-10-13")
    assert result["bodies"][0]["name"] == "Sample Council" and len(searcher.structure_prompts) == 1


def test_gemini_searcher_structure_makes_a_plain_json_call_without_the_search_tool():
    class Resp:
        text = '{"representatives": []}'

    class Models:
        def generate_content(self, **kwargs):
            self.kwargs = kwargs
            return Resp()

    class Client:
        models = Models()

    searcher = GeminiSearcher(model="gemini-test")
    searcher._client = Client()
    assert searcher.structure("turn this into json") == '{"representatives": []}'
    config = Client.models.kwargs["config"]
    assert not config.tools and config.response_mime_type == "application/json"


def supported_result():
    text = (
        "Representatives:\n\n"
        "**1. Sample Member**\n"
        "*   **Role:** Member of Parliament\n"
        "*   **Facts:**\n"
        "    *   Chairs the Finance Committee since 2024.\n"
        "*   **Official Social Media:** X (@sample_member), Facebook (sample.member)\n\n"
        "**2. Other Member**\n"
        "*   **Role:** Member of Parliament\n"
        "*   **Facts:**\n"
        "    *   Deputy Speaker from 2011 to 2016.\n"
        "*   **Official Social Media:** Not listed.\n"
    )
    split = text.index("**2. Other Member**")
    return SearchResult(
        text,
        [{"url": "https://r/1", "title": "parliament.gov.sg"}, {"url": "https://r/2", "title": "wikipedia.org"}, {"url": "https://r/3", "title": "chicagobooth.edu"}],
        supports=[
            {"start": 0, "end": split, "indices": [0, 1]},
            {"start": split, "end": len(text), "indices": [2]},
        ],
    )


class SupportSearcher:
    def __init__(self, result, json_text):
        self.result, self.json_text, self.structure_prompts = result, json_text, []

    def search(self, prompt):
        return self.result

    def structure(self, prompt):
        self.structure_prompts.append(prompt)
        return self.json_text


def people_json(*names):
    return json.dumps({"representatives": [
        {"name": n, "role": "Member of Parliament", "body": "Parliament", "constituency": "Sample GRC", "party": "P", "terms": 1,
         "facts": [], "handles": {}} for n in names]})


def test_a_person_is_kept_when_a_support_span_cites_a_page_for_their_name():
    searcher = SupportSearcher(supported_result(), people_json("Sample Member"))
    rep = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"][0]
    assert rep["name"] == "Sample Member"
    fact = rep["record"][0]
    shown = {fact["source"]["title"]} | {s["title"] for s in fact["also"]}
    assert shown == {"parliament.gov.sg", "wikipedia.org"}
    assert fact["source"]["grounded"] is True and all(s["grounded"] for s in fact["also"])
    assert {fact["source"]["url"]} | {s["url"] for s in fact["also"]} == {"https://r/1", "https://r/2"}


def test_facts_come_from_the_notes_for_that_person_not_from_the_model():
    searcher = SupportSearcher(supported_result(), people_json("Sample Member"))
    rep = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"][0]
    values = " ".join(f["value"] for f in rep["record"])
    assert "Chairs the Finance Committee since 2024" in values and "Deputy Speaker" not in values


def test_a_person_whose_name_is_not_in_any_supported_span_is_dropped():
    searcher = SupportSearcher(supported_result(), people_json("Invented Person"))
    result = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")
    assert result["representatives"] == [] and result["dropped"] >= 1


def test_each_person_gets_only_their_own_sources():
    searcher = SupportSearcher(supported_result(), people_json("Sample Member", "Other Member"))
    people = {p["name"]: p for p in lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"]}
    assert {f["source"]["title"] for f in people["Other Member"]["record"]} == {"chicagobooth.edu"}
    assert "chicagobooth.edu" not in {f["source"]["title"] for f in people["Sample Member"]["record"]}


def test_a_span_with_no_cited_chunk_gives_a_person_no_sources():
    result = supported_result()
    result.supports = [{"start": 0, "end": 10, "indices": []}]
    searcher = SupportSearcher(result, people_json("Sample Member"))
    assert lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"] == []


def test_sensitive_lines_in_the_notes_are_not_turned_into_facts():
    result = supported_result()
    result.text = result.text.replace("    *   Chairs the Finance Committee since 2024.\n", "    *   Chairs the Finance Committee since 2024.\n    *   Phone number 6123 4567.\n    *   Declared assets and net worth are very high.\n")
    searcher = SupportSearcher(result, people_json("Sample Member"))
    rep = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")["representatives"][0]
    text = " ".join(f["value"] for f in rep["record"]).lower()
    assert "chairs the finance committee" in text and "6123" not in text and "net worth" not in text and "assets" not in text


def test_grounding_supports_are_read_from_the_response():
    class Seg:
        def __init__(self, a, b): self.start_index, self.end_index = a, b

    class Sup:
        def __init__(self, a, b, idx): self.segment, self.grounding_chunk_indices = Seg(a, b), idx

    class Web:
        def __init__(self, u, t): self.uri, self.title = u, t

    class Chunk:
        def __init__(self, u, t): self.web = Web(u, t)

    class Meta:
        grounding_chunks = [Chunk("https://r/1", "parliament.gov.sg")]
        grounding_supports = [Sup(0, 12, [0])]

    class Cand:
        grounding_metadata = Meta()

    class Resp:
        text = "Sample Member"
        candidates = [Cand()]

    class Models:
        def generate_content(self, **kwargs): return Resp()

    class Client:
        models = Models()

    searcher = GeminiSearcher(model="gemini-test")
    searcher._client = Client()
    result = searcher.search("find")
    assert result.supports == [{"start": 0, "end": 12, "indices": [0]}]


REAL_NOTES = """The current elected representatives are:

**1. Seah Kian Peng**
*   **Role:** Speaker, Member of Parliament
*   **Party:** People's Action Party (PAP)
*   **Terms Served:**
    *   Member of Parliament from 2006 to 2025.
*   **Facts:**
    *   Elected as Speaker on August 2, 2023.
    *   Chaired the Estimates Committee from 2011 to 2015.
*   **Official Social Media:** Not listed on official pages.

**2. Goh Pei Ming**
*   **Role:** Senior Minister of State
*   **Party:** People's Action Party (PAP)
*   **Facts:**
    *   Serves as Senior Minister of State for Home Affairs.
*   **Official Social Media:** Goh Pei Ming (Facebook)

**3. Diana Pang**
*   **Role:** Member of Parliament
*   **Facts:**
    *   Second vice-chair of a government parliamentary committee as of March 2025.
*   **Official Social Media:** Not explicitly listed.
"""


def real_result(supports=None):
    n = REAL_NOTES
    cut2, cut3 = n.index("**2. Goh"), n.index("**3. Diana")
    return SearchResult(
        n,
        [{"url": "https://r/1", "title": "parliament.gov.sg"}, {"url": "https://r/2", "title": "wikipedia.org"}, {"url": "https://r/3", "title": "channelnewsasia.com"}],
        supports=supports or [
            {"start": 0, "end": cut2, "indices": [0, 1]},
            {"start": cut2, "end": cut3, "indices": [1]},
            {"start": cut3, "end": len(n), "indices": [2]},
        ],
    )


def real_people(*names):
    return json.dumps({"representatives": [
        {"name": n, "role": "MP", "body": "Parliament", "constituency": "Sample GRC", "party": "P", "terms": 1,
         "facts": [], "handles": {}} for n in names]})


def run_real(*names, supports=None):
    searcher = SupportSearcher(real_result(supports), real_people(*names))
    people = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-14")["representatives"]
    return {p["name"]: p for p in people}


def fact_text(person):
    return " | ".join(f"{f['label']}: {f['value']}" for f in person["record"])


def test_each_person_gets_only_facts_from_their_own_numbered_block():
    people = run_real("Seah Kian Peng", "Goh Pei Ming", "Diana Pang")
    assert "Estimates Committee" in fact_text(people["Seah Kian Peng"])
    assert "Estimates Committee" not in fact_text(people["Goh Pei Ming"])
    assert "Home Affairs" in fact_text(people["Goh Pei Ming"]) and "Home Affairs" not in fact_text(people["Seah Kian Peng"])
    assert "vice-chair" in fact_text(people["Diana Pang"]) and "Speaker" not in fact_text(people["Diana Pang"])


def test_a_longer_name_from_structuring_still_finds_the_right_block():
    people = run_real("Diana Pang Li Yen")
    assert "vice-chair" in fact_text(people["Diana Pang Li Yen"])


def test_social_media_lines_are_never_turned_into_facts():
    for person in run_real("Seah Kian Peng", "Goh Pei Ming", "Diana Pang").values():
        assert "social" not in fact_text(person).lower() and "facebook" not in fact_text(person).lower()


def test_role_and_party_lines_are_not_repeated_as_facts():
    text = fact_text(run_real("Seah Kian Peng")["Seah Kian Peng"]).lower()
    assert "role:" not in text and "party:" not in text and "people's action party" not in text


def test_facts_are_the_bullets_under_facts_and_terms_only():
    record = run_real("Seah Kian Peng")["Seah Kian Peng"]["record"]
    assert [f["label"] for f in record] == ["Terms served", "Fact", "Fact"]
    assert record[0]["value"].startswith("Member of Parliament from 2006")


def test_sources_only_come_from_supports_that_overlap_that_persons_block():
    people = run_real("Seah Kian Peng", "Goh Pei Ming", "Diana Pang")
    titles = lambda p: {f["source"]["title"] for f in p["record"]} | {a["title"] for f in p["record"] for a in f["also"]}
    assert titles(people["Seah Kian Peng"]) == {"parliament.gov.sg", "wikipedia.org"}
    assert titles(people["Goh Pei Ming"]) == {"wikipedia.org"}
    assert titles(people["Diana Pang"]) == {"channelnewsasia.com"}


def test_one_persons_handles_never_appear_on_another_person():
    listed = real_result()
    listed.text = listed.text.replace("**Official Social Media:** Not listed on official pages.", "**Official Social Media:** Facebook (seahkianpeng)")
    raw = json.dumps({"representatives": [
        {"name": "Seah Kian Peng", "role": "MP", "body": "P", "constituency": "C", "party": "P", "terms": 1, "facts": [], "handles": {"facebook": "seahkianpeng"}},
        {"name": "Diana Pang", "role": "MP", "body": "P", "constituency": "C", "party": "P", "terms": 1, "facts": [], "handles": {}},
    ]})
    searcher = SupportSearcher(listed, raw)
    people = {p["name"]: p for p in lookup_representatives(searcher, "Singapore", "C", "2026-10-14")["representatives"]}
    assert people["Seah Kian Peng"]["handles"] == {"facebook": "seahkianpeng"}
    assert people["Diana Pang"]["handles"] == {}
    assert "seahkianpeng" not in fact_text(people["Diana Pang"]).lower()


def test_a_person_with_no_overlapping_support_is_dropped_not_given_everyones_sources():
    far = [{"start": 0, "end": 5, "indices": [0, 1, 2]}]
    assert run_real("Goh Pei Ming", supports=far) == {}


def test_the_number_of_sources_per_fact_stays_small():
    for person in run_real("Seah Kian Peng", "Goh Pei Ming", "Diana Pang").values():
        for f in person["record"]:
            assert 1 + len(f["also"]) <= 4


def test_a_support_that_barely_touches_a_block_does_not_count():
    touching = [{"start": 0, "end": 60, "indices": [0, 1]}, {"start": 60, "end": 70, "indices": [2]}]
    assert run_real("Goh Pei Ming", supports=touching) == {}


@pytest.mark.parametrize("statement", [
    "Aims to build a cohesive, people-focused, green, and lively community.",
    "Believes in ensuring families can thrive and no one is left behind.",
    "Is committed to serving residents with dedication.",
    "Passionate about youth development.",
    "Strives to improve the lives of seniors.",
    "Promises to deliver better housing.",
    "Dedicated to the community and widely respected.",
    "Known for a caring approach.",
    "Vision of a vibrant and inclusive neighbourhood.",
])
def test_aims_beliefs_and_promises_are_not_facts(statement):
    result = real_result()
    result.text = result.text.replace("    *   Elected as Speaker on August 2, 2023.\n", f"    *   Elected as Speaker on August 2, 2023.\n    *   {statement}\n")
    searcher = SupportSearcher(result, real_people("Seah Kian Peng"))
    record = lookup_representatives(searcher, "Singapore", "C", "2026-10-14")["representatives"][0]["record"]
    values = " ".join(f["value"] for f in record)
    assert "Elected as Speaker" in values and statement not in values


@pytest.mark.parametrize("statement", [
    "Elected as Speaker on August 2, 2023.",
    "Chaired the Estimates Committee from 2011 to 2015.",
    "Served as Deputy Speaker from October 2011 to January 2016.",
    "Introduced a Private Member's Bill in 2010.",
    "Chairs the Marine Parade Leadership Foundation.",
    "Served over 22 years with NTUC FairPrice, including as Group CEO.",
    "Serves on the board of the Singapore Olympic Foundation.",
])
def test_dated_offices_and_roles_are_kept(statement):
    result = real_result()
    result.text = result.text.replace("    *   Elected as Speaker on August 2, 2023.\n", f"    *   {statement}\n")
    searcher = SupportSearcher(result, real_people("Seah Kian Peng"))
    record = lookup_representatives(searcher, "Singapore", "C", "2026-10-14")["representatives"][0]["record"]
    assert statement in " ".join(f["value"] for f in record)


def result_with_sources(titles, notes_text=None):
    base = real_result()
    base.sources = [{"url": f"https://r/{i}", "title": title} for i, title in enumerate(titles)]
    base.supports = [{"start": 0, "end": base.text.index("**2. Goh"), "indices": list(range(len(titles)))}]
    if notes_text:
        base.text = notes_text
    return base


def kept_titles(titles):
    searcher = SupportSearcher(result_with_sources(titles), real_people("Seah Kian Peng"))
    people = lookup_representatives(searcher, "Singapore", "C", "2026-10-14")["representatives"]
    if not people:
        return None
    record = people[0]["record"]
    return {f["source"]["title"] for f in record} | {a["title"] for f in record for a in f["also"]}


def test_official_and_reputable_sources_are_preferred_over_social_media_and_aggregators():
    shown = kept_titles(["facebook.com", "instagram.com", "indialeader.com", "parliament.gov.sg", "wikipedia.org", "channelnewsasia.com"])
    assert "parliament.gov.sg" in shown and "wikipedia.org" in shown
    assert "facebook.com" not in shown and "instagram.com" not in shown and "indialeader.com" not in shown


def test_a_person_supported_only_by_social_media_is_dropped():
    assert kept_titles(["facebook.com", "instagram.com", "youtube.com", "linktr.ee"]) is None


def test_government_domains_rank_first():
    searcher = SupportSearcher(result_with_sources(["wikipedia.org", "straitstimes.com", "parliament.gov.sg", "pmo.gov.sg"]), real_people("Seah Kian Peng"))
    fact = lookup_representatives(searcher, "Singapore", "C", "2026-10-14")["representatives"][0]["record"][0]
    assert fact["source"]["title"].endswith(".gov.sg")


@pytest.mark.parametrize("statement", [
    "Played a pivotal role in campaigning for BJP in the Balurghat constituency.",
    "Instrumental in delivering the new hospital.",
    "Widely credited with transforming the district.",
    "Is a leading figure in the party.",
    "Played a key role in the 2020 campaign.",
])
def test_praise_is_not_a_fact_even_when_it_has_a_year_or_an_office_word(statement):
    result = real_result()
    result.text = result.text.replace("    *   Elected as Speaker on August 2, 2023.\n", f"    *   Elected as Speaker on August 2, 2023.\n    *   {statement}\n")
    searcher = SupportSearcher(result, real_people("Seah Kian Peng"))
    values = " ".join(f["value"] for f in lookup_representatives(searcher, "Singapore", "C", "2026-10-14")["representatives"][0]["record"])
    assert "Elected as Speaker" in values and statement not in values


def test_the_page_must_say_sources_support_the_person_not_each_sentence():
    from policy_wind_tunnel.civic.research import NOTICE
    assert "person" in NOTICE.lower() and "each sentence" in NOTICE.lower()


def test_names_of_people_who_were_left_out_are_reported():
    searcher = SupportSearcher(supported_result(), people_json("Sample Member", "Invented Person"))
    result = lookup_representatives(searcher, "Singapore", "Sample GRC", "2026-10-13")
    assert [p["name"] for p in result["representatives"]] == ["Sample Member"]
    assert result["left_out"] == []
    assert result["dropped"] >= 1


def test_long_body_responsibilities_are_cut_at_a_sentence_or_word_not_mid_word():
    long = "Promoting social cohesion and active citizenship. The PA brings people of different backgrounds together through community clubs and programmes across the island every single year without fail."
    text = json.dumps({"bodies": [{"name": "Sample Body", "level": "national", "handles": [long], "source_url": "https://www.parliament.gov.sg/p"}]})
    handle = lookup_government(FakeSearcher(text), "Singapore", "C", "2026-10-14")["bodies"][0]["handles"][0]
    assert handle == "Promoting social cohesion and active citizenship." and len(handle) <= 160
    unbroken = "word " * 60
    text = json.dumps({"bodies": [{"name": "B", "level": "local", "handles": [unbroken], "source_url": "https://www.parliament.gov.sg/p"}]})
    cut = lookup_government(FakeSearcher(text), "Singapore", "C", "2026-10-14")["bodies"][0]["handles"][0]
    assert len(cut) <= 160 and cut.endswith("\u2026") and not cut[:-1].endswith("wor")


def people_json_with_handles(name, handles):
    return json.dumps({"representatives": [
        {"name": name, "role": "MP", "body": "P", "constituency": "C", "party": "P", "terms": 1, "facts": [], "handles": handles}]})

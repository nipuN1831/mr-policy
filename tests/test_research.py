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
        self.text, self.sources, self.prompts = text, sources, []

    def search(self, prompt):
        self.prompts.append(prompt)
        return SearchResult(self.text, list(self.sources))


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
    assert rep["handles"] == {"x": "sample_member"}


def test_every_result_says_it_is_live_unreviewed_and_neutral():
    result = lookup(reply(person()))
    notice = result["notice"].lower()
    assert "web search" in notice and "check the sources" in notice and "not an endorsement" in notice


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
    rep = lookup(reply(person(handles={"x": "https://x.com/sample", "tiktok": "sample", "facebook": "sample.member"})))["representatives"][0]
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
    assert "only" in prompt and "source_url" in prompt and "do not" in prompt
    assert "no phone" in prompt or "do not include" in prompt


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

    searcher = GeminiSearcher(model="gemini-3.8-flash")
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

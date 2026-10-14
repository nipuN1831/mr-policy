import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from policy_wind_tunnel import settings
from policy_wind_tunnel.agents.approval import ApprovalError, decide_ambiguity
from policy_wind_tunnel.agents.extractor import ExtractionError
from policy_wind_tunnel.agents.llm import LLM, GeminiLLM
from policy_wind_tunnel.civic import eligibility as civic_eligibility
from policy_wind_tunnel.civic.counterfactual import nearest_changes
from policy_wind_tunnel.civic.lookup import find_problems, find_representatives
from policy_wind_tunnel.civic.packs import available_countries, load_pack
from policy_wind_tunnel.civic.research import (
    GeminiSearcher,
    ResearchRefused,
    lookup_government,
    lookup_representatives,
    refuse_if_judgement,
)
from policy_wind_tunnel.contract.evaluator import ContractError
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.service import orchestrator
from policy_wind_tunnel.simulation.exploratory import run_exploratory
from policy_wind_tunnel.simulation.levers import levers
from policy_wind_tunnel.simulation.scenarios import scenario_by_id
from policy_wind_tunnel.simulation.whatif import ChangeError

STATIC_DIR = Path(__file__).resolve().parent / "static"
_UNSET = object()
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#0b6e7a"/>'
    '<rect x="7" y="9" width="18" height="3" rx="1.5" fill="#fff"/><rect x="7" y="15" width="18" height="3" rx="1.5" fill="#fff"/>'
    '<rect x="7" y="21" width="18" height="3" rx="1.5" fill="#ffd84d"/></svg>'
)


class ExtractRequest(BaseModel):
    policy_text: str
    use_gold: bool = False


class RunRequest(BaseModel):
    target: str
    contract: dict[str, Any] | None = None
    use_gold: bool = False


class WhatIfRequest(BaseModel):
    scenario: str | None = None
    changes: list[dict[str, Any]] | None = None
    population: int = Field(default=2000, ge=100, le=20000)
    contract: dict[str, Any] | None = None
    use_gold: bool = False


class LeversRequest(BaseModel):
    contract: dict[str, Any] | None = None
    use_gold: bool = False


class ExploratoryRequest(BaseModel):
    rule_id: str
    change_factor: float = 1.0
    contract: dict[str, Any] | None = None
    use_gold: bool = False


class CheckRequest(BaseModel):
    inputs: dict[str, Any]


class ChangeRequest(BaseModel):
    inputs: dict[str, Any]
    targets: list[str] | None = None
    lock: list[str] | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    country: str = "in"


class LeaderLookupRequest(BaseModel):
    country: str
    place: str = Field(default="", max_length=120)


class ApproveRequest(BaseModel):
    contract: dict[str, Any]
    ambiguity_id: str
    status: str
    resolution: str | None = None


def llm_from_environment() -> LLM | None:
    return GeminiLLM(settings.model_name()) if settings.credential_mode() != "none" else None


def _load_contract(payload: dict[str, Any] | None, use_gold: bool) -> Contract:
    if payload is None:
        if use_gold:
            return LENDING_CONTRACT
        raise HTTPException(422, detail="supply a contract or set use_gold")
    try:
        return Contract.model_validate(payload)
    except ValidationError as error:
        raise HTTPException(422, detail=error.errors(include_url=False, include_context=False)[:5]) from error


def live_leaders_enabled() -> bool:
    return settings.live_leaders_enabled()


def create_app(llm: Any = _UNSET, searcher: Any = _UNSET) -> FastAPI:
    model = llm_from_environment() if llm is _UNSET else llm
    if searcher is _UNSET:
        searcher = GeminiSearcher(settings.model_name()) if model is not None else None
    lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}
    app = FastAPI(title="Policy Wind Tunnel")

    _CHAT_SYSTEM = (
        "You are Policy Wind Tunnel, a civic information assistant for India and Singapore. "
        "Answer the user's policy question in 2-4 plain sentences. Be factual and cite the relevant law or scheme name. "
        "Then output a JSON object on a new line with these exact keys:\n"
        "  answer: string (under 120 words)\n"
        "  intent: one of scheme_check | problem | rights | representatives | officials_whatif | general\n"
        "  scheme_id: null OR exactly one of: in_caa_2019 | in_pmuy | sg_silver_support\n"
        "  redirect_path: chosen by these rules:\n"
        "    - if scheme_id is not null → always use /citizen (never #decides)\n"
        "    - if intent is problem → /citizen#decides\n"
        "    - if intent is rights → /citizen#rights\n"
        "    - if intent is representatives → /citizen#leaders\n"
        "    - if intent is officials_whatif → /officials\n"
        "    - otherwise → /citizen\n"
        "Never make up statistics or invent sources."
    )
    _CHAT_KEYWORDS = {
        "caa": ("in_caa_2019", "/citizen", "The CAA 2019 fast-tracks citizenship for six religious minorities from Afghanistan, Bangladesh or Pakistan who entered India by 31 Dec 2014, after 5 years of residency. It does not apply to Muslims, Inner Line Permit states, or Sixth Schedule areas. Check your exact eligibility on the next page."),
        "citizenship": ("in_caa_2019", "/citizen", "The Citizenship Amendment Act 2019 covers Hindu, Sikh, Buddhist, Jain, Parsi and Christian applicants from three countries. Entry must be on or before 31 December 2014 and 5 years of residency are required. Check your eligibility with the step-by-step checker."),
        "lpg": ("in_pmuy", "/citizen", "Ujjwala PMUY 2.0 gives a free LPG connection (not the cylinder) to women from poor households with no existing OMC connection. You need to be 18+, have no other LPG connection in the household, and submit a deprivation declaration. Check your eligibility on the next page."),
        "ujjwala": ("in_pmuy", "/citizen", "Ujjwala PMUY 2.0 gives a free LPG connection (not the cylinder) to women from poor households with no existing OMC connection. You need to be 18+, have no other LPG connection in the household, and submit a deprivation declaration."),
        "pmuy": ("in_pmuy", "/citizen", "PM Ujjwala Yojana 2.0 provides free LPG connections to eligible women from poor households. Eligibility requires age 18+, no existing OMC connection in the household, and a deprivation declaration form."),
        "silver support": ("sg_silver_support", "/citizen", "Singapore's Silver Support Scheme provides quarterly cash supplements to elderly lower-income Singaporeans aged 65+. Eligibility depends on household income per person and housing type. Check your exact qualification on the next page."),
        "bank": (None, "/citizen#decides", "For bank complaints, first raise it with the bank and get a reference number. If unresolved after 30 days, file with the RBI Complaint Management System at cms.rbi.org.in. The helpline is 14448, Mon–Sat 8am–10pm."),
        "rti": (None, "/citizen#rights", "The Right to Information Act 2005 lets any citizen request records from public authorities. File at rtionline.gov.in for central bodies. State matters need state portals. The PIO has 30 days to reply."),
        "cpgrams": (None, "/citizen#decides", "CPGRAMS is the central government grievance portal at pgportal.gov.in. It is free. Each ministry has a nodal officer. RTI, sub judice and service matters are out of scope."),
        "complaint": (None, "/citizen#decides", "For central government complaints, use CPGRAMS at pgportal.gov.in. For consumer disputes, call the National Consumer Helpline on 1915. For bank issues, contact the RBI Ombudsman after first raising it with your bank."),
        "rights": (None, "/citizen#rights", "Your key rights include the Right to Information (RTI Act 2005), Consumer Protection (Consumer Protection Act 2019), and Free Legal Services (Legal Services Authorities Act 1987). See the Rights tab for how to use each one."),
        "representative": (None, "/citizen#leaders", "You can look up your Member of Parliament, MLA, or local councillor from the My Area tab. For India, Sansad.in lists Lok Sabha members. The live search uses Gemini to find your area's current representatives."),
        "what if": (None, "/officials", "The Officials page lets you simulate a rule change — re-decide thousands of synthetic applicants and see who moves in or out. Try raising the income floor or changing a residency requirement."),
    }

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        q = request.question.strip().lower()
        if model is not None:
            try:
                import json as _json
                raw = model.generate_json(_CHAT_SYSTEM, f"Country: {request.country}\nQuestion: {request.question}")
                # extract JSON block: last {...} in response
                start = raw.rfind("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    meta = _json.loads(raw[start:end])
                    answer_text = meta.get("answer") or raw[:start].strip()
                    return {
                        "answer": answer_text,
                        "intent": meta.get("intent", "general"),
                        "scheme_id": meta.get("scheme_id"),
                        "redirect_path": meta.get("redirect_path"),
                        "powered_by": "gemini",
                    }
            except Exception:
                pass
        # keyword fallback
        for kw, (scheme_id, path, answer_text) in _CHAT_KEYWORDS.items():
            if kw in q:
                return {"answer": answer_text, "intent": "general", "scheme_id": scheme_id, "redirect_path": path, "powered_by": "fallback"}
        return {
            "answer": "I couldn't find a specific answer for that question. Try browsing the topics below or use the full citizen checker.",
            "intent": "general",
            "scheme_id": None,
            "redirect_path": "/citizen",
            "powered_by": "fallback",
        }

    @app.get("/api/health")
    def health():
        info = settings.describe()
        return {"status": "ok", "llm": model is not None, "model": info["model"], "credentials": info["credentials"]}

    @app.get("/api/demo")
    def demo():
        return orchestrator.demo_payload()

    @app.post("/api/extract")
    def extract(request: ExtractRequest):
        if model is None and not request.use_gold:
            raise HTTPException(503, detail="no language model configured; set use_gold to use the bundled contract")
        try:
            return orchestrator.extraction_payload(request.policy_text, model, request.use_gold)
        except ExtractionError as error:
            raise HTTPException(422, detail={"errors": error.errors}) from error

    @app.post("/api/run")
    def run(request: RunRequest):
        contract = _load_contract(request.contract, request.use_gold)
        try:
            return orchestrator.run_payload(contract, request.target)
        except orchestrator.UnknownTarget as error:
            raise HTTPException(404, detail=f"unknown target {request.target}") from error
        except orchestrator.ContractMismatch as error:
            raise HTTPException(422, detail=str(error)) from error

    @app.post("/api/levers")
    def levers_route(request: LeversRequest):
        return levers(_load_contract(request.contract, request.use_gold))

    @app.post("/api/exploratory")
    def exploratory_route(request: ExploratoryRequest):
        contract = _load_contract(request.contract, request.use_gold)
        try:
            return run_exploratory(contract, rule_id=request.rule_id, change_factor=request.change_factor)
        except Exception as error:
            raise HTTPException(422, detail=str(error)) from error

    @app.post("/api/whatif")
    def whatif(request: WhatIfRequest):
        contract = _load_contract(request.contract, request.use_gold)
        scenario = None
        changes = request.changes
        if request.scenario:
            try:
                scenario = scenario_by_id(request.scenario)
            except KeyError as error:
                raise HTTPException(404, detail=f"unknown scenario {request.scenario}") from error
            changes = scenario.changes
        if not changes:
            raise HTTPException(422, detail="supply a scenario or changes")
        try:
            return orchestrator.whatif_payload(contract, changes, request.population, scenario)
        except (ChangeError, orchestrator.ContractMismatch) as error:
            raise HTTPException(422, detail=str(error)) from error

    @app.post("/api/approve")
    def approve(request: ApproveRequest):
        contract = _load_contract(request.contract, False)
        try:
            updated = decide_ambiguity(contract, request.ambiguity_id, request.status, request.resolution)
        except ApprovalError as error:
            code = 404 if "no ambiguity" in str(error) else 422
            raise HTTPException(code, detail=str(error)) from error
        return {"contract": updated.model_dump()}

    @app.get("/api/benchmark")
    def benchmark():
        return orchestrator.benchmark_payload(LENDING_CONTRACT)

    def _pack(code: str):
        try:
            return load_pack(code)
        except KeyError as error:
            raise HTTPException(404, detail=f"unknown country {code}") from error

    def _scheme_call(scheme_id: str, action):
        try:
            return action()
        except civic_eligibility.UnknownScheme as error:
            raise HTTPException(404, detail=str(error)) from error
        except civic_eligibility.NotCheckable as error:
            raise HTTPException(422, detail=str(error)) from error
        except (ContractError, ValueError) as error:
            raise HTTPException(422, detail=str(error)) from error

    @app.get("/api/civic/countries")
    def civic_countries():
        return available_countries()

    @app.get("/api/civic/countries/{code}")
    def civic_country(code: str):
        pack = _pack(code)
        checkable = {s["id"] for s in civic_eligibility.list_schemes() if s["self_check"]}
        data = pack.model_dump()
        for scheme in data["schemes"]:
            scheme["self_check"] = scheme["id"] in checkable
        return data

    @app.get("/api/civic/countries/{code}/problems")
    def civic_problems(code: str, text: str = ""):
        return {"matches": [p.model_dump() for p in find_problems(_pack(code), text)]}

    @app.get("/api/civic/countries/{code}/representatives")
    def civic_representatives(code: str, constituency: str = ""):
        pack = _pack(code)
        found = find_representatives(pack, constituency) if constituency else pack.representatives
        return {
            "demo": True,
            "notice": "These representatives are fictional demo data. No real person is shown.",
            "representatives": [r.model_dump() for r in found],
        }

    def _live() -> bool:
        return searcher is not None and live_leaders_enabled()

    @app.get("/api/civic/leaders/status")
    def leaders_status():
        return {"live": _live()}

    @app.post("/api/civic/leaders/lookup")
    def leaders_lookup(request: LeaderLookupRequest):
        if not _live():
            raise HTTPException(503, detail="Live lookup needs Gemini to be connected, and is switched off otherwise.")
        pack = _pack(request.country)
        place = " ".join(request.place.split())
        if not place:
            raise HTTPException(422, detail="Enter a place, such as a constituency or town.")
        try:
            refuse_if_judgement(place)
        except ResearchRefused as error:
            raise HTTPException(422, detail=str(error)) from error
        key = (pack.code, place.lower())
        if key not in lookup_cache:
            as_of = datetime.date.today().isoformat()
            try:
                people = lookup_representatives(searcher, pack.name, place, as_of)
                bodies = lookup_government(searcher, pack.name, place, as_of)
            except Exception as error:  # noqa: BLE001 - network and model failures must not become a 500
                raise HTTPException(502, detail=f"The web search did not complete: {type(error).__name__}") from error
            found = {
                "country": pack.code,
                "place": place,
                "representatives": people["representatives"],
                "bodies": bodies["bodies"],
                "dropped": people["dropped"] + bodies["dropped"],
                "left_out": people.get("left_out", []),
                "notice": people["notice"],
                "as_of": as_of,
            }
            if not found["representatives"] and not found["bodies"]:
                return found
            lookup_cache[key] = found
        return lookup_cache[key]

    @app.get("/api/civic/schemes")
    def civic_schemes():
        return civic_eligibility.list_schemes()

    @app.get("/api/civic/schemes/{scheme_id}/form")
    def civic_form(scheme_id: str):
        return _scheme_call(scheme_id, lambda: civic_eligibility.form_spec(scheme_id))

    @app.post("/api/civic/schemes/{scheme_id}/check")
    def civic_check(scheme_id: str, request: CheckRequest):
        return _scheme_call(scheme_id, lambda: civic_eligibility.check(scheme_id, request.inputs))

    @app.post("/api/civic/schemes/{scheme_id}/change")
    def civic_change(scheme_id: str, request: ChangeRequest):
        def run():
            spec = civic_eligibility.get_scheme(scheme_id)
            return nearest_changes(spec, request.inputs, request.targets, request.lock).as_dict()

        return _scheme_call(scheme_id, run)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(FAVICON_SVG, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC_DIR / "landing.html").read_text()

    @app.get("/officials", response_class=HTMLResponse)
    def officials_page():
        return (STATIC_DIR / "officials.html").read_text()

    @app.get("/about", response_class=HTMLResponse)
    def about_page():
        return (STATIC_DIR / "about.html").read_text()

    @app.get("/citizen", response_class=HTMLResponse)
    def citizen_page():
        return (STATIC_DIR / "citizen.html").read_text()

    return app


settings.load_env()
app = create_app()

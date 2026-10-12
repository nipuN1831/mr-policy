import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from policy_wind_tunnel.agents.approval import ApprovalError, decide_ambiguity
from policy_wind_tunnel.agents.extractor import ExtractionError
from policy_wind_tunnel.agents.llm import LLM, GeminiLLM
from policy_wind_tunnel.civic import eligibility as civic_eligibility
from policy_wind_tunnel.civic.counterfactual import nearest_changes
from policy_wind_tunnel.civic.lookup import find_problems, find_representatives
from policy_wind_tunnel.civic.packs import available_countries, load_pack
from policy_wind_tunnel.contract.evaluator import ContractError
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.service import orchestrator
from policy_wind_tunnel.simulation.scenarios import scenario_by_id
from policy_wind_tunnel.simulation.whatif import ChangeError

STATIC_DIR = Path(__file__).resolve().parent / "static"
_UNSET = object()


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


class CheckRequest(BaseModel):
    inputs: dict[str, Any]


class ChangeRequest(BaseModel):
    inputs: dict[str, Any]
    targets: list[str] | None = None
    lock: list[str] | None = None


class ApproveRequest(BaseModel):
    contract: dict[str, Any]
    ambiguity_id: str
    status: str
    resolution: str | None = None


def llm_from_environment() -> LLM | None:
    configured = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    return GeminiLLM(os.environ.get("PWT_MODEL", "gemini-3.8-flash")) if configured else None


def _load_contract(payload: dict[str, Any] | None, use_gold: bool) -> Contract:
    if payload is None:
        if use_gold:
            return LENDING_CONTRACT
        raise HTTPException(422, detail="supply a contract or set use_gold")
    try:
        return Contract.model_validate(payload)
    except ValidationError as error:
        raise HTTPException(422, detail=error.errors(include_url=False, include_context=False)[:5]) from error


def create_app(llm: Any = _UNSET) -> FastAPI:
    model = llm_from_environment() if llm is _UNSET else llm
    app = FastAPI(title="Policy Wind Tunnel")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "llm": model is not None}

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
        except ChangeError as error:
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

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC_DIR / "landing.html").read_text()

    @app.get("/officials", response_class=HTMLResponse)
    def officials_page():
        return (STATIC_DIR / "officials.html").read_text()

    @app.get("/citizen", response_class=HTMLResponse)
    def citizen_page():
        return (STATIC_DIR / "citizen.html").read_text()

    return app


app = create_app()

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError

from policy_wind_tunnel.agents.approval import ApprovalError, decide_ambiguity
from policy_wind_tunnel.agents.extractor import ExtractionError
from policy_wind_tunnel.agents.llm import LLM, GeminiLLM
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.service import orchestrator

STATIC_DIR = Path(__file__).resolve().parent / "static"
_UNSET = object()


class ExtractRequest(BaseModel):
    policy_text: str
    use_gold: bool = False


class RunRequest(BaseModel):
    target: str
    contract: dict[str, Any] | None = None
    use_gold: bool = False


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

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC_DIR / "index.html").read_text()

    return app


app = create_app()

import contextlib
import datetime
import hmac
import logging
import secrets
import threading
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# Pre-warm cache for these leaders so demo clicks load instantly
_HOTSHOT_LEADERS = [
    ("India", "Narendra Modi"),
    ("India", "Rahul Gandhi"),
    ("India", "Amit Shah"),
    ("India", "Smriti Irani"),
    ("India", "Arvind Kejriwal"),
]

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from policy_wind_tunnel import settings
from policy_wind_tunnel.agents.approval import ApprovalError, decide_ambiguity
from policy_wind_tunnel.agents.extractor import ExtractionError
from policy_wind_tunnel.agents.llm import LLM, GeminiLLM
from policy_wind_tunnel.civic import eligibility as civic_eligibility
from policy_wind_tunnel.civic.counterfactual import nearest_changes
from policy_wind_tunnel.civic.firestore_cache import get_cache
from policy_wind_tunnel.civic.lookup import find_problems, find_representatives
from policy_wind_tunnel.civic.packs import available_countries, load_pack
from policy_wind_tunnel.civic.research import (
    GeminiSearcher,
    ResearchRefused,
    lookup_government,
    lookup_person_detail,
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
LOGIN_FAILURE_MESSAGE = "That email or password is incorrect."
GATE_BLOCKED_MESSAGE = "Sign in required."
RATE_LIMIT_MESSAGE = "Too many attempts. Try again in a minute."
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
_EXEMPT_PATHS = {"/login", "/favicon.ico", "/api/login", "/api/logout"}


class _AuthRequired(Exception):
    """Raised by require_session when no valid session cookie is present."""


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
    language: str = "English"


class LeaderLookupRequest(BaseModel):
    country: str
    place: str = Field(default="", max_length=120)


class PersonLookupRequest(BaseModel):
    country: str
    name: str = Field(max_length=200)
    language: str = "English"


class ApproveRequest(BaseModel):
    contract: dict[str, Any]
    ambiguity_id: str
    status: str
    resolution: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


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


def create_app(llm: Any = _UNSET, searcher: Any = _UNSET, *, enable_login_gate: bool = False) -> FastAPI:
    model = llm_from_environment() if llm is _UNSET else llm
    if searcher is _UNSET:
        searcher = GeminiSearcher(settings.model_name()) if model is not None else None
    lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}
    fs_cache = get_cache()

    @contextlib.asynccontextmanager
    async def _lifespan(_app: FastAPI):
        if searcher is not None:
            threading.Thread(target=_warm_hotshots_fn, daemon=True, name="hotshot-warmup").start()
        yield

    def _warm_hotshots_fn() -> None:
        as_of = datetime.date.today().isoformat()
        for country, name in _HOTSHOT_LEADERS:
            key = (country.lower()[:2], "person", name.lower(), "English")
            if key in lookup_cache:
                continue
            cached = fs_cache.get(key)
            if cached is not None:
                lookup_cache[key] = cached
                _log.info("pre-cached %s (from Firestore)", name)
                continue
            try:
                detail = lookup_person_detail(searcher, country, name, as_of, "English")
                lookup_cache[key] = detail
                fs_cache.put(key, detail)
                _log.info("pre-cached %s (from Gemini)", name)
            except Exception as exc:  # noqa: BLE001
                _log.warning("warm-up failed for %s: %s", name, exc)

    _valid_sessions: set[str] = set()
    _login_attempts: dict[str, list[float]] = {}

    def _is_authenticated(request: Request) -> bool:
        return request.cookies.get("pwt_session", "") in _valid_sessions

    def _recent_failures(ip: str) -> list[float]:
        now = time.time()
        return [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_RATE_LIMIT_WINDOW_SECONDS]

    def _is_rate_limited(ip: str) -> bool:
        recent = _recent_failures(ip)
        _login_attempts[ip] = recent
        return len(recent) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS

    def _record_failed_attempt(ip: str) -> None:
        recent = _recent_failures(ip)
        recent.append(time.time())
        _login_attempts[ip] = recent

    def _clear_failed_attempts(ip: str) -> None:
        _login_attempts.pop(ip, None)

    def require_session(request: Request) -> None:
        path = request.url.path
        if path in _EXEMPT_PATHS or path.startswith("/static/"):
            return
        if not _is_authenticated(request):
            raise _AuthRequired()

    app = FastAPI(
        title="Policy Wind Tunnel",
        lifespan=_lifespan,
        dependencies=[Depends(require_session)] if enable_login_gate else [],
    )

    @app.exception_handler(_AuthRequired)
    async def _handle_auth_required(request: Request, exc: _AuthRequired):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": GATE_BLOCKED_MESSAGE}, status_code=401)
        return RedirectResponse("/login", status_code=302)

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
        "  misconceptions: array of 2-3 short strings — the most common factual misunderstandings or misleading assumptions "
        "people hold about this policy or topic. Each string is one plain sentence, 'read between the lines' style: "
        "surface what is NOT obvious, what official announcements downplay, or where public understanding diverges from the "
        "actual rule. Do NOT use leading labels like 'Myth:' or numbers. Do NOT include if no genuine misconception exists "
        "(return empty array). Never make up statistics or invent sources. "
        "Write BOTH the 'answer' field AND each string in 'misconceptions' in the language given by 'Respond in:' "
        "(English, हिन्दी, or मराठी) — everything else in the JSON stays as specified."
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
        "who is my mp": (None, "/citizen#leaders", "Search your constituency in the 'My area: who represents me' tab. For India, we have all 543 Lok Sabha MPs from the 2024 election — search by constituency name or MP name."),
        "my mp": (None, "/citizen#leaders", "Find your MP in the 'My area: who represents me' tab. Type your constituency name and we will show the elected representative with their party, constituency, and source links."),
        " mp ": (None, "/citizen#leaders", "Find your Member of Parliament in the 'My area: who represents me' tab. All 543 Lok Sabha MPs from the 18th Lok Sabha (2024 election) are available."),
        "mla": (None, "/citizen#leaders", "MLA information is available through state legislature websites. For Lok Sabha MPs, use the 'My area: who represents me' tab — we have all 543 MPs from the 2024 election."),
        "lok sabha": (None, "/citizen#leaders", "All 543 Lok Sabha MPs from the 18th Lok Sabha (2024 general election) are in the 'My area: who represents me' tab. Search by constituency or MP name."),
        "member of parliament": (None, "/citizen#leaders", "Find your Member of Parliament in the 'My area: who represents me' tab. All 543 18th Lok Sabha MPs sourced from ECI 2024 results and sansad.in."),
        "what if": (None, "/officials", "The Officials page lets you simulate a rule change — re-decide thousands of synthetic applicants and see who moves in or out. Try raising the income floor or changing a residency requirement."),
        "broker": (None, "/citizen#decides", "If a broker cheated you, file a complaint with SEBI at scores.sebi.gov.in (for stock brokers) or with the Insurance Ombudsman at ecoi.co.in (for insurance brokers). For real estate agents, file with the state RERA authority. Keep all payment records and communication as evidence."),
        "cheated": (None, "/citizen#decides", "If you were cheated, identify the authority: SEBI for financial brokers, RBI Ombudsman for banks, state RERA for real estate, or CPGRAMS for government services. File a police FIR and a consumer forum complaint (under Consumer Protection Act 2019) in parallel — consumer courts have no filing fee up to ₹5 lakh claims."),
        "fraud": (None, "/citizen#decides", "For financial fraud, report immediately to your bank's fraud helpline, then file at cybercrime.gov.in (for online fraud). For offline fraud, file an FIR and a consumer complaint. The National Consumer Helpline is 1915."),
        "scam": (None, "/citizen#decides", "For scams, report online fraud at cybercrime.gov.in. For phone/UPI scams, call your bank immediately to freeze the account and file at 1930 (National Cyber Crime helpline). Keep screenshots and transaction IDs."),
        "consumer": (None, "/citizen#decides", "The Consumer Protection Act 2019 covers unfair trade practices, defective goods, and deficient services. File online at edaakhil.nic.in. No advocate needed for claims under ₹5 lakh. The district consumer forum must respond within 21 days of admission."),
        "sebi": (None, "/citizen#decides", "SEBI handles complaints against stock brokers, mutual funds, and listed companies. File at scores.sebi.gov.in. The company must respond within 30 days. If unresolved, SEBI takes up the matter directly."),
        "pension": (None, "/citizen#decides", "For pension grievances, use the Centralised Pension Grievance Redress and Monitoring System at pgportal.gov.in. For EPFO/PF issues, file at epfigms.gov.in. Include your UAN and employer details in the complaint."),
        "refund": (None, "/citizen#decides", "For a refused refund from a business, file under Consumer Protection Act 2019 at edaakhil.nic.in. For a bank or payment gateway refund, escalate to the RBI Ombudsman at cms.rbi.org.in after 30 days without resolution."),
        "hospital": (None, "/citizen#decides", "For medical negligence, file a complaint with the State Medical Council. For overcharging, file with the Consumer Forum (hospitals are 'services' under Consumer Protection Act 2019). Government hospital complaints go to the CPGRAMS or state health ministry."),
        "police": (None, "/citizen#rights", "If police refuse to file an FIR, you can file a complaint directly to the Superintendent of Police or use Section 156(3) CrPC to approach a magistrate. The SC has ruled police cannot refuse an FIR for a cognizable offence. You can also file a zero FIR at any station regardless of jurisdiction."),
        "ration": (None, "/citizen#decides", "For ration not received or name missing from ration card: first complain to your Fair Price Shop dealer, then the Block Supply Officer. Use CPGRAMS (pgportal.gov.in) for central escalation. National Food Security helpline: 1967."),
        "aadhar": (None, "/citizen#decides", "For Aadhaar issues (update, linking, not working), visit your nearest Aadhaar Seva Kendra or use the UIDAI self-service portal at myaadhaar.uidai.gov.in. Helpline: 1947. For seeding Aadhaar to bank accounts, visit your bank branch."),
        "aadhaar": (None, "/citizen#decides", "For Aadhaar issues (update, linking, not working), visit your nearest Aadhaar Seva Kendra or use the UIDAI self-service portal at myaadhaar.uidai.gov.in. Helpline: 1947. For seeding Aadhaar to bank accounts, visit your bank branch."),
        "pm kisan": (None, "/citizen#decides", "For PM-KISAN instalment not received: check your payment status at pmkisan.gov.in → Beneficiary Status. Common reasons: Aadhaar not seeded to bank, name mismatch, or land record issue. Helpline: 155261 or 011-24300606. Visit your local Agriculture Department office with Aadhaar, land record, and bank passbook."),
        "kisan": (None, "/citizen#decides", "For PM-KISAN instalment not received: check at pmkisan.gov.in → Beneficiary Status. Helpline: 155261. Visit local Agriculture office with Aadhaar and land record (khatauni)."),
        "ayushman": (None, "/citizen#decides", "For Ayushman Bharat (PM-JAY): check your eligibility and download your e-card at beneficiary.nha.gov.in using Aadhaar. If an empanelled hospital refuses cashless treatment, call the PM-JAY helpline 14555 immediately. File a grievance on the NHA portal for denial."),
        "mnrega": (None, "/citizen#decides", "For MNREGA work not given: you are entitled to work within 15 days of applying or an unemployment allowance. Check payment at mnregaweb4.nic.in using your Job Card number. Complain to the Block Programme Officer. Helpline: 1800-345-22-44."),
        "mgnrega": (None, "/citizen#decides", "For MGNREGA/MNREGA work not given: you are entitled to work within 15 days or an unemployment allowance. Check at mnregaweb4.nic.in. Complain to the Block Programme Officer. Helpline: 1800-345-22-44."),
        "scholarship": (None, "/citizen#decides", "For scholarship not received: track your application at scholarships.gov.in. Common reasons: incomplete documents, institution not approved. Contact your institution's nodal officer first. Helpline: 0120-6619540 (Mon–Fri 8am–8pm)."),
        "bijli": (None, "/citizen#decides", "For electricity bill disputes or unresolved power cuts: complain to your DISCOM customer care first. For billing errors, file with the Consumer Grievance Redressal Forum of your DISCOM, then the State Electricity Regulatory Commission Ombudsman. National helpline: 1912."),
        "fir": (None, "/citizen#rights", "You can file a zero FIR at ANY police station in India regardless of jurisdiction. If police refuse, send a registered post complaint to the Superintendent of Police or apply to the Judicial Magistrate under Section 156(3) CrPC. Supreme Court ruled police cannot refuse a cognizable offence FIR."),
        "land": (None, "/citizen#decides", "For land record errors or mutations: check your khasra/khatauni on your state's land records portal (dilrmp.gov.in lists all states). For errors, apply to the Patwari/Lekhpal. For disputes, escalate to Tehsildar → SDM → DM. File RTI for records under which any government action was taken."),
    }

    def _keyword_match(q: str) -> dict | None:
        for kw, (scheme_id, path, answer_text) in _CHAT_KEYWORDS.items():
            if kw in q:
                return {"answer": answer_text, "intent": "general", "scheme_id": scheme_id, "redirect_path": path, "powered_by": "fallback"}
        return None

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        q = request.question.strip().lower()
        if model is not None:
            try:
                import json as _json
                raw = model.generate_json(
                    _CHAT_SYSTEM,
                    f"Country: {request.country}\nRespond in: {request.language}\nQuestion: {request.question}",
                )
                start = raw.rfind("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    meta = _json.loads(raw[start:end])
                    answer_text = meta.get("answer") or raw[:start].strip()
                    redirect = meta.get("redirect_path") or "/citizen"
                    # if Gemini returns generic /citizen with no fragment, check keywords for a more specific redirect
                    if redirect in ("/citizen", None) and meta.get("intent", "general") == "general":
                        kw_hit = _keyword_match(q)
                        if kw_hit:
                            return {**kw_hit, "answer": answer_text, "powered_by": "gemini+keyword"}
                    raw_misc = meta.get("misconceptions")
                    misconceptions = [s for s in (raw_misc or []) if isinstance(s, str) and s.strip()][:3]
                    return {
                        "answer": answer_text,
                        "intent": meta.get("intent", "general"),
                        "scheme_id": meta.get("scheme_id"),
                        "redirect_path": redirect,
                        "powered_by": "gemini",
                        "misconceptions": misconceptions,
                    }
            except Exception:
                pass
        # keyword fallback (when model is None or JSON extraction failed)
        kw_hit = _keyword_match(q)
        if kw_hit:
            return kw_hit
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
        all_fictional = all(r.fictional for r in found)
        return {
            "demo": all_fictional,
            "notice": (
                "These representatives are fictional demo data. No real person is shown."
                if all_fictional
                else "Representative data sourced from ECI 2024 results and sansad.in."
            ),
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
            cached = fs_cache.get(key)
            if cached is not None:
                lookup_cache[key] = cached
            else:
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
                fs_cache.put(key, found)
        return lookup_cache[key]

    @app.post("/api/civic/leaders/person")
    def leaders_person(request: PersonLookupRequest):
        if not _live():
            raise HTTPException(503, detail="Live lookup needs Gemini to be connected, and is switched off otherwise.")
        pack = _pack(request.country)
        name = " ".join(request.name.split())
        if not name:
            raise HTTPException(422, detail="Enter a person's name.")
        try:
            refuse_if_judgement(name)
        except ResearchRefused as error:
            raise HTTPException(422, detail=str(error)) from error
        key = (pack.code, "person", name.lower(), request.language)
        if key not in lookup_cache:
            cached = fs_cache.get(key)
            if cached is not None:
                lookup_cache[key] = cached
            else:
                as_of = datetime.date.today().isoformat()
                try:
                    detail = lookup_person_detail(searcher, pack.name, name, as_of, request.language)
                except Exception as error:  # noqa: BLE001
                    raise HTTPException(502, detail=f"The web search did not complete: {type(error).__name__}") from error
                lookup_cache[key] = detail
                fs_cache.put(key, detail)
        return lookup_cache[key]

    @app.get("/api/civic/countries/{code}/policies/upcoming")
    def civic_upcoming_policies(code: str, status: str = ""):
        pack = _pack(code)
        policies = pack.upcoming_policies
        if status:
            policies = [p for p in policies if p.status == status]
        return {"policies": [p.model_dump() for p in policies]}

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

    @app.post("/api/login")
    def login(payload: LoginRequest, request: Request, response: Response):
        client_ip = request.client.host if request.client else "unknown"
        if _is_rate_limited(client_ip):
            raise HTTPException(429, detail=RATE_LIMIT_MESSAGE)
        email = payload.email.strip().lower()
        expected_password = settings.login_password()
        password_matches = bool(expected_password) and hmac.compare_digest(payload.password, expected_password)
        if email not in settings.login_emails() or not password_matches:
            _record_failed_attempt(client_ip)
            raise HTTPException(401, detail=LOGIN_FAILURE_MESSAGE)
        _clear_failed_attempts(client_ip)
        token = secrets.token_urlsafe(32)
        _valid_sessions.add(token)
        response.set_cookie(
            "pwt_session",
            token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return {"ok": True}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        _valid_sessions.discard(request.cookies.get("pwt_session", ""))
        response.delete_cookie("pwt_session")
        return {"ok": True}

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

    @app.get("/api/civic/leaders/hotshots")
    def leaders_hotshots():
        return {"leaders": [{"country": c, "name": n} for c, n in _HOTSHOT_LEADERS]}

    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        return (STATIC_DIR / "login.html").read_text()

    return app


settings.load_env()
app = create_app(enable_login_gate=True)

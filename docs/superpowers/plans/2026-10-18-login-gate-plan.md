# Login gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/login` page that matches the existing citizen/officials visual style, and gate every page and API route behind it using a minimal, dependency-free, server-side signed-cookie check against an env-configured email whitelist and shared password.

**Architecture:** `src/policy_wind_tunnel/service/app.py` gets a new `login_emails`/`login_password`/`session_secret`-backed `require_session` FastAPI dependency, attached globally via `FastAPI(dependencies=[...])` only when `enable_login_gate=True` is passed to `create_app()`. A custom `_AuthRequired` exception + exception handler turns a missing/invalid session into a 302 redirect (HTML routes) or 401 JSON (`/api/*` routes). `/login`, `/favicon.ico`, `/static/*`, `/api/login`, and `/api/logout` are exempt. Production (`app = create_app(enable_login_gate=True)` at the bottom of the file) turns the gate on; every existing test keeps calling `create_app()` without the new keyword and is therefore completely unaffected (default `False`) — this is a deliberate testability decision beyond what the spec covered, see Global Constraints.

**Tech Stack:** FastAPI, Starlette's `Request`/`Response`/cookie handling, Python stdlib `hmac`/`hashlib`/`secrets` (no new dependencies), plain HTML/CSS/JS matching the existing static pages, pytest + `fastapi.testclient.TestClient`.

## Global Constraints

- No new third-party dependency (no `itsdangerous`, no auth library) — use stdlib `hmac`, `hashlib`, `secrets` only (spec §2).
- Visual style must reuse the exact CSS custom properties, fonts (`DM Sans` body / `Manrope` headings), and component conventions already used in `citizen.html`/`officials.html` — plain white card on the light `--page` background (spec §1, layout **C**).
- `/login` has **no** "Forgot password?" and **no** "Sign up" link. Error copy is always the single generic string `"That email or password is incorrect."`, identical for an unrecognized email and a wrong password (spec §1).
- English only — no language switcher on `/login` (spec §1).
- Cookie name is `pwt_session`; flags are `HttpOnly`, `SameSite=Lax`, `Secure` set dynamically from `request.url.scheme == "https"`, and **no** `Max-Age`/`Expires` (true session cookie) (spec §2).
- After a successful login the client always redirects to `/`, never back to whatever page triggered the gate (spec §2).
- Env vars: `PWT_LOGIN_EMAILS` (comma-separated, case-insensitive), `PWT_LOGIN_PASSWORD`, `PWT_SESSION_SECRET` (random in-memory fallback + `RuntimeWarning` if unset) (spec §2–3).
- `.env.example` gets placeholder values only — never real emails or a real password (spec §3).
- Fail-open-to-login, not fail-open-to-content: if `PWT_LOGIN_EMAILS`/`PWT_LOGIN_PASSWORD` are unset, the app still boots and the gate still redirects everyone to `/login`; the login endpoint just rejects every attempt (spec §3).
- **Deviation/addition beyond the spec, decided during planning:** `create_app()` gains a keyword-only `enable_login_gate: bool = False` parameter. The ~15 existing test files across `tests/` construct `TestClient(create_app(...))` directly and assert unauthenticated 200s; retrofitting a session into every one of them (or a global dependency-override) was evaluated and rejected as disproportionate churn for this feature. Defaulting the gate off means every existing test is untouched; the one real entrypoint (`app = create_app(enable_login_gate=True)`) opts in explicitly. A dedicated `tests/test_login.py` exercises the gate itself with `enable_login_gate=True`.

---

## File Structure

| File | Change |
|---|---|
| `src/policy_wind_tunnel/settings.py` | Add `login_emails()`, `login_password()`, `session_secret()` |
| `src/policy_wind_tunnel/service/app.py` | New imports, `LoginRequest` model, `_AuthRequired` exception, `require_session` dependency, `enable_login_gate` param, `/login` `GET`, `/api/login` `POST`, `/api/logout` `POST` |
| `src/policy_wind_tunnel/service/static/login.html` | New file — the login page |
| `src/policy_wind_tunnel/service/static/citizen.html` | Add "Sign out" nav link + JS |
| `src/policy_wind_tunnel/service/static/officials.html` | Add "Sign out" nav link + JS |
| `src/policy_wind_tunnel/service/static/about.html` | Add "Sign out" nav link + JS |
| `src/policy_wind_tunnel/service/static/landing.html` | Add "Sign out" nav link + JS |
| `tests/test_settings.py` | New tests for the three settings functions |
| `tests/test_api.py` | New tests for `/login` page + sign-out link; extend two existing "every page" loops |
| `tests/test_login.py` | New file — gate behavior, login/logout flow |
| `tests/conftest.py` | Add the 3 new env keys to `ENV_KEYS` |
| `.env.example` | Add 3 placeholder vars |

---

### Task 1: Settings helpers for login config

**Files:**
- Modify: `src/policy_wind_tunnel/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `settings.login_emails() -> set[str]`, `settings.login_password() -> str`, `settings.session_secret() -> str` — all read live from `os.environ` on every call (same pattern as `settings.model_name()`), used by Task 3 and Task 4.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_settings.py`, after `test_describe_reports_the_kill_switch` (and add the three new keys to the local `KEYS` tuple at the top of the file):

```python
KEYS = (
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "PWT_MODEL",
    "PWT_LIVE_LEADERS",
    "PWT_LOGIN_EMAILS",
    "PWT_LOGIN_PASSWORD",
    "PWT_SESSION_SECRET",
)
```

```python
def test_login_emails_defaults_to_empty(monkeypatch):
    assert settings.login_emails() == set()


def test_login_emails_parses_a_comma_separated_case_insensitive_list(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", " Demo@Example.com, other@example.com ,,")
    assert settings.login_emails() == {"demo@example.com", "other@example.com"}


def test_login_password_defaults_to_empty_string(monkeypatch):
    assert settings.login_password() == ""
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", "shared-secret")
    assert settings.login_password() == "shared-secret"


def test_session_secret_defaults_to_empty_and_is_stripped(monkeypatch):
    assert settings.session_secret() == ""
    monkeypatch.setenv("PWT_SESSION_SECRET", "  abc123  ")
    assert settings.session_secret() == "abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_settings.py -v -k login_emails_defaults`
Expected: `FAIL` with `AttributeError: module 'policy_wind_tunnel.settings' has no attribute 'login_emails'`

- [ ] **Step 3: Implement the settings functions**

In `src/policy_wind_tunnel/settings.py`, add after `live_leaders_enabled()` (before `describe()`):

```python
def login_emails() -> set[str]:
    raw = os.environ.get("PWT_LOGIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def login_password() -> str:
    return os.environ.get("PWT_LOGIN_PASSWORD", "")


def session_secret() -> str:
    return os.environ.get("PWT_SESSION_SECRET", "").strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_settings.py -v`
Expected: all `PASS`, including the 4 new tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy
git add src/policy_wind_tunnel/settings.py tests/test_settings.py
git commit -m "feat: add login whitelist/password/session-secret settings helpers"
```

---

### Task 2: The `/login` page

**Files:**
- Create: `src/policy_wind_tunnel/service/static/login.html`
- Modify: `src/policy_wind_tunnel/service/app.py:409-424` (add the `/login` route next to the other page routes)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: nothing new yet (the page's JS calls `POST /api/login`, which does not exist until Task 3 — that's fine, this task only proves the page itself renders and is wired to call that URL; Task 3/4 prove the backend side).
- Produces: `GET /login` serving `login.html`, reachable with plain `client.get("/login")` (gate is off by default per Task 4, and `/login` is exempt even when it's on).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_login_page_is_served_and_matches_shared_page_conventions(client):
    page = client.get("/login")
    assert page.status_code == 200
    assert 'class="skip"' in page.text
    assert 'name="viewport"' in page.text
    assert "/static/app.css" in page.text
    assert 'lang="en"' in page.text
    assert "Welcome back" in page.text
    assert 'type="email"' in page.text and 'type="password"' in page.text
    assert 'id="loginError"' in page.text
    assert "/api/login" in page.text
    # no forgot-password / sign-up links, per spec
    assert "forgot" not in page.text.lower()
    assert "sign up" not in page.text.lower() and "sign-up" not in page.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_api.py -v -k test_login_page_is_served`
Expected: `FAIL` with `404` (route does not exist yet)

- [ ] **Step 3: Create the login page**

Create `src/policy_wind_tunnel/service/static/login.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in | Policy Wind Tunnel</title>
<meta name="description" content="Sign in to Policy Wind Tunnel.">
<link rel="icon" href="/favicon.ico" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/app.css">
<style>
:root {
  --ink: #10251f; --text: #34433d; --muted: #65736d;
  --green: #15533f; --green-dark: #0b3e2e;
  --line: #e4e8e3; --page: #fafbf8; --fail: #b3261e;
  --shadow: 0 14px 38px rgba(24,48,37,.07); --radius: 20px;
  font-synthesis: none; text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--page); color: var(--ink); font-family: "DM Sans", system-ui, sans-serif; font-size: 16px; line-height: 1.6; }
button, input { font: inherit; }
button:focus-visible, a:focus-visible, input:focus-visible { outline: 3px solid #4e8c70; outline-offset: 3px; }
.skip { position: absolute; top: -60px; left: 16px; z-index: 100; padding: 10px 14px; background: var(--green-dark); color: white; border-radius: 10px; text-decoration: none; }
.skip:focus { top: 12px; }

.site-header { height: 72px; padding: 0 clamp(20px, 5.5vw, 88px); display: flex; align-items: center; background: rgba(255,254,250,.95); border-bottom: 1px solid rgba(21,83,63,.08); position: sticky; top: 0; z-index: 10; backdrop-filter: blur(8px); }
.brand { display: inline-flex; align-items: center; gap: 13px; text-decoration: none; color: var(--ink); font-family: Manrope, sans-serif; font-size: clamp(17px, 1.8vw, 22px); font-weight: 800; letter-spacing: -.6px; white-space: nowrap; }
.brand-mark { width: 40px; height: 40px; color: var(--green); flex: none; }

.login-wrap { min-height: calc(100vh - 72px); display: flex; align-items: center; justify-content: center; padding: 40px 20px; }
.login-card { width: 100%; max-width: 380px; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); padding: 32px 30px; }
.login-eyebrow { margin: 0 0 8px; font: 700 10px/1 "DM Sans", sans-serif; letter-spacing: 1.6px; text-transform: uppercase; color: #6c8475; }
.login-title { margin: 0 0 22px; font: 700 26px/1.2 Manrope, sans-serif; letter-spacing: -.02em; color: var(--ink); }
.field { margin-bottom: 16px; }
.field label { display: block; margin-bottom: 6px; font-size: 13px; font-weight: 700; color: var(--text); }
.field input { width: 100%; background: #fff; color: var(--ink); border: 1.5px solid #6b8190; border-radius: 10px; padding: 10px 14px; min-height: 48px; font-size: 16px; }
.login-btn { width: 100%; margin-top: 6px; display: inline-flex; align-items: center; justify-content: center; background: var(--green-dark); color: #fff; border: 0; border-radius: 11px; padding: 11px 22px; font: 650 16px "DM Sans", sans-serif; cursor: pointer; min-height: 48px; transition: background .15s; }
.login-btn:hover { background: var(--green); }
.login-btn:disabled { opacity: .5; cursor: not-allowed; }
.login-error { min-height: 20px; margin: 14px 0 0; color: var(--fail); font-size: 14px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: .01ms !important; } }
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <a class="brand" href="/" aria-label="Policy Wind Tunnel home">
    <svg class="brand-mark" viewBox="0 0 48 48" role="img" aria-hidden="true">
      <path d="M5 40V24C5 13.5 13.5 5 24 5s19 8.5 19 19v16" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/>
      <path d="M12 40V24c0-6.6 5.4-12 12-12s12 5.4 12 12v16" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/>
      <path d="M19 40V27a5 5 0 0 1 10 0v13" fill="currentColor" opacity=".72"/>
    </svg>
    <span>Policy Wind Tunnel</span>
  </a>
</header>
<main id="main" class="login-wrap">
  <form class="login-card" id="loginForm" autocomplete="off" novalidate>
    <p class="login-eyebrow">SIGN IN</p>
    <h1 class="login-title">Welcome back</h1>
    <div class="field">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" autocomplete="username" required>
    </div>
    <div class="field">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" autocomplete="current-password" required>
    </div>
    <button type="submit" class="login-btn" id="signInBtn">Sign in</button>
    <p class="login-error" id="loginError" role="alert"></p>
  </form>
</main>
<script>
const form = document.getElementById("loginForm");
const errorEl = document.getElementById("loginError");
const btn = document.getElementById("signInBtn");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  btn.disabled = true;
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      errorEl.textContent = typeof data.detail === "string" ? data.detail : "That email or password is incorrect.";
      btn.disabled = false;
      return;
    }
    window.location.href = "/";
  } catch (_) {
    errorEl.textContent = "Something went wrong. Try again.";
    btn.disabled = false;
  }
});
</script>
</body>
</html>
```

- [ ] **Step 4: Add the route**

In `src/policy_wind_tunnel/service/app.py`, add this route next to the other page routes (after the `@app.get("/citizen", ...)` block, before `return app`, i.e. around current line 423):

```python
    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        return (STATIC_DIR / "login.html").read_text()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_api.py -v -k test_login_page_is_served`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy
git add src/policy_wind_tunnel/service/static/login.html src/policy_wind_tunnel/service/app.py tests/test_api.py
git commit -m "feat: add the /login page"
```

---

### Task 3: `/api/login` and `/api/logout`

**Files:**
- Modify: `src/policy_wind_tunnel/service/app.py` (top-of-file imports; new module-level constants/model; new routes near `/favicon.ico`)
- Test: `tests/test_login.py` (new file)

**Interfaces:**
- Consumes: `settings.login_emails()`, `settings.login_password()` from Task 1.
- Produces: `POST /api/login` (body `{"email": str, "password": str}` → `200 {"ok": true}` + `Set-Cookie: pwt_session=...` on success, `401 {"detail": "That email or password is incorrect."}` on failure) and `POST /api/logout` (`200 {"ok": true}` + clears the cookie). Also produces the module-level constant `LOGIN_FAILURE_MESSAGE = "That email or password is incorrect."` and the cookie name `"pwt_session"`, both relied on by Task 4's tests.
- Note: this task does **not** add the gate yet — these two routes work standalone and are reachable with no cookie at all, exactly like every other route today. Task 4 adds enforcement.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_login.py`:

```python
import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.service.app import create_app

EMAIL = "demo@example.com"
PASSWORD = "shared-demo-password"


@pytest.fixture()
def configured_client(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", f"{EMAIL}, other@example.com")
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", PASSWORD)
    monkeypatch.setenv("PWT_SESSION_SECRET", "test-secret")
    return TestClient(create_app(llm=None))


def test_correct_credentials_log_in_and_set_a_cookie(configured_client):
    response = configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "pwt_session" in configured_client.cookies


def test_email_match_is_case_insensitive(configured_client):
    response = configured_client.post("/api/login", json={"email": EMAIL.upper(), "password": PASSWORD})
    assert response.status_code == 200


def test_wrong_password_is_rejected_with_the_generic_message(configured_client):
    response = configured_client.post("/api/login", json={"email": EMAIL, "password": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "That email or password is incorrect."
    assert "pwt_session" not in configured_client.cookies


def test_unknown_email_gets_the_exact_same_generic_message(configured_client):
    response = configured_client.post("/api/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert response.status_code == 401
    assert response.json()["detail"] == "That email or password is incorrect."


def test_empty_email_and_password_are_rejected_with_the_generic_message(configured_client):
    response = configured_client.post("/api/login", json={"email": "", "password": ""})
    assert response.status_code == 401
    assert response.json()["detail"] == "That email or password is incorrect."


def test_empty_password_never_matches_an_unset_shared_password(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", EMAIL)
    monkeypatch.delenv("PWT_LOGIN_PASSWORD", raising=False)
    client = TestClient(create_app(llm=None))
    response = client.post("/api/login", json={"email": EMAIL, "password": ""})
    assert response.status_code == 401


def test_the_cookie_is_httponly_samesite_lax_and_has_no_max_age(configured_client):
    response = configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    set_cookie = response.headers["set-cookie"]
    assert "pwt_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "max-age" not in set_cookie.lower()
    assert "expires=" not in set_cookie.lower()


def test_logout_clears_the_cookie(configured_client):
    configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    response = configured_client.post("/api/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "pwt_session" not in configured_client.cookies
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_login.py -v`
Expected: every test `FAIL` with `404 Not Found` (neither route exists yet)

- [ ] **Step 3: Implement the routes**

In `src/policy_wind_tunnel/service/app.py`, change the imports at the top of the file from:

```python
import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
```

to:

```python
import datetime
import hashlib
import hmac
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
```

Add this new request model next to the other `*Request` models (e.g. right after `class ApproveRequest(BaseModel): ...`, around line 98):

```python
class LoginRequest(BaseModel):
    email: str
    password: str
```

Add this module-level constant near `FAVICON_SVG` (around line 40):

```python
LOGIN_FAILURE_MESSAGE = "That email or password is incorrect."
```

Inside `create_app()`, change:

```python
    app = FastAPI(title="Policy Wind Tunnel")
```

to:

```python
    app = FastAPI(title="Policy Wind Tunnel")
    session_secret = settings.session_secret() or secrets.token_hex(32)
    session_token = hmac.new(session_secret.encode(), b"pwt-authenticated", hashlib.sha256).hexdigest()
```

This needs `import secrets` added alongside the other new imports at the top — update the import block above to:

```python
import datetime
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
```

(Task 4 replaces the plain `secrets.token_hex(32)` fallback with the warned version — this task keeps it simple since the warning behavior isn't under test yet here.)

Add the two routes in `src/policy_wind_tunnel/service/app.py`, right before `@app.get("/favicon.ico", ...)` (current line 403):

```python
    @app.post("/api/login")
    def login(payload: LoginRequest, request: Request, response: Response):
        email = payload.email.strip().lower()
        expected_password = settings.login_password()
        password_matches = bool(expected_password) and hmac.compare_digest(payload.password, expected_password)
        if email not in settings.login_emails() or not password_matches:
            raise HTTPException(401, detail=LOGIN_FAILURE_MESSAGE)
        response.set_cookie(
            "pwt_session",
            session_token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie("pwt_session")
        return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_login.py -v`
Expected: all 7 tests `PASS`

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest -q`
Expected: all tests `PASS` (these two new routes have no effect on anything else — no gate yet)

- [ ] **Step 6: Commit**

```bash
cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy
git add src/policy_wind_tunnel/service/app.py tests/test_login.py
git commit -m "feat: add /api/login and /api/logout"
```

---

### Task 4: The gate itself

**Files:**
- Modify: `src/policy_wind_tunnel/service/app.py`
- Test: `tests/test_login.py`

**Interfaces:**
- Consumes: `session_token` and `LOGIN_FAILURE_MESSAGE` from Task 3; `settings.session_secret()` from Task 1.
- Produces: `create_app(..., *, enable_login_gate: bool = False)`. When `True`, every route except `GET /login`, `GET /favicon.ico`, `/static/*`, `POST /api/login`, `POST /api/logout` requires a valid `pwt_session` cookie — HTML routes get a `302` to `/login`, `/api/*` routes get `401 {"detail": "Sign in required."}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_login.py`:

```python
GATE_BLOCKED_MESSAGE = "Sign in required."


@pytest.fixture()
def gated_client(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", f"{EMAIL}, other@example.com")
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", PASSWORD)
    monkeypatch.setenv("PWT_SESSION_SECRET", "test-secret")
    return TestClient(create_app(llm=None, enable_login_gate=True))


def test_pages_redirect_to_login_when_unauthenticated(gated_client):
    for path in ("/", "/citizen", "/officials", "/about"):
        response = gated_client.get(path, follow_redirects=False)
        assert response.status_code == 302, path
        assert response.headers["location"] == "/login", path


def test_login_page_itself_is_reachable_without_a_session(gated_client):
    assert gated_client.get("/login").status_code == 200


def test_static_assets_and_the_favicon_are_reachable_without_a_session(gated_client):
    assert gated_client.get("/static/app.css").status_code == 200
    assert gated_client.get("/favicon.ico").status_code == 200


def test_api_routes_are_blocked_with_401_json_not_a_redirect(gated_client):
    response = gated_client.get("/api/health", follow_redirects=False)
    assert response.status_code == 401
    assert response.json()["detail"] == GATE_BLOCKED_MESSAGE


def test_login_and_logout_endpoints_stay_reachable_without_a_session(gated_client):
    assert gated_client.post("/api/login", json={"email": "nobody@example.com", "password": "x"}).status_code == 401
    assert gated_client.post("/api/logout").status_code == 200


def test_correct_credentials_unlock_every_page_and_api_route(gated_client):
    login = gated_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    for path in ("/", "/citizen", "/officials", "/about", "/api/health"):
        assert gated_client.get(path).status_code == 200, path


def test_sign_out_locks_every_page_again(gated_client):
    gated_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    assert gated_client.get("/").status_code == 200
    gated_client.post("/api/logout")
    assert gated_client.get("/", follow_redirects=False).status_code == 302


def test_missing_env_vars_fail_open_to_login_not_to_content(monkeypatch):
    monkeypatch.delenv("PWT_LOGIN_EMAILS", raising=False)
    monkeypatch.delenv("PWT_LOGIN_PASSWORD", raising=False)
    client = TestClient(create_app(llm=None, enable_login_gate=True))
    assert client.get("/", follow_redirects=False).status_code == 302
    response = client.post("/api/login", json={"email": "anyone@example.com", "password": "anything"})
    assert response.status_code == 401


def test_the_gate_is_off_by_default_so_every_other_test_file_is_unaffected():
    client = TestClient(create_app(llm=None))
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_login.py -v -k "gate or redirect or unlock or sign_out or fail_open"`
Expected: `FAIL` — `create_app()` raises `TypeError: create_app() got an unexpected keyword argument 'enable_login_gate'`

- [ ] **Step 3: Implement the gate**

In `src/policy_wind_tunnel/service/app.py`, add these imports (merge into the block already touched in Task 3):

```python
import datetime
import hashlib
import hmac
import secrets
import warnings
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
```

Add these module-level constants/classes right after `LOGIN_FAILURE_MESSAGE` (added in Task 3):

```python
GATE_BLOCKED_MESSAGE = "Sign in required."
_EXEMPT_PATHS = {"/login", "/favicon.ico", "/api/login", "/api/logout"}


class _AuthRequired(Exception):
    """Raised by require_session when no valid session cookie is present."""
```

Change `def create_app(llm: Any = _UNSET, searcher: Any = _UNSET) -> FastAPI:` to:

```python
def create_app(llm: Any = _UNSET, searcher: Any = _UNSET, *, enable_login_gate: bool = False) -> FastAPI:
```

Then replace this whole block (as it stands after Task 3 — `lookup_cache` followed by the `app = FastAPI(...)` line and the two session lines added in Task 3):

```python
    lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}
    app = FastAPI(title="Policy Wind Tunnel")
    session_secret = settings.session_secret() or secrets.token_hex(32)
    session_token = hmac.new(session_secret.encode(), b"pwt-authenticated", hashlib.sha256).hexdigest()
```

with:

```python
    lookup_cache: dict[tuple[str, str], dict[str, Any]] = {}

    raw_secret = settings.session_secret()
    if raw_secret:
        session_secret = raw_secret
    else:
        session_secret = secrets.token_hex(32)
        warnings.warn(
            "PWT_SESSION_SECRET is not set; using a random secret for this process. "
            "Existing sessions will not survive a restart.",
            RuntimeWarning,
            stacklevel=2,
        )
    session_token = hmac.new(session_secret.encode(), b"pwt-authenticated", hashlib.sha256).hexdigest()

    def _is_authenticated(request: Request) -> bool:
        return hmac.compare_digest(request.cookies.get("pwt_session", ""), session_token)

    def require_session(request: Request) -> None:
        path = request.url.path
        if path in _EXEMPT_PATHS or path.startswith("/static/"):
            return
        if not _is_authenticated(request):
            raise _AuthRequired()

    app = FastAPI(
        title="Policy Wind Tunnel",
        dependencies=[Depends(require_session)] if enable_login_gate else [],
    )

    @app.exception_handler(_AuthRequired)
    async def _handle_auth_required(request: Request, exc: _AuthRequired):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": GATE_BLOCKED_MESSAGE}, status_code=401)
        return RedirectResponse("/login", status_code=302)
```

Note there is now exactly one `app = FastAPI(...)` assignment and one `session_token` computation in the function — the Task-3 versions of both are fully replaced, not duplicated.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_login.py -v`
Expected: all tests `PASS`

- [ ] **Step 5: Run the full test suite**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest -q`
Expected: all tests `PASS` — every pre-existing test calls `create_app()` without `enable_login_gate`, so it defaults to `False` and behaves exactly as before.

- [ ] **Step 6: Commit**

```bash
cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy
git add src/policy_wind_tunnel/service/app.py tests/test_login.py
git commit -m "feat: gate every page and API route behind a signed session cookie"
```

---

### Task 5: "Sign out" link on every gated page

**Files:**
- Modify: `src/policy_wind_tunnel/service/static/citizen.html:208-212`
- Modify: `src/policy_wind_tunnel/service/static/officials.html:142-146`
- Modify: `src/policy_wind_tunnel/service/static/about.html:89-93`
- Modify: `src/policy_wind_tunnel/service/static/landing.html:281-285`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `POST /api/logout` from Task 3.
- Produces: nothing new consumed by later tasks — this is a leaf change.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_every_gated_page_offers_a_sign_out_link(client):
    for path in ("/", "/citizen", "/officials", "/about"):
        text = client.get(path).text
        assert 'id="signOutLink"' in text, path
        assert "/api/logout" in text, path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_api.py -v -k sign_out_link`
Expected: `FAIL` — `'id="signOutLink"' in text` is `False` for every path

- [ ] **Step 3: Add the link and script to `citizen.html`**

In `src/policy_wind_tunnel/service/static/citizen.html`, change (around line 208-212):

```html
  <nav class="header-nav" aria-label="Main">
    <a class="nav-link on" href="/citizen" aria-current="page">For citizens</a>
    <a class="nav-link" href="/officials">For officials</a>
    <a class="nav-link" href="/about">How it works</a>
  </nav>
```

to:

```html
  <nav class="header-nav" aria-label="Main">
    <a class="nav-link on" href="/citizen" aria-current="page">For citizens</a>
    <a class="nav-link" href="/officials">For officials</a>
    <a class="nav-link" href="/about">How it works</a>
    <a class="nav-link" href="/login" id="signOutLink">Sign out</a>
  </nav>
```

Then, in the `<script>` block, right after the existing line `const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));` (current line 295), add:

```javascript
document.getElementById("signOutLink").addEventListener("click", (e) => {
  e.preventDefault();
  fetch("/api/logout", { method: "POST" }).finally(() => { window.location.href = "/login"; });
});
```

- [ ] **Step 4: Add the link and script to `officials.html`**

In `src/policy_wind_tunnel/service/static/officials.html`, change (around line 142-146):

```html
  <nav class="header-nav" aria-label="Main">
    <a class="nav-link" href="/citizen">For citizens</a>
    <a class="nav-link on" href="/officials" aria-current="page">For officials</a>
    <a class="nav-link" href="/about">How it works</a>
  </nav>
```

to:

```html
  <nav class="header-nav" aria-label="Main">
    <a class="nav-link" href="/citizen">For citizens</a>
    <a class="nav-link on" href="/officials" aria-current="page">For officials</a>
    <a class="nav-link" href="/about">How it works</a>
    <a class="nav-link" href="/login" id="signOutLink">Sign out</a>
  </nav>
```

Then, in the `<script>` block, right after the existing line `const $ = (id) => document.getElementById(id);` (current line 245), add:

```javascript
document.getElementById("signOutLink").addEventListener("click", (e) => {
  e.preventDefault();
  fetch("/api/logout", { method: "POST" }).finally(() => { window.location.href = "/login"; });
});
```

- [ ] **Step 5: Add the link and script to `about.html`**

In `src/policy_wind_tunnel/service/static/about.html`, change (around line 89-93):

```html
  <nav class="header-nav" aria-label="Main">
    <a class="nav-link" href="/citizen">For citizens</a>
    <a class="nav-link" href="/officials">For officials</a>
    <a class="nav-link on" href="/about" aria-current="page">How it works</a>
  </nav>
```

to:

```html
  <nav class="header-nav" aria-label="Main">
    <a class="nav-link" href="/citizen">For citizens</a>
    <a class="nav-link" href="/officials">For officials</a>
    <a class="nav-link on" href="/about" aria-current="page">How it works</a>
    <a class="nav-link" href="/login" id="signOutLink">Sign out</a>
  </nav>
```

Then, in the `<script>` block, right after the existing line `const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));` (current line 147), add:

```javascript
document.getElementById("signOutLink").addEventListener("click", (e) => {
  e.preventDefault();
  fetch("/api/logout", { method: "POST" }).finally(() => { window.location.href = "/login"; });
});
```

- [ ] **Step 6: Add the link and script to `landing.html`**

In `src/policy_wind_tunnel/service/static/landing.html`, change (around line 281-285):

```html
      <nav class="header-nav" aria-label="Main">
        <a class="nav-link primary" href="/citizen" data-i18n="nav1">For citizens</a>
        <a class="nav-link" href="/officials" data-i18n="nav2">For officials</a>
        <a class="nav-link" href="/about" data-i18n="nav3">How it works</a>
      </nav>
```

to:

```html
      <nav class="header-nav" aria-label="Main">
        <a class="nav-link primary" href="/citizen" data-i18n="nav1">For citizens</a>
        <a class="nav-link" href="/officials" data-i18n="nav2">For officials</a>
        <a class="nav-link" href="/about" data-i18n="nav3">How it works</a>
        <a class="nav-link" href="/login" id="signOutLink">Sign out</a>
      </nav>
```

Then, in the `<script>` block, right after the existing line `const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));` (current line 566), add:

```javascript
document.getElementById("signOutLink").addEventListener("click", (e) => {
  e.preventDefault();
  fetch("/api/logout", { method: "POST" }).finally(() => { window.location.href = "/login"; });
});
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_api.py -v -k sign_out_link`
Expected: `PASS`

- [ ] **Step 8: Run the full test suite**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest -q`
Expected: all tests `PASS` (adding one more `.nav-link` doesn't affect any existing string assertions — none of the existing tests assert an exact count of nav links)

- [ ] **Step 9: Commit**

```bash
cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy
git add src/policy_wind_tunnel/service/static/citizen.html src/policy_wind_tunnel/service/static/officials.html src/policy_wind_tunnel/service/static/about.html src/policy_wind_tunnel/service/static/landing.html tests/test_api.py
git commit -m "feat: add a Sign out link to every gated page"
```

---

### Task 6: Turn the gate on, wire config, final regression pass

**Files:**
- Modify: `src/policy_wind_tunnel/service/app.py:428-429` (the bottom of the file)
- Modify: `.env.example`
- Modify: `tests/conftest.py`
- Modify: `tests/test_api.py` (extend two existing "every page" loops to include `/login`)

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: the production `app` object, now actually gated — this is the task that makes the feature live.

- [ ] **Step 1: Write the failing test**

Add `/login` to the loop in the two existing tests in `tests/test_api.py`. Change:

```python
def test_every_page_has_a_skip_link_viewport_and_shared_stylesheet(client):
    for path in ("/", "/citizen", "/officials", "/about"):
```

to:

```python
def test_every_page_has_a_skip_link_viewport_and_shared_stylesheet(client):
    for path in ("/", "/citizen", "/officials", "/about", "/login"):
```

and change:

```python
def test_every_page_declares_its_icon(client):
    for path in ("/", "/citizen", "/officials", "/about"):
```

to:

```python
def test_every_page_declares_its_icon(client):
    for path in ("/", "/citizen", "/officials", "/about", "/login"):
```

(These should already pass immediately since Task 2 built `/login` to the same conventions — this step is a safety net, not a new behavior. If it fails, Task 2's `login.html` is missing one of the shared conventions and needs a fix before continuing.)

- [ ] **Step 2: Run the two tests to confirm they already pass**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest tests/test_api.py -v -k "skip_link_viewport or declares_its_icon"`
Expected: `PASS`

- [ ] **Step 3: Turn the gate on for the real app**

In `src/policy_wind_tunnel/service/app.py`, change the bottom of the file from:

```python
settings.load_env()
app = create_app()
```

to:

```python
settings.load_env()
app = create_app(enable_login_gate=True)
```

- [ ] **Step 4: Add the new env vars to `.env.example`**

Append to `.env.example`:

```
# Login gate: a whitelist of emails (comma-separated) sharing one password.
# Demo-only access control, not a real identity provider.
PWT_LOGIN_EMAILS=demo1@example.com,demo2@example.com
PWT_LOGIN_PASSWORD=change-me
# Signs the session cookie. If left blank, a random one is generated per
# process (sessions won't survive a restart) and a warning is logged.
PWT_SESSION_SECRET=
```

- [ ] **Step 5: Isolate the new env vars in `conftest.py`**

In `tests/conftest.py`, change:

```python
ENV_KEYS = (
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "PWT_MODEL",
    "PWT_LIVE_LEADERS",
)
```

to:

```python
ENV_KEYS = (
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "PWT_MODEL",
    "PWT_LIVE_LEADERS",
    "PWT_LOGIN_EMAILS",
    "PWT_LOGIN_PASSWORD",
    "PWT_SESSION_SECRET",
)
```

- [ ] **Step 6: Run the full test suite one more time**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && .venv/bin/pytest -q`
Expected: all tests `PASS`. This is the final check that flipping the production app to `enable_login_gate=True` (which no test exercises directly — every test still builds its own `create_app()` without the flag) hasn't broken anything, and that `tests/test_login.py`'s dedicated `gated_client` fixture still covers the real gated behavior end to end.

- [ ] **Step 7: Manually smoke-test the running app**

Run: `cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy && PWT_LOGIN_EMAILS=you@example.com PWT_LOGIN_PASSWORD=test-password .venv/bin/uvicorn policy_wind_tunnel.service.app:app --reload` and in a browser:
1. Visit `http://127.0.0.1:8000/` → confirm it redirects to `/login`.
2. Try a wrong password → confirm the generic error appears, no page navigation.
3. Sign in with `you@example.com` / `test-password` → confirm you land on `/`.
4. Click "Sign out" in the header → confirm you're bounced back to `/login`.
5. Stop the server (Ctrl+C).

- [ ] **Step 8: Commit**

```bash
cd /Users/piyush.maheshwari2/Tech/Hackathon/mr-policy
git add src/policy_wind_tunnel/service/app.py .env.example tests/conftest.py tests/test_api.py
git commit -m "feat: turn the login gate on for the deployed app"
```

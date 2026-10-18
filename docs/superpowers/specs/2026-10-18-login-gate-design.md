# Login gate — design spec

Date: 2026-10-18

## Purpose

Policy Wind Tunnel currently serves four static pages (`/`, `/citizen`, `/officials`, `/about`) with no session concept at all. We're adding a login gate in front of all of them: a whitelist of allowed emails (a mix of real and mock addresses) sharing a single password for now. This is not an integration with any real identity provider — it's a small homegrown check, built to feel like an ordinary login page to anyone using it, while staying honest in the code about being a demo-grade gate.

## Out of scope

- Per-user accounts, roles, or permissions — there is exactly one shared credential set; "logged in" is a single boolean, not an identity.
- Password reset, sign-up, "remember me," multi-factor, or any other account-management flow.
- Real identity provider integration (OAuth, SSO, etc.).
- Protecting against a determined attacker. The goal is to stop casual/unauthenticated browsing, not to be a security boundary.

## 1. Page design

New page at `/login`, served as a static HTML file the same way the other four pages are (`src/policy_wind_tunnel/service/static/login.html`, returned via a new `@app.get("/login")` route).

- Visual language matches `citizen.html` / `officials.html` exactly: same `:root` CSS custom properties (`--ink`, `--green`, `--green-dark`, `--page`, `--line`, etc.), same `"DM Sans"` body / `Manrope` heading fonts, same `.site-header`, `.wrap`, `.card`, input, and primary-button styles. This is layout **C** from the brainstorming mockups: a plain white card centered on the light `--page` background — not the landing page's dark photo hero.
- Header: brand mark + "Policy Wind Tunnel" wordmark only. No nav links on this page (there is nothing reachable yet pre-login).
- Card content:
  - Eyebrow: "SIGN IN"
  - Heading: "Welcome back"
  - Email input (`type=email`, required)
  - Password input (`type=password`, required)
  - Primary button: "Sign in"
  - Inline error line (reuses the existing `.err` text style), empty until a failed attempt, `role="alert"`
- Deliberately **no** "Forgot password?" and **no** "Sign up" link. This reads as a normal internal/invite-only tool and avoids drawing attention to the fact that access is whitelist-based.
- Error copy is a single generic message for every failure mode: **"That email or password is incorrect."** It must never differ depending on whether the email was recognized — that would leak the existence of a whitelist.
- English only. No language switcher on this page (the landing page's hi/mr switcher is not replicated here).
- Once logged in, every other page's header nav gets one more link: **"Sign out"** (styled like the existing `.nav-link`), which calls `POST /api/logout` then redirects to `/login`.

## 2. Auth mechanism

No new third-party dependency (no `itsdangerous`, no auth library) — implemented with the standard library (`hmac`, `hashlib`, `secrets`) directly in `app.py`.

### Credentials

- `PWT_LOGIN_EMAILS` — comma-separated list of allowed emails (matched case-insensitively, whitespace-trimmed).
- `PWT_LOGIN_PASSWORD` — the single shared password, compared with `hmac.compare_digest` (constant-time) to avoid trivial timing attacks.
- `PWT_SESSION_SECRET` — server-side secret used to sign the session cookie's value. If unset at startup, the server generates a random one in memory (sessions won't survive a restart, which is acceptable for this use case) and logs a warning.

All three are read from the environment (`.env`, already gitignored in this repo) — never committed with real values.

### Login endpoint

`POST /api/login`, JSON body `{ "email": str, "password": str }`:

1. Normalize email (`strip().lower()`), compare against the parsed `PWT_LOGIN_EMAILS` set.
2. Compare password via `hmac.compare_digest`.
3. On success: set cookie `pwt_session=<token>`, where `<token> = hmac.new(secret, b"pwt-authenticated", hashlib.sha256).hexdigest()`. This is a single fixed token (there's only one "identity" to represent), signed so it can't be forged by guessing — a user can't just set `document.cookie="pwt_session=ok"` in devtools, they'd need the server secret to produce a valid token.
   - Cookie flags: `HttpOnly`, `SameSite=Lax`, `Secure` set dynamically (`request.url.scheme == "https"`), **no `Max-Age`/`Expires`** — a true session cookie that disappears when the browser closes, per the "persist for browser session" decision.
4. On failure: respond `401` with `{"detail": "That email or password is incorrect."}` — same message and same status for unknown email vs. wrong password.

`POST /api/logout`: clears the `pwt_session` cookie (`Set-Cookie` with `Max-Age=0`) and returns `{"ok": true}`.

### Gate

A small FastAPI dependency/middleware applied to every route **except**:

- `GET /login`
- `GET /favicon.ico`
- anything under `/static/*`
- `POST /api/login`
- `POST /api/logout`

For everything else:

- If the request path starts with `/api/` → missing/invalid cookie returns `401` JSON (so a direct `curl`/fetch to e.g. `/api/chat` can't bypass the login page).
- Otherwise (an HTML page) → missing/invalid cookie returns a `302` redirect to `/login`.

Validity check: recompute the expected token from `PWT_SESSION_SECRET` and compare to the cookie value with `hmac.compare_digest`.

After a **successful** login, the client always redirects to `/` — never back to whatever page originally triggered the gate (confirmed earlier; no `?next=` param is used or needed).

## 3. Config & rollout behavior

- `.env.example` gets three new placeholder entries:
  ```
  PWT_LOGIN_EMAILS=demo1@example.com,demo2@example.com
  PWT_LOGIN_PASSWORD=change-me
  PWT_SESSION_SECRET=
  ```
  (left blank/placeholder on purpose — real values, including the real+mock email mix, are set locally and on Cloud Run, never committed.)
- **Fail-open-to-login, not fail-open-to-content:** if `PWT_LOGIN_EMAILS` or `PWT_LOGIN_PASSWORD` is unset or empty at startup, the app still boots (doesn't crash) and the gate still redirects everyone to `/login` as normal — but the login endpoint will reject every attempt until both are configured, since there's nothing to match against. This means a contributor who clones the repo without setting these env vars sees a working login page that correctly refuses everyone, rather than either crashing the app or accidentally leaving every page open.
- No changes to `/api/health`, `/api/demo`, etc. beyond being covered by the general gate like any other `/api/*` route.

## Testing notes for the implementation plan

- Verify: visiting `/`, `/citizen`, `/officials`, `/about` while logged out redirects to `/login`.
- Verify: `/login`, `/static/*` assets, and the favicon load without a cookie.
- Verify: correct email+password sets the cookie and lands on `/`; wrong password, wrong email, and empty fields all show the same generic error.
- Verify: direct `fetch`/`curl` to a protected `/api/*` route without the cookie gets `401`, not data.
- Verify: "Sign out" clears the cookie and a subsequent page load redirects to `/login`.
- Verify: cookie has no `Max-Age`, so a closed-and-reopened browser is logged out again (manual check, since this isn't something an automated test can easily simulate).

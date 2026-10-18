import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.service.app import create_app

EMAIL = "demo@example.com"
PASSWORD = "shared-demo-password"


@pytest.fixture()
def configured_client(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", f"{EMAIL}, other@example.com")
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", PASSWORD)
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


def test_each_login_gets_a_distinct_session_token(configured_client):
    configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    token_a = configured_client.cookies["pwt_session"]
    configured_client.post("/api/logout")
    configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    token_b = configured_client.cookies["pwt_session"]
    assert token_a != token_b


def test_logging_out_one_session_does_not_affect_another(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", EMAIL)
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", PASSWORD)
    app = create_app(llm=None, enable_login_gate=True)
    browser_a = TestClient(app)
    browser_b = TestClient(app)
    browser_a.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    browser_b.post("/api/login", json={"email": EMAIL, "password": PASSWORD})

    browser_a.post("/api/logout")

    assert browser_a.get("/", follow_redirects=False).status_code == 302
    assert browser_b.get("/").status_code == 200


def test_a_revoked_token_cannot_be_replayed_even_if_someone_captured_it(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", EMAIL)
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", PASSWORD)
    client = TestClient(create_app(llm=None, enable_login_gate=True))
    client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    captured_token = client.cookies["pwt_session"]
    client.post("/api/logout")

    client.cookies.set("pwt_session", captured_token)
    replay = client.get("/", follow_redirects=False)
    assert replay.status_code == 302


def test_too_many_failed_attempts_are_rate_limited(configured_client):
    for _ in range(5):
        configured_client.post("/api/login", json={"email": EMAIL, "password": "wrong"})
    blocked = configured_client.post("/api/login", json={"email": EMAIL, "password": "wrong"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many attempts. Try again in a minute."


def test_a_correct_login_is_still_blocked_once_rate_limited(configured_client):
    for _ in range(5):
        configured_client.post("/api/login", json={"email": EMAIL, "password": "wrong"})
    blocked = configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    assert blocked.status_code == 429
    assert "pwt_session" not in configured_client.cookies


def test_successful_login_clears_the_failed_attempt_counter(configured_client):
    for _ in range(4):
        configured_client.post("/api/login", json={"email": EMAIL, "password": "wrong"})
    ok = configured_client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
    assert ok.status_code == 200
    configured_client.post("/api/logout")

    last = None
    for _ in range(4):
        last = configured_client.post("/api/login", json={"email": EMAIL, "password": "wrong"})
    assert last.status_code == 401  # still under the limit, proving the earlier 4 failures were cleared


GATE_BLOCKED_MESSAGE = "Sign in required."


@pytest.fixture()
def gated_client(monkeypatch):
    monkeypatch.setenv("PWT_LOGIN_EMAILS", f"{EMAIL}, other@example.com")
    monkeypatch.setenv("PWT_LOGIN_PASSWORD", PASSWORD)
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

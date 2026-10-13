import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel import settings
from policy_wind_tunnel.service.app import create_app

KEYS = ("GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "PWT_MODEL", "PWT_LIVE_LEADERS")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def write_env(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text)
    return path


def test_values_are_loaded_from_an_env_file(tmp_path, monkeypatch):
    path = write_env(tmp_path, "GOOGLE_API_KEY=abc123\nPWT_MODEL=gemini-test\n")
    settings.load_env(path)
    import os

    assert os.environ["GOOGLE_API_KEY"] == "abc123" and os.environ["PWT_MODEL"] == "gemini-test"


def test_a_real_environment_variable_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PWT_MODEL", "from-shell")
    settings.load_env(write_env(tmp_path, "PWT_MODEL=from-file\n"))
    import os

    assert os.environ["PWT_MODEL"] == "from-shell"


def test_a_missing_env_file_is_fine(tmp_path):
    assert settings.load_env(tmp_path / "nope.env") is False


def test_model_defaults_when_unset_and_follows_the_variable(monkeypatch):
    assert settings.model_name() == "gemini-2.5-flash"
    monkeypatch.setenv("PWT_MODEL", "gemini-other")
    assert settings.model_name() == "gemini-other"


def test_a_blank_model_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("PWT_MODEL", "   ")
    assert settings.model_name() == "gemini-2.5-flash"


def test_credentials_are_detected_for_an_api_key(monkeypatch):
    assert settings.credential_mode() == "none"
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    assert settings.credential_mode() == "api_key"


def test_credentials_are_detected_for_vertex(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
    assert settings.credential_mode() == "vertex"


def test_vertex_needs_a_project(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    assert settings.credential_mode() == "none"


def test_a_blank_key_does_not_count(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "  ")
    assert settings.credential_mode() == "none"


def test_describe_never_contains_the_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "super-secret-value-123")
    text = repr(settings.describe())
    assert "super-secret-value-123" not in text
    assert settings.describe() == {"model": "gemini-2.5-flash", "credentials": "api_key", "live_leaders": True}


def test_describe_reports_the_kill_switch(monkeypatch):
    monkeypatch.setenv("PWT_LIVE_LEADERS", "0")
    assert settings.describe()["live_leaders"] is False


def test_health_reports_model_and_credential_mode_but_not_the_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "super-secret-value-123")
    body = TestClient(create_app()).get("/api/health").json()
    assert body["llm"] is True and body["model"] == "gemini-2.5-flash" and body["credentials"] == "api_key"
    assert "super-secret-value-123" not in str(body)


def test_health_with_no_credentials_says_so():
    body = TestClient(create_app()).get("/api/health").json()
    assert body["llm"] is False and body["credentials"] == "none"

import pytest

from policy_wind_tunnel import settings

ENV_KEYS = (
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "PWT_MODEL",
    "PWT_LIVE_LEADERS",
    "PWT_LOGIN_EMAILS",
    "PWT_LOGIN_PASSWORD",
)


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch, tmp_path):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / "no-such.env")

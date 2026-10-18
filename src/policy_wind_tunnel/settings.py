import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "gemini-2.5-flash"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path = ENV_FILE) -> bool:
    return load_dotenv(path, override=False) if path.exists() else False


def model_name() -> str:
    return os.environ.get("PWT_MODEL", "").strip() or DEFAULT_MODEL


def credential_mode() -> str:
    if os.environ.get("GOOGLE_API_KEY", "").strip():
        return "api_key"
    vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("1", "true", "yes")
    if vertex and os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip():
        return "vertex"
    return "none"


def live_leaders_enabled() -> bool:
    return os.environ.get("PWT_LIVE_LEADERS", "1").strip() != "0"


def login_emails() -> set[str]:
    raw = os.environ.get("PWT_LOGIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def login_password() -> str:
    return os.environ.get("PWT_LOGIN_PASSWORD", "")


def describe() -> dict[str, object]:
    return {"model": model_name(), "credentials": credential_mode(), "live_leaders": live_leaders_enabled()}

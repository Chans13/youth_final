"""Configuration for the Youth Center MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_API_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_TRANSPORT = "streamable-http"
DEFAULT_TIMEOUT_SECONDS = 15.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_CANDIDATES = (Path.cwd() / ".env", PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables."""

    open_api_key: str
    youth_center_api_url: str
    host: str
    port: int
    transport: str
    timeout_seconds: float


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _get_first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return ""


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_dotenv() -> None:
    """Load local .env values without overriding real environment variables."""

    for dotenv_path in dict.fromkeys(DOTENV_CANDIDATES):
        if not dotenv_path.is_file():
            continue
        for line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip()
            if not name:
                continue
            if os.environ.get(name, "") != "":
                continue
            os.environ[name] = _strip_quotes(value.strip())


def get_settings() -> Settings:
    """Load settings from process environment."""

    _load_dotenv()

    return Settings(
        open_api_key=_get_first_env(
            "OPEN_API_KEY",
            "open_api_key",
            "YOUTH_CENTER_API_KEY",
            "YOUTHCENTER_API_KEY",
            "YOUTHCENTER_API_KEY_POLICY",
        ),
        youth_center_api_url=os.getenv(
            "YOUTH_CENTER_API_URL", DEFAULT_API_URL
        ).strip(),
        host=os.getenv("MCP_HOST", DEFAULT_HOST),
        port=_get_int("MCP_PORT", DEFAULT_PORT),
        transport=os.getenv("MCP_TRANSPORT", DEFAULT_TRANSPORT),
        timeout_seconds=_get_float(
            "YOUTH_CENTER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
        ),
    )

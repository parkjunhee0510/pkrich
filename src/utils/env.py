from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        sanitize_proxy_environment()
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip("\ufeff").strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip().lstrip("\ufeff")
        os.environ.setdefault(normalized_key, normalize_env_value(value))

    sanitize_proxy_environment()


def is_env_flag_enabled(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def sanitize_proxy_environment() -> None:
    for name in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        value = os.getenv(name)
        if value and _is_broken_local_proxy(value):
            os.environ.pop(name, None)


def normalize_env_value(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        return normalized[1:-1].strip()
    return normalized


def _is_broken_local_proxy(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    hostname = (parsed.hostname or "").strip().lower()
    port = parsed.port
    return hostname in {"127.0.0.1", "localhost", "::1"} and port == 9

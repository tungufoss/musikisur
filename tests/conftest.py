import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from .env without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


_load_dotenv(ENV_FILE)


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls external APIs with real credentials")

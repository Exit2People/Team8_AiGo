"""환경 변수와 설정 값. 숫자는 PROMPTS/SHARED/04_CONSTANTS.md 기준."""

import os
from pathlib import Path

from dotenv import load_dotenv


def _find_root() -> Path:
    """위로 올라가며 data/reference 폴더가 있는 곳을 뿌리로 써요 (저장소 · 배포 폴더 둘 다)."""
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "data" / "reference").is_dir():
            return p
    return here.parent


ROOT = _find_root()
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def flag(name: str, default: bool = False) -> bool:
    v = env(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def cors_origins() -> list[str]:
    raw = env("AIGO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000") or ""
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def cors_regex() -> str:
    return env("AIGO_CORS_REGEX", r"https://aigo-final[a-z0-9-]*\.vercel\.app") or ""


def model() -> str:
    return env("AIGO_MODEL", "claude-sonnet-5-5") or "claude-sonnet-5-5"


def has_ai() -> bool:
    return bool(env("ANTHROPIC_API_KEY") or env("ANTHROPIC_AUTH_TOKEN"))


def has_jev() -> bool:
    return flag("AIGO_JEV") and bool(env("TYPESAFE_API_KEY"))

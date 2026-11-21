"""환경 변수와 설정 값. 숫자는 PROMPTS/SHARED/04_CONSTANTS.md 기준."""

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


def _find_root() -> Path:
    """위로 올라가며 data/reference 폴더가 있는 곳을 뿌리로 써요 (저장소 · 배포 폴더 둘 다)."""
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "data" / "reference").is_dir():
            return p
    return here.parent.parent


ROOT = _find_root()
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

KST = timezone(timedelta(hours=9))

# 04_CONSTANTS 1절
RADIUS_KM = (2.0, 5.0)
MAX_AI_QUESTIONS = 3
QUESTION_AI_TIMEOUT = 3.5
OPEN_AI_TIMEOUT = 5.0
RECOMMEND_TOTAL = 8.0
RECOMMEND_AI_MAX = 6.0
TRANSIT_TOP = 6
TRANSIT_TIMEOUT = 2.5
EXPAND_TIMEOUT = 3.5
INFO_TIMEOUT = 1.5
MAX_CANDIDATES = 3
AI_POOL = 20
AGENT_MAX_ROUNDS = 6
AGENT_TIMEOUT = 30.0
AGENT_RELAX_MIN = 20
# 30일 안에 다녀온 곳: 빼지 않고 점수만 깎아요. 다른 좋은 곳이 없으면 다시 추천돼요 (다시 가고 싶을 수 있어서)
VISITED_PENALTY = 0.5
# 규칙 추천에 다녀온 곳이 없을 때, 가장 잘 맞는 다녀온 곳이 3번째 후보와 이만큼 안쪽이면 3번째 자리에 넣어요
REVISIT_MARGIN = 1.0
# 지난 며칠 보여 줬지만 고르지 않은 곳: 점수를 깎아 다른 곳이 먼저 보이게 (빼지는 않아요)
SHOWN_PENALTY = 1.0
# 날짜별 섞기: 점수가 비슷한 곳끼리만 날마다 순서가 바뀌게 더하는 폭 (±절반)
DAILY_JITTER = 0.5
# 추천 3곳 가운데 다녀온 곳은 이만큼까지 (직접 말한 곳은 따로)
MAX_VISITED_SHOWN = 1
QUESTION_AGENT_TIMEOUT = 6.0
QUESTION_AGENT_ROUNDS = 2
QUESTION_JEV_NATURAL_MIN = 0.6
QUESTION_JEV_FIT_MIN = 0.35
QUESTION_FIXED = 3  # 첫 말(no 0) · 몸(no 1) · 시간(no 2)
QUESTION_MAX_LEN = 32  # 이어 받는 질문이 조금 길어져도 되게 (예전 25자)
QUESTION_SCREEN = 8.0  # 화면 Q_FALLBACK (04_CONSTANTS 3절). 질문 하나는 이 안에 답해요
QUESTION_SCREEN_MARGIN = 2.5  # 에이전트가 늦으면 발전 질문 · 은행으로 갈 자리. 8초에 바짝 붙지 않게 넉넉히 (실측 7.86초가 나왔어요)
EXTRA_MIN_LEFT = 8  # 1개 더(no 7)는 답으로 좁힌 뒤에도 이만큼 남았을 때만
EARLY_LEFT = 3  # 답으로 좁힌 곳이 이만큼 이하면 정해진 질문을 다 채우지 않고 일찍 끝내요 (EXTRA_MIN_LEFT 보다 작게)
EARLY_MIN_NO = 4  # 일찍 끝내기는 처음 말 · 몸 · 시간 뒤 질문을 하나 이상 물은 다음부터 (no 4부터)
JEV_TIMEOUT = 2.0
JEV_MIN_YES = 0.5
MIN_PER_TRANSFER = 5
MIN_STAY = 60
SESSION_DAYS = 30
CONSENT_VERSION = "2026-11-20"
RETENTION_DAYS = 90
EST_SLACK_MIN = 15
REC_WAIT = 20.0  # 화면 REC_FAIL (04_CONSTANTS 3절)


def env(name: str, default: str | None = None) -> str | None:
    # Vercel에 파이프로 넣은 값 끝의 줄바꿈 · 공백을 떼요 ("1\n"을 꺼짐으로 읽거나 키 인증이 깨지지 않게)
    v = os.environ.get(name)
    v = v.strip() if v is not None else None
    return v if v else default


def flag(name: str, default: bool = False) -> bool:
    v = env(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def cors_origins() -> list[str]:
    raw = env("AIGO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000") or ""
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def cors_regex() -> str:
    return env("AIGO_CORS_REGEX", r"https://(aigo-final|ai-go-team8)[a-z0-9-]*\.vercel\.app") or ""


def model() -> str:
    return env("AIGO_MODEL", "claude-sonnet-5-5") or "claude-sonnet-5-5"


def has_ai() -> bool:
    return bool(env("ANTHROPIC_API_KEY") or env("ANTHROPIC_AUTH_TOKEN"))


has_ai_key = has_ai


def has_jev_key() -> bool:
    return bool(env("TYPESAFE_API_KEY"))


def has_jev() -> bool:
    return flag("AIGO_JEV") and has_jev_key()


def jev_model() -> str:
    return env("AIGO_JEV_MODEL", "jev-latest") or "jev-latest"


def question_mode() -> str:
    return env("AIGO_QUESTION", "graph") or "graph"


def question_start() -> str:
    return env("AIGO_QUESTION_START", "open") or "open"


def agent_on() -> bool:
    # exp/agent-full: 이 브랜치에서는 추천 에이전트가 기본으로 켜져요 (끄려면 AIGO_AGENT=0)
    return (env("AIGO_AGENT", "1") or "1") == "1"


def question_total() -> int:
    """질문 수 고정 (첫 말 · 몸 · 시간 포함). AIGO_QUESTION_TOTAL, 기본 7."""
    try:
        n = int(env("AIGO_QUESTION_TOTAL", "7") or "7")
    except ValueError:
        n = 7
    return max(QUESTION_FIXED + 1, min(n, 12))


def question_agent_on() -> bool:
    return env("AIGO_QUESTION_AGENT") != "0"


def question_jev_on() -> bool:
    return env("AIGO_QUESTION_JEV") != "0"


def chat_jev_on() -> bool:
    return env("AIGO_CHAT_JEV") != "0"


def nickname_jev_on() -> bool:
    """키가 있으면 닉네임도 Jev로 한 번 더 봐요. 0이면 규칙만."""
    return env("AIGO_NICK_JEV") != "0"


def transit_on() -> bool:
    return (env("AIGO_TRANSIT", "on") or "on").lower() != "off"


def sync_frozen() -> bool:
    return flag("AIGO_SYNC_FREEZE")


def public_url() -> str:
    return (env("AIGO_PUBLIC_URL", "http://localhost:3000") or "").rstrip("/")


def ref_dir() -> Path:
    return Path(env("AIGO_REF_DIR") or ROOT / "data" / "reference")


def db_path() -> Path:
    return Path(env("AIGO_DB_PATH") or ROOT / "data" / "cache" / "aigo.db")


def snapshot_path() -> Path:
    return Path(env("AIGO_SNAPSHOT_PATH") or ROOT / "data" / "snapshot" / "aigo.db")


def now() -> datetime:
    """서울 시각. AIGO_NOW가 HH:MM이면 오늘 그 시각, ISO면 그 날짜 · 시각."""
    real = datetime.now(KST)
    raw = env("AIGO_NOW")
    if not raw:
        return real
    raw = raw.strip()
    try:
        if "T" in raw:
            dt = datetime.fromisoformat(raw)
            return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", raw)
        if m:
            return real.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    except ValueError:
        pass
    return real

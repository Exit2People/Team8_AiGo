"""매번 새로운 질문 (SHARED_EXPERIMENT 0-1). AIGO_QUESTION_VARIETY 기본 1, 0이면 늘 같은 질문.

- 서버 메모리에 최근에 낸 질문 문장 50개를 둬요 (로그인 · DB 없이, 서버가 다시 뜨면 비어요).
- 질문 에이전트에는 최근 질문과 "이번 각도"를 주고, 같은 뜻이어도 말투 · 순서를 바꾸게 해요 (AI 호출 수 · 시간은 그대로).
- 대신 길(은행 · 발전 질문)은 미리 만든 다른 말투 중에서 최근에 안 쓴 것을 고르고, 선택지 순서를 섞어요.
- 시험은 AIGO_QUESTION_SEED 로 씨앗을 고정하거나 스위치를 꺼요.
"""

import random
import re
from collections import deque

from app import config

RECENT_MAX = 50
_recent: deque[str] = deque(maxlen=RECENT_MAX)
_rng: random.Random | None = None
_seed: str | None = None

ANGLES = [
    "어르신이 처음 한 말 속 낱말 하나를 골라 그걸 더 구체적으로 물어요.",
    "바로 앞 답을 받아서 '그럼 ~은 어떠세요?'처럼 이어 물어요.",
    "같이 가는 사람이 즐길 거리 쪽에서 물어요 (같이 가는 사람이 있을 때).",
    "어떤 분위기 · 느낌이 좋은지로 물어요.",
    "오늘 갈 수 있는 곳 이름 두세 곳을 바로 견주게 물어요.",
    "가서 무엇을 하고 싶은지(보기 · 해 보기 · 쉬기)로 물어요.",
]


def on() -> bool:
    return config.env("AIGO_QUESTION_VARIETY", "1") != "0"


def rng() -> random.Random:
    global _rng, _seed
    seed = config.env("AIGO_QUESTION_SEED")
    if _rng is None or seed != _seed:
        _seed = seed
        _rng = random.Random(seed) if seed is not None else random.Random()
    return _rng


def _norm(s: str) -> str:
    return re.sub(r"[\s?.!,·~]", "", s or "")


def remember(question: str | None) -> None:
    if question and on():
        _recent.append(question)


def recent(n: int = RECENT_MAX) -> list[str]:
    return list(_recent)[-n:]


def clear() -> None:
    _recent.clear()


def used(question: str) -> int:
    k = _norm(question)
    return sum(1 for q in _recent if _norm(q) == k)


def pick_text(options: list[str]) -> str:
    """최근에 덜 쓴 말투 중 하나 (꺼져 있으면 늘 첫 번째)."""
    if not on() or len(options) <= 1:
        return options[0]
    low = min(used(o) for o in options)
    fresh = [o for o in options if used(o) == low]
    return rng().choice(fresh)


def shuffle(choices: list[str]) -> list[str]:
    if not on() or len(choices) <= 1:
        return list(choices)
    out = list(choices)
    rng().shuffle(out)
    return out


def angle() -> str | None:
    return rng().choice(ANGLES) if on() else None

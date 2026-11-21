"""TypeSafe Jev (yes 확률). 실패는 None, 402 → 300초 · 429 → 60초 쉬어요."""

import asyncio
import logging
import time

import httpx

from app import config

log = logging.getLogger("aigo.jev")

URL = "https://api.typesafe.ai/v1/systemone"
_cool_until = 0.0


def cooling() -> bool:
    return time.monotonic() < _cool_until


def reset() -> None:
    global _cool_until
    _cool_until = 0.0


async def _post(body: dict, timeout: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as c:
        return await c.post(URL, json=body, headers={"Authorization": f"Bearer {config.env('TYPESAFE_API_KEY')}"})


async def ask_many(state, questions: dict[str, str], timeout: float) -> dict[str, float] | None:
    global _cool_until
    if not config.has_jev_key() or timeout <= 0 or not questions or cooling():
        return None
    body = {
        "model": config.jev_model(),
        "state": state,
        "questions": {k: {"type": "noul", "instructions": q} for k, q in questions.items()},
    }
    try:
        r = await asyncio.wait_for(_post(body, timeout), timeout=timeout)
    except Exception as e:
        log.warning("Jev 오류: %s", type(e).__name__)
        return None
    if r.status_code == 402:
        _cool_until = time.monotonic() + 300
        return None
    if r.status_code == 429:
        _cool_until = time.monotonic() + 60
        return None
    if r.status_code != 200:
        log.warning("Jev 상태 %s", r.status_code)
        return None
    try:
        answers = r.json()["answers"]
        out = {}
        for k in questions:
            v = float(answers[k]["noul"])
            if not 0.0 <= v <= 1.0:
                return None
            out[k] = v
        return out
    except (ValueError, KeyError, TypeError):
        return None


async def ask_yes(state, question: str, timeout: float) -> float | None:
    r = await ask_many(state, {"q": question}, timeout)
    return None if r is None else r["q"]

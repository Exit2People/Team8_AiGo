"""AI가 쓴 이유가 자료와 맞는지 검사 (04_CONSTANTS 9절) + Jev."""

import asyncio
import re

from app import config

_ZERO = ("갈아타지 않", "환승 없", "환승 안", "한 번에 가", "갈아탈 필요")
_ONE = ("한 번만 갈아", "1번만 갈아", "한 번 갈아", "환승 한 번", "환승 1번")


def check(reason: str, item: dict) -> bool:
    r = (reason or "").strip()
    if not r or len(r) > 60:
        return False
    route = item["route"]
    p = item["place"]
    t = route.get("transfers", 0)
    if any(k in r for k in _ZERO) and t != 0:
        return False
    if any(k in r for k in _ONE) and t != 1:
        return False
    for m in re.finditer(r"(\d+)\s*번\s*(만\s*)?(갈아|환승)", r):
        if int(m.group(1)) != t:
            return False
    last = next((lg for lg in route.get("legs") or [] if lg.get("kind") == "하차"), {})
    ok_min = {route.get("totalMin"), last.get("walkMin"), p.get("walkMin")}
    for m in re.finditer(r"(\d+)\s*분", r):
        if int(m.group(1)) not in ok_min:
            return False
    if "실내" in r and p.get("inout") == "바깥":
        return False
    if ("바깥" in r or "야외" in r) and p.get("inout") == "실내":
        return False
    if "엘리베이터" in r and not p.get("elevatorExit"):
        return False
    if "계단 없" in r and "계단" in (p.get("terrain") or []):
        return False
    # 요금 · 시간 길이는 자료로 확인할 수 있을 때만 써요
    if "무료" in r and ((p.get("info") or {}).get("fee") or {}).get("free") is not True:
        return False
    if re.search(r"\d+\s*(천|만)?\s*원", r) or re.search(r"\d+\s*시간", r):
        return False
    return True


def verify_picks(picks: list[dict], items: list[dict]) -> list[dict]:
    by = {it["place"]["id"]: it for it in items}
    seen: set[str] = set()
    out = []
    for pk in picks:
        pid = pk.get("id")
        it = by.get(pid)
        if not it or pid in seen or it.get("overEstimate"):
            continue
        if not check(pk.get("reason") or "", it):
            continue
        seen.add(pid)
        out.append({"item": it, "reason": pk["reason"].strip()})
    return out


async def confirm_by_jev(verified: list[dict], timeout: float | None = None) -> list[dict]:
    """timeout: 남은 시간 안에서만 확인해요. 0.3초보다 적게 남으면 건너뛰어요."""
    from app.llm import jev
    from app.recommend.pick import for_ai
    from app.recommend.prompts import VERIFY_JEV_QUESTION

    t = config.JEV_TIMEOUT if timeout is None else min(config.JEV_TIMEOUT, timeout)
    if not config.has_jev() or not verified or t < 0.3:
        return verified
    res = await asyncio.gather(*[
        jev.ask_yes({"장소 자료": for_ai(v["item"]), "추천 이유": v["reason"]}, VERIFY_JEV_QUESTION, t)
        for v in verified
    ])
    return [v for v, p in zip(verified, res) if p is None or p >= config.JEV_MIN_YES]

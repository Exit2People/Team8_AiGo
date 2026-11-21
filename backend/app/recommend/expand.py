"""말 넓혀 찾기: 바람이 목록에 그대로 없을 때만 AI 한 번."""

import re

from app import config
from app.question.opening import clean_hint
from app.recommend.wish import matches_place, place_text, wish_moods, wish_tokens
from app.schemas import Conditions, want_of

TOO_WIDE = {"공원", "구경", "장소", "명소", "관광", "나들이", "산책", "서울", "박물관", "미술관", "전시관", "전시",
            "체험관", "체험", "문화", "센터", "전망대"}


def wishes_of(cond: Conditions) -> list[str]:
    return [x for x in [cond.extra.place, *cond.extra.wish] if x]


def needs_expand(cond: Conditions, items: list[dict]) -> bool:
    wishes = wishes_of(cond)
    if not wishes or cond.extra.expanded:
        return False
    for it in items:
        p = it["place"]
        if matches_place(p, cond.extra.place):
            return False
        text = place_text(p)
        for w in cond.extra.wish:
            if wish_moods(w) & set(p.get("mood") or []) or any(t in text for t in wish_tokens(w)):
                return False
    return True


def tidy_words(words, wishes: list[str]) -> list[str]:
    out: list[str] = []
    for w in words or []:
        w = clean_hint(w, 6)
        if not w or w in TOO_WIDE or w in wishes or w in out:
            continue
        out.append(w)
    return out[:6]


def tidy_places(places) -> list[str]:
    out: list[str] = []
    for p in places or []:
        if not isinstance(p, str):
            continue
        p = re.sub(r"\s+", " ", p).strip()
        if not (2 <= len(p) <= 30) or not clean_hint(p, 30) or p in out:
            continue
        out.append(p)
    return out[:3]


async def expand(cond: Conditions, timeout: float) -> tuple[list[str], list[str]]:
    from app.llm.client import ask_json
    from app.recommend.prompts import EXPAND_SCHEMA, EXPAND_SYSTEM

    wishes = wishes_of(cond)
    v = await ask_json(EXPAND_SYSTEM, {"바란 것": wishes, "하고 싶은 것": want_of(cond)}, EXPAND_SCHEMA,
                       min(config.EXPAND_TIMEOUT, timeout))
    if not v:
        return [], []
    return tidy_words(v.get("words"), wishes), tidy_places(v.get("places"))

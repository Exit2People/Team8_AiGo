"""AI가 목록 밖에서 고른 시설을 카카오로 확인해 후보로 (서울 · 이름 같음 · 1곳일 때만)."""

import asyncio
import logging
import re

import httpx

from app import config
from app.data import geo, loader
from app.data.filter_places import filter_places, wants_free_only
from app.data.preferences import selected
from app.schemas import Conditions

log = logging.getLogger("aigo.map")

KAKAO_SEARCH = "https://dapi.kakao.com/v2/local/search/keyword.json"
LOOKUP_TIMEOUT = 1.0
REASON = "카카오맵에서 장소 위치를 확인했어요"
_SEOUL = re.compile(r"^서울(특별시)?\s+\S+구")


def _key(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def can_resolve(cond: Conditions, weather: str | None) -> bool:
    if selected(cond) or wants_free_only(cond) or weather in ("비", "눈"):
        return False
    if cond.basic.inout in ("실내가 좋아요", "바깥이 좋아요"):
        return False
    return not (cond.range.avoid or cond.extra.avoid)


def to_place(d: dict) -> dict | None:
    try:
        lat, lng = float(d["y"]), float(d["x"])
    except (KeyError, TypeError, ValueError):
        return None
    near = geo.nearest_station(lat, lng)
    if not near:
        return None
    st, dist = near
    wm = geo.walk_minutes_round(dist)
    cat = (d.get("category_name") or "").split(">")[-1].strip() or "장소"
    return {
        "id": f"KAKAO:{d['id']}", "name": d.get("place_name"), "kind": cat, "gu": (d.get("address_name") or "").split()[1]
        if len((d.get("address_name") or "").split()) > 1 else None,
        "station": st["name"], "exit": None, "walkMin": wm, "walkLevel": 1 if wm <= 5 else (2 if wm <= 12 else 3),
        "terrain": [], "closed": [], "always": False, "elevatorExit": None, "lat": lat, "lng": lng, "source": "kakao",
        "info": {"photo": None, "fee": {"free": None, "text": None}, "phone": d.get("phone") or None,
                 "homepage": f"https://place.map.kakao.com/{d['id']}"},
        "inout": None, "inoutBy": None, "wants": [], "mood": [],
    }


async def _lookup(c: httpx.AsyncClient, name: str) -> dict | None:
    r = await c.get(KAKAO_SEARCH, params={"query": f"서울 {name}"},
                    headers={"Authorization": f"KakaoAK {config.env('KAKAO_REST_API_KEY')}"})
    if r.status_code != 200:
        return None
    j = r.json()
    docs = j.get("documents") or []
    ok = []
    for i, d in enumerate(docs):
        addr = d.get("road_address_name") or d.get("address_name") or ""
        try:
            lat, lng = float(d.get("y")), float(d.get("x"))
        except (TypeError, ValueError):
            continue
        if (_SEOUL.match(addr) and str(d.get("id", "")).isdigit() and _key(d.get("place_name")) == _key(name)
                and 37 <= lat <= 38 and 126 <= lng <= 128):
            ok.append((i, d))
    if len(ok) != 1:
        return None
    i, d = ok[0]
    if not (j.get("meta") or {}).get("is_end", True) and i != 0:
        return None
    return d


async def resolve(names: list[str], cond: Conditions, now, weather: str | None, timeout: float,
                  visited: list[str] | tuple = ()) -> list[dict]:
    if timeout <= 0 or not names or not config.env("KAKAO_REST_API_KEY") or not can_resolve(cond, weather):
        return []
    try:
        async with httpx.AsyncClient(timeout=LOOKUP_TIMEOUT) as c:
            res = await asyncio.wait_for(asyncio.gather(*[_lookup(c, n) for n in names], return_exceptions=True),
                                         timeout=min(LOOKUP_TIMEOUT, timeout))
    except Exception as e:
        log.warning("카카오 확인 오류: %s", type(e).__name__)
        return []
    db = loader.places()
    places = []
    for d in res:
        if isinstance(d, Exception) or not d:
            continue
        p = to_place(d)
        if not p:
            continue
        dup = any(_key(q.get("name")) == _key(p["name"]) and q.get("lat") is not None
                  and geo.distance_m(q["lat"], q["lng"], p["lat"], p["lng"]) <= 500 for q in db)
        if not dup:
            places.append(p)
    # 이름 두 개가 같은 곳을 가리키면 하나로, 다녀온 곳은 빼요
    places = list({p["id"]: p for p in places}.values())
    return filter_places(cond, now, weather, list(visited), places=places) if places else []

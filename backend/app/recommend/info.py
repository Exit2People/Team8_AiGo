"""사진 · 요금 · 전화 · 걷는 길 붙이기. 실패한 칸만 비워요."""

import asyncio
import logging
import re

import httpx

from app import config
from app.data import geo, loader

log = logging.getLogger("aigo.info")

KAKAO_SEARCH = "https://dapi.kakao.com/v2/local/search/keyword.json"
TMAP_WALK = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"
KAKAO_RADIUS_M = 500

_PHONE = re.compile(r"(0\d{1,2}[\s.\-)]*\d{3,4}[\s.\-]*\d{4}|1\d{3}[\s.\-]*\d{4})")


def tidy_phone(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    m = _PHONE.search(text)
    if not m:
        return text, text
    num = re.sub(r"[\s.)]+", "-", m.group(1))
    num = re.sub(r"-+", "-", num).strip("-")
    return num, text


def _base(p: dict) -> dict:
    info = {"photo": None, "fee": None, "phone": None, "phoneText": None, "homepage": None, "walk": None}
    for k, v in (p.get("info") or {}).items():
        if k in info and v is not None:
            info[k] = v
    if info["phone"]:
        info["phone"], info["phoneText"] = tidy_phone(info["phone"])
    return info


async def _kakao_phone(c: httpx.AsyncClient, p: dict) -> dict | None:
    key = config.env("KAKAO_REST_API_KEY")
    if not key or p.get("lat") is None:
        return None
    r = await c.get(KAKAO_SEARCH, headers={"Authorization": f"KakaoAK {key}"},
                    params={"query": p["name"], "x": p["lng"], "y": p["lat"], "radius": KAKAO_RADIUS_M,
                            "sort": "distance", "size": 5})
    if r.status_code != 200:
        return None
    name = (p.get("name") or "").replace(" ", "")
    for d in r.json().get("documents") or []:
        dn = (d.get("place_name") or "").replace(" ", "")
        if dn and (dn.startswith(name) or name.startswith(dn)):
            return {"phone": d.get("phone") or None, "homepage": d.get("place_url") or None}
    return None


async def _walk(c: httpx.AsyncClient, p: dict, station: dict) -> dict | None:
    key = config.env("TMAP_APP_KEY")
    if not key:
        return None
    body = {"startX": station["lng"], "startY": station["lat"], "endX": p["lng"], "endY": p["lat"],
            "startName": "%EC%97%AD", "endName": "%EC%9E%A5%EC%86%8C",
            "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO", "searchOption": "0"}
    r = await c.post(TMAP_WALK, json=body, headers={"appKey": key})
    if r.status_code != 200:
        return None
    props = r.json()["features"][0]["properties"]
    dist = int(props["totalDistance"])
    m = max(1, round(dist / geo.WALK_M_PER_MIN))
    if p.get("kind") == "공원" and m > int(p.get("walkMin") or 1) * 1.5 + 3:
        return None
    return {"fromStation": station["name"], "distanceM": dist, "min": m, "source": "tmap"}


async def _attach_one(c: httpx.AsyncClient, cand: dict, p: dict, route: dict) -> None:
    info = cand["info"]
    tasks = {}
    if not info["phone"] and p.get("source") != "kakao":
        tasks["phone"] = _kakao_phone(c, p)
    last = next((lg for lg in route.get("legs") or [] if lg.get("kind") == "하차"), {})
    st = loader.station_by_name(last.get("station") or p.get("station"))
    if st and p.get("lat") is not None and geo.distance_m(st["lat"], st["lng"], p["lat"], p["lng"]) <= 3000:
        tasks["walk"] = _walk(c, p, st)
    if not tasks:
        return
    res = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for k, v in zip(tasks, res):
        if isinstance(v, Exception) or not v:
            continue
        if k == "phone":
            if v.get("phone") and not info["phone"]:
                info["phone"], info["phoneText"] = tidy_phone(v["phone"])
            if v.get("homepage") and not info["homepage"]:
                info["homepage"] = v["homepage"]
        else:
            info["walk"] = v


async def attach(cands: list[dict], items: list[dict], budget: float) -> None:
    for cand, it in zip(cands, items):
        cand["info"] = _base(it["place"])
    if budget <= 0.1 or not (config.env("KAKAO_REST_API_KEY") or config.env("TMAP_APP_KEY")):
        return
    try:
        async with httpx.AsyncClient(timeout=min(config.INFO_TIMEOUT, budget)) as c:
            await asyncio.wait_for(
                asyncio.gather(*[_attach_one(c, cand, it["place"], it["route"]) for cand, it in zip(cands, items)],
                               return_exceptions=True),
                timeout=budget)
    except (asyncio.TimeoutError, Exception) as e:
        log.warning("정보 붙이기 늦음: %s", type(e).__name__)

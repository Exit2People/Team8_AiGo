"""실제 길 (서울시 환승경로 → TMAP). 하루 기억, 다시 재서 빼기."""

import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from app import config
from app.data import geo, loader

log = logging.getLogger("aigo.transit")

SEOUL_SUBWAY = "http://ws.bus.go.kr/api/rest/pathinfo/getPathInfoBySubway"
SEOUL_MIX = "http://ws.bus.go.kr/api/rest/pathinfo/getPathInfoByBusNSub"
TMAP = "https://apis.openapi.sk.com/transit/routes"

_cache: dict[tuple, list[dict]] = {}


def enabled() -> bool:
    return config.transit_on() and bool(config.env("DATA_GO_KR_SERVICE_KEY") or config.env("TMAP_APP_KEY"))


def bus_name(nm: str) -> str:
    import re

    nm = (nm or "").strip()
    m = re.fullmatch(r"(\d+)([가-힣]+)", nm)
    if m:
        return f"{m.group(1)}번 버스({m.group(2)})"
    if re.fullmatch(r"[가-힣]*\d+", nm):
        return f"{nm}번 버스"
    return f"{nm} 버스"


def _walk_round(m: float) -> int:
    return round(m * geo.DETOUR / geo.WALK_M_PER_MIN)


def seoul_to_route(item: dict, start: tuple[float, float], place: dict, now: datetime) -> dict | None:
    paths = item.get("pathList") or []
    if isinstance(paths, dict):
        paths = [paths]
    if not paths:
        return None
    legs = []
    buses = 0
    for i, p in enumerate(paths):
        nm = p.get("routeNm") or ""
        subway = bool(p.get("railLinkList")) or nm.endswith("호선") or nm.endswith("선")
        leg = {"kind": "탑승" if i == 0 else "환승", "station": p.get("fname"), "getOff": p.get("tname"),
               "mode": "지하철" if subway else "버스", "line": nm if subway else bus_name(nm)}
        if subway:
            rl = p.get("railLinkList")
            leg["stops"] = len(rl) if isinstance(rl, list) else (1 if rl else None)
        else:
            buses += 1
        legs.append(leg)
    try:
        f = paths[0]
        first = _walk_round(geo.distance_m(start[0], start[1], float(f["fy"]), float(f["fx"])))
        last_p = paths[-1]
        last = max(1, _walk_round(geo.distance_m(float(last_p["ty"]), float(last_p["tx"]), place["lat"], place["lng"])))
        ride = int(float(item.get("time")))
    except (KeyError, TypeError, ValueError):
        return None
    legs.append({"kind": "하차", "station": paths[-1].get("tname"), "exit": None, "walkMin": last})
    total = ride + first + last
    return {"totalMin": total, "arriveAt": (now + timedelta(minutes=total)).strftime("%H:%M"),
            "transfers": len(paths) - 1, "legs": legs, "source": "seoul", "firstWalkMin": first, "buses": buses}


def tmap_to_route(data: dict, now: datetime) -> dict | None:
    try:
        it = data["metaData"]["plan"]["itineraries"][0]
    except (KeyError, IndexError, TypeError):
        return None
    legs, buses, ride_s, walk_m, first = [], 0, 0, 0.0, None
    raw = it.get("legs") or []
    for lg in raw:
        mode = lg.get("mode")
        if mode == "WALK":
            walk_m += float(lg.get("distance") or 0)
            if first is None:
                first = max(0, round(float(lg.get("distance") or 0) / geo.WALK_M_PER_MIN))
            continue
        ride_s += float(lg.get("sectionTime") or 0)
        r = lg.get("route") or ""
        if mode == "BUS":
            line, m = f"{r.split(':')[-1]}번 버스", "버스"
            buses += 1
        elif mode == "SUBWAY":
            line, m = r.replace("수도권", "", 1).strip(), "지하철"
        elif mode == "EXPRESSBUS":
            line, m = "고속버스", "버스"
        elif mode == "TRAIN":
            line, m = "기차", "기차"
        else:
            line, m = "탈것", "탈것"
        stops = ((lg.get("passStopList") or {}).get("stationList") or [])
        legs.append({"kind": "탑승" if not legs else "환승", "station": (lg.get("start") or {}).get("name"),
                     "getOff": (lg.get("end") or {}).get("name"), "mode": m, "line": line,
                     "stops": max(0, len(stops) - 1) if stops else None})
    if not legs:
        return None
    last_walk = float((raw[-1].get("distance") or 0)) if raw and raw[-1].get("mode") == "WALK" else 0
    legs.append({"kind": "하차", "station": legs[-1]["getOff"], "exit": None,
                 "walkMin": max(1, round(last_walk / geo.WALK_M_PER_MIN))})
    total = max(1, round(ride_s / 60 + walk_m / geo.WALK_M_PER_MIN))
    transfers = it.get("transferCount")
    if transfers is None:
        transfers = len(legs) - 2
    return {"totalMin": total, "arriveAt": (now + timedelta(minutes=total)).strftime("%H:%M"),
            "transfers": int(transfers), "legs": legs, "source": "tmap", "firstWalkMin": first or 0, "buses": buses}


def choose(routes: list[dict], limit: int, from_dong: bool) -> dict | None:
    if not routes:
        return None

    def travel(r):
        return r["totalMin"] - (r.get("firstWalkMin", 0) if from_dong else 0)

    subway = [r for r in routes if r.get("buses", 0) == 0 and travel(r) <= limit]
    pool = subway or routes
    return sorted(pool, key=lambda r: (r["transfers"], r["totalMin"]))[0]


async def _seoul(start, place, now) -> list[dict] | None:
    key = config.env("DATA_GO_KR_SERVICE_KEY")
    if not key:
        return None
    from urllib.parse import unquote

    params = {"serviceKey": unquote(key), "resultType": "json", "startX": start[1], "startY": start[0],
              "endX": place["lng"], "endY": place["lat"]}
    async with httpx.AsyncClient(timeout=config.TRANSIT_TIMEOUT) as c:
        res = await asyncio.gather(c.get(SEOUL_SUBWAY, params=params), c.get(SEOUL_MIX, params=params),
                                   return_exceptions=True)
    routes, ok = [], False
    for r in res:
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        try:
            items = (r.json().get("msgBody") or {}).get("itemList") or []
        except ValueError:
            continue
        ok = True
        if isinstance(items, dict):
            items = [items]
        for it in items:
            rt = seoul_to_route(it, start, place, now)
            if rt:
                routes.append(rt)
    return routes if ok else None


async def _tmap(start, place, now) -> dict | None:
    key = config.env("TMAP_APP_KEY")
    if not key:
        return None
    body = {"startX": str(start[1]), "startY": str(start[0]), "endX": str(place["lng"]), "endY": str(place["lat"]),
            "count": 1, "lang": 0, "format": "json", "searchDttm": now.strftime("%Y%m%d%H%M")}
    async with httpx.AsyncClient(timeout=config.TRANSIT_TIMEOUT) as c:
        r = await c.post(TMAP, json=body, headers={"appKey": key, "accept": "application/json"})
    if r.status_code != 200:
        return None
    return tmap_to_route(r.json(), now)


async def find(start: tuple[float, float], place: dict, now: datetime, limit: int, from_dong: bool) -> dict | None:
    day = now.strftime("%Y-%m-%d")
    ck = ("seoul", round(start[0], 4), round(start[1], 4), place.get("id"), day)
    routes = _cache.get(ck)
    if routes is None:
        try:
            routes = await _seoul(start, place, now)
        except Exception as e:
            log.warning("서울시 길 오류: %s", type(e).__name__)
            routes = None
        if routes is not None:
            _cache[ck] = routes
    picked = choose(routes or [], limit, from_dong)
    if picked:
        return dict(picked)
    tk = ("tmap", round(start[0], 4), round(start[1], 4), place.get("id"), day)
    if tk in _cache:
        return dict(_cache[tk][0]) if _cache[tk] else None
    try:
        rt = await _tmap(start, place, now)
    except Exception as e:
        log.warning("TMAP 오류: %s", type(e).__name__)
        return None
    if rt:
        _cache[tk] = [rt]
        return dict(rt)
    return None


def origin_point(cond) -> tuple[float, float] | None:
    o = cond.origin
    if o.lat is not None and o.lng is not None:
        return o.lat, o.lng
    if o.type == "동":
        hit = loader.dong_by_id(o.id)
        if hit:
            return hit[1]["lat"], hit[1]["lng"]
    s = loader.station_by_name(o.name) or loader.station_by_id(o.id)
    return (s["lat"], s["lng"]) if s else None


def breaks(item: dict, rt: dict, cond, now: datetime) -> str | None:
    from app.data.filter_places import avoid_of, open_info

    if rt["totalMin"] - rt.get("startWalkMin", 0) > cond.range.oneWayMin:
        return "이동 시간"
    if "버스 환승" in avoid_of(cond) and rt["transfers"] > 0 and rt.get("buses", 0) > 0:
        return "버스 환승"
    if open_info(item["place"], now + timedelta(minutes=rt["totalMin"]))["ok"] is False:
        return "도착하면 닫혀요"
    return None


def _from_dong(rt: dict, cond, from_name: str, start_from: str | None) -> dict:
    from app.data.filter_places import avoid_of
    from app.data.route import start_tip

    if start_from:
        fw = int(rt.get("firstWalkMin") or 0)
        rt["startWalkMin"] = fw
        rt["legs"][0]["tip"] = start_tip(start_from, rt["legs"][0].get("station") or from_name, fw,
                                         cond.range.walk, avoid_of(cond))
    return rt


async def measure_all(items: list[dict], cond, now: datetime, budget: float) -> list[dict]:
    """주어진 곳을 모두 재요. 통과한 곳만 (길 바꿔서) 돌려줘요."""
    from app.data.filter_places import start_station

    start = origin_point(cond)
    if not items or start is None or budget <= 0.3 or not enabled():
        return []
    from_name, _, start_from = start_station(cond)
    tasks = [find(start, it["place"], now, cond.range.oneWayMin, bool(start_from)) for it in items]
    try:
        res = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=budget)
    except asyncio.TimeoutError:
        return []
    out = []
    for it, rt in zip(items, res):
        if isinstance(rt, Exception) or not rt:
            continue
        rt = _from_dong(rt, cond, from_name, start_from)
        if breaks(it, rt, cond, now):
            continue
        new = dict(it)
        new["route"] = rt
        new.pop("overEstimate", None)
        out.append(new)
    return out


async def refine(items: list[dict], cond, now: datetime, budget: float) -> tuple[list[dict], dict]:
    from app.recommend.pick import diverse_pool

    stats = {"asked": 0, "measured": 0, "dropped": {}}
    plain = [x for x in items if not x.get("overEstimate")]
    if not enabled() or not items or origin_point(cond) is None or budget <= 0.3:
        return diverse_pool(plain, cond, config.AI_POOL), stats
    targets = diverse_pool(items, cond, config.TRANSIT_TOP)
    stats["asked"] = len(targets)
    measured = await measure_all(targets, cond, now, min(config.TRANSIT_TIMEOUT, budget))
    stats["measured"] = len(measured)
    if not measured:
        return diverse_pool(plain, cond, config.AI_POOL), stats
    done = {m["place"]["id"] for m in measured}
    asked = {t["place"]["id"] for t in targets}
    rest = [x for x in diverse_pool(plain, cond, len(plain)) if x["place"]["id"] not in asked]
    stats["dropped"] = {"재서 뺌": len(asked) - len(done)}
    return (measured + rest)[: config.AI_POOL], stats

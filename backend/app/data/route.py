"""어림 길: 역 사이 직선거리로 시간을 어림해요 (estimated: true)."""

from datetime import datetime, timedelta

from app import config
from app.data import geo, loader

EST_WAIT_MIN = 4
EST_MIN_PER_KM = 2.2


def estimate_route(from_name: str, place: dict, now: datetime) -> dict | None:
    a = loader.station_by_name(from_name)
    b = loader.station_by_name(place.get("station"))
    if a is None or b is None:
        return None
    walk = int(place.get("walkMin") or 1)
    alight = {"kind": "하차", "station": b["name"], "exit": place.get("exit"), "walkMin": walk}
    if a["name"] == b["name"]:
        total, transfers, legs = walk, 0, [alight]
    else:
        common = [ln for ln in a.get("lines") or [] if ln in (b.get("lines") or [])]
        transfers = 0 if common else 1
        km = geo.distance_m(a["lat"], a["lng"], b["lat"], b["lng"]) / 1000
        ride = round(EST_WAIT_MIN + km * EST_MIN_PER_KM) + transfers * config.MIN_PER_TRANSFER
        total = ride + walk
        line = common[0] if common else ((a.get("lines") or [None])[0])
        board = {"kind": "탑승", "station": a["name"], "mode": "지하철"}
        if line:
            board["line"] = line
        legs = [board, alight]
    return {
        "totalMin": total,
        "arriveAt": (now + timedelta(minutes=total)).strftime("%H:%M"),
        "transfers": transfers,
        "legs": legs,
        "estimated": True,
    }


def start_tip(dong_name: str, station: str, minutes: int, walk_level: str, avoid: list[str]) -> str:
    tip = f"{dong_name}에서 {station}까지 걸어서 약 {minutes}분"
    if minutes > 10 and (walk_level in ("조금만", "가장 적게") or "계단" in avoid):
        tip += " · 걷기 힘드시면 택시를 타셔도 돼요"
    return tip


def find_route(from_name: str, place: dict, now: datetime, start_walk: int = 0, start_from: str | None = None,
               walk_level: str = "조금만", avoid: list[str] | None = None) -> dict | None:
    r = estimate_route(from_name, place, now + timedelta(minutes=start_walk))
    if r is None:
        return None
    if start_from:
        r["totalMin"] += start_walk
        r["arriveAt"] = (now + timedelta(minutes=r["totalMin"])).strftime("%H:%M")
        r["startWalkMin"] = start_walk
        r["legs"][0]["tip"] = start_tip(start_from, from_name, start_walk, walk_level, avoid or [])
    return r

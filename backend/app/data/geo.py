"""거리 · 걷는 시간 · 가까운 역."""

import math

from app import config
from app.data import loader

WALK_M_PER_MIN = 67
DETOUR = 1.3


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def walk_minutes(meters: float) -> int:
    return max(1, math.ceil(meters * DETOUR / WALK_M_PER_MIN))


def walk_minutes_round(meters: float) -> int:
    return max(1, round(meters * DETOUR / WALK_M_PER_MIN))


def nearest_station(lat: float, lng: float) -> tuple[dict, float] | None:
    best = None
    for s in loader.stations():
        d = distance_m(lat, lng, s["lat"], s["lng"])
        if best is None or d < best[1]:
            best = (s, d)
    return best


def nearby_stations(lat: float, lng: float) -> dict:
    ranked = sorted(
        ((distance_m(lat, lng, s["lat"], s["lng"]), s) for s in loader.stations()),
        key=lambda x: x[0],
    )
    for radius in config.RADIUS_KM:
        inside = [(d, s) for d, s in ranked if d <= radius * 1000][:4]
        if inside:
            return {
                "radiusKm": radius,
                "widened": radius != config.RADIUS_KM[0],
                "stations": [
                    {
                        "id": s["id"], "name": s["name"], "type": s.get("type") or "역",
                        "lines": list(s.get("lines") or []), "lat": s["lat"], "lng": s["lng"],
                        "distanceM": int(round(d / 10.0) * 10), "walkMin": walk_minutes(d),
                    }
                    for d, s in inside
                ],
            }
    return {"radiusKm": config.RADIUS_KM[-1], "widened": True, "stations": []}

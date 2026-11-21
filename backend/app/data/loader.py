"""자료 파일 읽기: 역 · 장소 · 구/동 · 시장 · 한강공원."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from app import config
from app.data import places_db

log = logging.getLogger("aigo.loader")

_stations: list[dict] | None = None


def _read_json(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _group_stations(rows: list[dict]) -> list[dict]:
    """같은 이름 역(환승역)을 하나로 묶고 노선을 합쳐요."""
    by: dict[str, dict] = {}
    for r in rows:
        name = r.get("name")
        if not name or r.get("lat") is None or r.get("lng") is None:
            continue
        if name in by:
            s = by[name]
            for ln in r.get("lines") or []:
                if ln not in s["lines"]:
                    s["lines"].append(ln)
            s["_n"] += 1
            s["_lat"] += float(r["lat"])
            s["_lng"] += float(r["lng"])
        else:
            by[name] = {
                "id": r.get("id"), "name": name, "type": r.get("type") or "역",
                "lines": list(r.get("lines") or []),
                "_n": 1, "_lat": float(r["lat"]), "_lng": float(r["lng"]),
            }
    out = []
    for s in by.values():
        n = s.pop("_n")
        s["lat"] = round(s.pop("_lat") / n, 6)
        s["lng"] = round(s.pop("_lng") / n, 6)
        out.append(s)
    return out


def stations() -> list[dict]:
    global _stations
    if _stations is not None:
        return _stations
    rows: list[dict] = []
    for db in (config.db_path(), config.snapshot_path()):
        p = db.parent / "stations.json"
        if p.is_file():
            try:
                data = _read_json(p)
            except (OSError, ValueError):
                continue
            if isinstance(data, list) and data:
                rows = data
                break
    _stations = _group_stations(rows)
    return _stations


def clear_cache() -> None:
    global _stations
    _stations = None
    places_db.clear_cache()
    districts.cache_clear()


def station_by_name(name: str | None) -> dict | None:
    if not name:
        return None
    for s in stations():
        if s["name"] == name:
            return s
    return None


def station_by_id(sid: str | None) -> dict | None:
    if not sid:
        return None
    for s in stations():
        if s["id"] == sid:
            return s
    return None


def places() -> list[dict]:
    return places_db.places()


def place_by_id(pid: str) -> dict | None:
    for p in places():
        if p.get("id") == pid:
            return p
    return None


@lru_cache(maxsize=1)
def districts() -> list[dict]:
    data = _read_json(config.ref_dir() / "seoul_dongs.json")
    return sorted(data["districts"], key=lambda d: d["gu"])


def dong_by_id(dong_id: str) -> tuple[str, dict] | None:
    for d in districts():
        for dong in d["dongs"]:
            if dong["id"] == dong_id:
                return d["gu"], dong
    return None


def dong_by_label(label: str | None) -> tuple[str, dict] | None:
    """`성동구 성수1가1동` 꼴 → (구, 동)."""
    if not label:
        return None
    parts = label.strip().split()
    if len(parts) != 2:
        return None
    for d in districts():
        if d["gu"] == parts[0]:
            for dong in d["dongs"]:
                if dong["name"] == parts[1]:
                    return d["gu"], dong
    return None


def _optional(name: str, key: str) -> list[dict]:
    try:
        data = _read_json(config.ref_dir() / name)
        return list(data.get(key) or [])
    except (OSError, ValueError, AttributeError):
        return []


def hangang_parks() -> list[dict]:
    return _optional("hangang_parks.json", "parks")


def markets() -> list[dict]:
    return _optional("seoul_markets.json", "markets")

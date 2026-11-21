"""장소 SQLite 읽기 (읽기 전용). 매일 만든 DB → 스냅숏 → 없으면 빈 목록."""

import json
import logging
import re
import sqlite3
from pathlib import Path

from app import config

log = logging.getLogger("aigo.places_db")

_cache: dict = {}
_WEEKLY = re.compile(r"매주\s*([월화수목금토일])요일")
_DAYS = "월화수목금토일"


def _fix_closed(p: dict) -> None:
    """쉬는 날 글에 '매주 월요일'이 있는데 closed 숫자에 빠진 곳을 채워요 (weekday: 월=0)."""
    text = (p.get("museum") or {}).get("closedText") or ""
    days = {_DAYS.index(d) for d in _WEEKLY.findall(text)}
    if days - set(p.get("closed") or []):
        p["closed"] = sorted(set(p.get("closed") or []) | days)


def current_path() -> Path | None:
    for p in (config.db_path(), config.snapshot_path()):
        if p.is_file():
            return p
    return None


def kind() -> str | None:
    p = current_path()
    if p is None:
        return None
    return "daily" if p == config.db_path() else "snapshot"


def _open(p: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def _load(p: Path) -> dict | None:
    key = (str(p), p.stat().st_mtime)
    if _cache.get("key") == key:
        return _cache["value"]
    try:
        con = _open(p)
        try:
            hidden = {r[0] for r in con.execute("select id from overrides where hidden = 1")}
            places = [json.loads(r[1]) for r in con.execute("select id, data from places order by id") if r[0] not in hidden]
            meta = {k: json.loads(v) for k, v in con.execute("select key, value from meta")}
        finally:
            con.close()
    except sqlite3.Error as e:
        log.warning("장소 DB 읽기 오류: %s", type(e).__name__)
        return _cache.get("value")
    for p in places:
        _fix_closed(p)
    value = {"places": places, "meta": meta}
    _cache["key"] = key
    _cache["value"] = value
    return value


def places() -> list[dict]:
    p = current_path()
    if p is None:
        return []
    v = _load(p)
    return list(v["places"]) if v else []


def meta() -> dict:
    p = current_path()
    if p is None:
        return {}
    v = _load(p)
    return dict(v["meta"]) if v else {}


def fetched_at() -> str | None:
    return meta().get("fetchedAt")


def clear_cache() -> None:
    _cache.clear()

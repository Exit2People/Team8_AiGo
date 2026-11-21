"""기상청 초단기실황. 비 · 눈이면 바깥 장소를 빼요. 실패는 '확인 불가'(맑음 아님)."""

import logging
import math
import time
from datetime import timedelta
from urllib.parse import unquote

import httpx

from app import config

log = logging.getLogger("aigo.weather")

CITY_HALL = (37.5665, 126.9780)
BAD = ("비", "눈")
URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

_cache: dict[tuple[int, int], tuple[float, dict]] = {}


def to_grid(lat: float, lng: float) -> tuple[int, int]:
    """위경도 → 기상청 5km 격자 (Lambert 정각원추)."""
    re_, grid = 6371.00877, 5.0
    slat1, slat2, olon, olat = 30.0, 60.0, 126.0, 38.0
    xo, yo = 43, 136
    d = math.pi / 180.0
    re_ /= grid
    slat1, slat2, olon, olat = slat1 * d, slat2 * d, olon * d, olat * d
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re_ * sf / math.pow(ro, sn)
    ra = math.tan(math.pi * 0.25 + lat * d * 0.5)
    ra = re_ * sf / math.pow(ra, sn)
    theta = lng * d - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    x = int(ra * math.sin(theta) + xo + 0.5)
    y = int(ro - ra * math.cos(theta) + yo + 0.5)
    return x, y


def _unavailable() -> dict:
    return {"weather": "확인 불가", "temperature": None, "source": "unavailable"}


def pty_to_weather(pty: str | int | None) -> str | None:
    try:
        v = int(float(pty))
    except (TypeError, ValueError):
        return None
    if v == 0:
        return "강수 없음"
    if v in (1, 2, 5, 6):
        return "비"
    if v in (3, 7):
        return "눈"
    return None


def _fetch(nx: int, ny: int) -> dict:
    key = config.env("DATA_GO_KR_SERVICE_KEY")
    if not key:
        return _unavailable()
    base = config.now() - timedelta(minutes=40)
    params = {
        "serviceKey": unquote(key), "dataType": "JSON", "numOfRows": 20, "pageNo": 1,
        "base_date": base.strftime("%Y%m%d"), "base_time": base.strftime("%H00"), "nx": nx, "ny": ny,
    }
    try:
        r = httpx.get(URL, params=params, timeout=1.5)
        data = r.json()
        if data["response"]["header"]["resultCode"] != "00":
            return _unavailable()
        items = data["response"]["body"]["items"]["item"]
    except Exception as e:  # 실패는 확인 불가
        log.warning("날씨 오류: %s", type(e).__name__)
        return _unavailable()
    vals = {i.get("category"): i.get("obsrValue") for i in items}
    w = pty_to_weather(vals.get("PTY"))
    if w is None:
        return _unavailable()
    try:
        temp = float(vals.get("T1H")) if vals.get("T1H") is not None else None
    except (TypeError, ValueError):
        temp = None
    return {
        "weather": w, "temperature": temp, "source": "kma",
        "observedAt": base.strftime("%Y-%m-%dT%H:00:00+09:00"),
    }


def current(lat: float | None = None, lng: float | None = None) -> dict:
    override = config.env("AIGO_WEATHER")
    if override:
        return {"weather": override, "temperature": None, "source": "override"}
    if lat is None or lng is None:
        lat, lng = CITY_HALL
    grid = to_grid(lat, lng)
    hit = _cache.get(grid)
    if hit and hit[0] > time.monotonic():
        return dict(hit[1])
    value = _fetch(*grid)
    if len(_cache) > 512:
        _cache.clear()
    ttl = 300 if value["source"] == "kma" else 30
    _cache[grid] = (time.monotonic() + ttl, value)
    return dict(value)


def today() -> str:
    """API를 부르지 않는 날씨 (덮어쓰기 또는 서울시청 기억값)."""
    override = config.env("AIGO_WEATHER")
    if override:
        return override
    hit = _cache.get(to_grid(*CITY_HALL))
    return hit[1]["weather"] if hit else "확인 불가"


def is_bad(w: str | None) -> bool:
    return w in BAD


def clear_cache() -> None:
    _cache.clear()

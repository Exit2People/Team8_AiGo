"""규칙으로 거르기 + 운영 시간 판단 (04_CONSTANTS 5절)."""

import re
from datetime import datetime, timedelta

from app import config
from app.data import geo, loader, route, transit
from app.schemas import Conditions

WALK_CAP = {"제한 없음": 3, "많이": 3, "보통": 2, "조금만": 1, "가장 적게": 1}
EARLY_OK = 30
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[~∼\-–—]\s*(\d{1,2}):(\d{2})")


def wants_free_only(cond: Conditions) -> bool:
    return any(x.a == "무료인 곳만요" for x in cond.ai)


def avoid_of(cond: Conditions) -> list[str]:
    return list(dict.fromkeys([*cond.range.avoid, *cond.extra.avoid]))


def start_station(cond: Conditions) -> tuple[str, int, str | None]:
    o = cond.origin
    if o.type != "동":
        return o.name, 0, None
    lat, lng = o.lat, o.lng
    if lat is None or lng is None:
        hit = loader.dong_by_id(o.id)
        if hit:
            lat, lng = hit[1]["lat"], hit[1]["lng"]
    if lat is None or lng is None:
        return o.name, 0, None
    near = geo.nearest_station(lat, lng)
    if not near:
        return o.name, 0, None
    s, d = near
    return s["name"], geo.walk_minutes(d), o.name


def _hm(h: str, m: str) -> int:
    return int(h) * 60 + int(m)


def _spans(text: str) -> tuple[int, int] | None:
    found = TIME_RE.findall(text or "")
    if not found:
        return None
    starts = [_hm(a, b) for a, b, _, _ in found]
    ends = []
    for a, b, c, d in found:
        s, e = _hm(a, b), _hm(c, d)
        if e <= s:
            e += 24 * 60
        ends.append(e)
    return min(starts), max(ends)


def _minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def open_info(place: dict, at: datetime) -> dict:
    """도착 시각 기준 {ok, today, why, lastEntry}."""
    if place.get("source") == "kakao":
        return {"ok": None, "today": "운영 시간 확인 필요", "why": None, "lastEntry": None}
    if at.weekday() in (place.get("closed") or []):
        return {"ok": False, "today": "오늘 쉬는 날", "why": "쉬는 날", "lastEntry": None}
    t = _minutes(at)
    kind = place.get("kind")
    if kind == "행사":
        hours = (place.get("event") or {}).get("hours") or ""
        sp = _spans(hours)
        today = hours or "행사 안내에서 확인"
        if sp is None:
            return {"ok": True, "today": today, "why": None, "lastEntry": None}
        s, e = sp
        if t < s - EARLY_OK:
            return {"ok": False, "today": today, "why": "아직 열지 않음", "lastEntry": None}
        if e - t < min(60, (e - s) / 2):
            return {"ok": False, "today": today, "why": "곧 닫음", "lastEntry": None}
        return {"ok": True, "today": today, "why": None, "lastEntry": None}
    if kind == "시장":
        today = "보통 09:00~19:00 (가게마다 달라요)"
        if t < 9 * 60 - EARLY_OK:
            return {"ok": False, "today": today, "why": "아직 열지 않음", "lastEntry": None}
        if 19 * 60 - t < config.MIN_STAY:
            return {"ok": False, "today": today, "why": "곧 닫음", "lastEntry": None}
        return {"ok": True, "today": today, "why": None, "lastEntry": None}
    if place.get("always"):
        return {"ok": True, "today": "항상 열림", "why": None, "lastEntry": None}
    op, cl, last = place.get("open"), place.get("close"), place.get("lastEntry")
    today = place.get("hoursText") or (f"{op}~{cl}" if op and cl else "운영 시간 확인 필요")
    if not (op and cl):
        return {"ok": True, "today": today, "why": None, "lastEntry": last}
    o, c = _hm(*op.split(":")), _hm(*cl.split(":"))
    if last and t > _hm(*last.split(":")):
        return {"ok": False, "today": today, "why": "입장 마감", "lastEntry": last}
    if t < o - EARLY_OK:
        return {"ok": False, "today": today, "why": "아직 열지 않음", "lastEntry": last}
    if c - t < config.MIN_STAY:
        return {"ok": False, "today": today, "why": "곧 닫음", "lastEntry": last}
    return {"ok": True, "today": today, "why": None, "lastEntry": last}


# ── 어르신용이 아닌 행사 · 좌표가 어긋난 곳 (10_BACKEND_SPEC to_place 1 · 2, 09_ACCEPTANCE 3.3) ──
# 스냅숏을 만들 때 거른 규칙이지만, 매일 받기(sync)를 빼서 추천할 때 한 번 더 걸러요.
RECRUIT_WORDS = ("모집", "신청자", "교육생", "공모")
KID_WORDS = ("어린이", "유아", "영아", "아동", "초등", "청소년", "중·고등", "학년")
ADULT_WORDS = ("누구나", "성인", "전체", "제한", "전 연령", "시민", "어르신", "시니어", "이상")
OPEN_TO_ALL = ("누구나", "전 연령", "전체", "어르신", "시니어")
KID_PLACES = ("어린이박물관", "어린이열람실", "키즈")
GUARDIAN_RE = re.compile(r"보호자\s*(를\s*)?동반")
AGE_RANGE_RE = re.compile(r"(\d{1,2})\s*[~∼\-–]\s*(\d{1,2})\s*세")
WRONG_PLACE_M = 2500


def for_seniors(p: dict) -> bool:
    """행사가 어르신도 갈 수 있는 것인지. 행사가 아니면 늘 참이에요."""
    ev = p.get("event")
    if p.get("kind") != "행사" or not ev:
        return True
    name = p.get("name") or ""
    if any(w in name for w in RECRUIT_WORDS):
        return False
    target = ev.get("target") or ""
    if any(w in target for w in ("전 연령", "어르신", "시니어")):
        return True
    # 이름이 어린이 시설이면 대상이 "이용자 누구나"여도 아이 전용으로 봐요
    if any(w in name for w in KID_PLACES):
        return False
    if any(w in target for w in OPEN_TO_ALL):
        return True
    # "성인 보호자를 동반한 3~9세 어린이": 어른 말이 보호자로만 나오면 아이 전용이에요
    if GUARDIAN_RE.search(target):
        return False
    ages = AGE_RANGE_RE.search(target)
    if ages and int(ages.group(2)) <= 13:
        return False
    if any(w in target for w in KID_WORDS) and not any(w in target for w in ADULT_WORDS):
        return False
    return True


def wrong_place(p: dict) -> bool:
    """주소의 구와 좌표가 어긋남: 그 구의 어느 동 중심에서도 2,500m 넘게 떨어짐. 구를 모르면 판단하지 않아요."""
    gu, lat, lng = p.get("gu"), p.get("lat"), p.get("lng")
    if not gu or lat is None or lng is None:
        return False
    for d in loader.districts():
        if d["gu"] == gu:
            return all(geo.distance_m(lat, lng, x["lat"], x["lng"]) > WRONG_PLACE_M for x in d["dongs"])
    return False


def filter_places(cond: Conditions, now: datetime, weather: str | None, visited: list[str] | None = None,
                  places: list[dict] | None = None, counts: dict | None = None) -> list[dict]:
    visited_set = set(visited or [])
    exclude = set(cond.exclude)
    today = now.strftime("%Y-%m-%d")
    bad = weather in ("비", "눈")
    inout = cond.basic.inout
    free_only = wants_free_only(cond)
    walk = cond.range.walk
    cap = WALK_CAP.get(walk, 1)
    avoid = set(avoid_of(cond))
    limit = cond.range.oneWayMin
    from_name, start_walk, start_from = start_station(cond)
    can_measure = transit.enabled()
    counts = counts if counts is not None else {}
    out = []

    def drop(why: str):
        counts[why] = counts.get(why, 0) + 1

    for p in (places if places is not None else loader.places()):
        if not for_seniors(p):
            drop("어르신용 아님"); continue
        if wrong_place(p):
            drop("위치가 어긋남"); continue
        ev = p.get("event")
        if p.get("kind") == "행사" and ev:
            if not (ev.get("start") or "") <= today <= (ev.get("end") or "9999"):
                drop("행사 날짜 아님"); continue
        if p.get("id") in visited_set:
            drop("30일 안에 다녀옴"); continue
        if p.get("id") in exclude:
            drop("이번에 이미 봄"); continue
        pin = p.get("inout")
        if bad and pin == "바깥":
            drop("날씨"); continue
        if inout == "실내가 좋아요" and pin == "바깥":
            drop("실내를 원함"); continue
        if inout == "바깥이 좋아요" and pin == "실내":
            drop("바깥을 원함"); continue
        fee = ((p.get("info") or {}).get("fee") or {}).get("free")
        if free_only and fee is False:
            drop("유료"); continue
        wl = int(p.get("walkLevel") or 3)
        if wl > cap or (walk == "가장 적게" and int(p.get("walkMin") or 99) > 5):
            drop("걷는 양"); continue
        if avoid & set(p.get("terrain") or []):
            drop("피할 것"); continue
        r = route.find_route(from_name, p, now, start_walk, start_from, walk, list(avoid))
        if r is None:
            drop("길 없음"); continue
        over = False
        travel = r["totalMin"] - r.get("startWalkMin", 0)
        if travel > limit:
            if r.get("estimated") and can_measure and travel <= limit + config.EST_SLACK_MIN:
                over = True
            else:
                drop("이동 시간"); continue
        oi = open_info(p, now + timedelta(minutes=r["totalMin"]))
        if oi["ok"] is False:
            drop(oi["why"] or "운영"); continue
        item = {"place": p, "route": r, "open": {"today": oi["today"], "lastEntry": oi.get("lastEntry")}}
        if over:
            item["overEstimate"] = True
        out.append(item)

    from app.data import preferences

    sel = preferences.selected(cond)
    if sel:
        crit, ans = sel
        keep = [x for x in out if ans in preferences.place_values(x["place"], crit)]
        if keep:
            counts["질문 5 선택"] = len(out) - len(keep)
            out = keep
    return out

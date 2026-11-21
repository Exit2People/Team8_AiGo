import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import config
from app.data import filter_places as fp
from app.data import loader, transit
from app.llm import client as llm
from app.llm import jev
from app.main import app
from app.recommend import expand as ex
from app.recommend.pick import diverse_pool, pick_by_rule, rank_by_rule, rule_reason
from app.recommend.verify import check, verify_picks
from app.schemas import Conditions

client = TestClient(app)
ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}}
    base.update(kw)
    return Conditions.model_validate(base)


def rec(c: Conditions, visited=None) -> dict:
    r = client.post("/recommend", json={"conditions": c.model_dump(), "visited": visited or []})
    assert r.status_code == 200
    return r.json()


def test_recommend_rule_without_key():
    j = rec(cond(basic={"want": "바람 쐬기"}))
    assert j["notFound"] is False and j["by"] == "rule"
    assert 1 <= len(j["candidates"]) <= 3
    ids = {p["id"] for p in loader.places()}
    for c in j["candidates"]:
        assert c["place"]["id"] in ids and c["reason"]
        assert c["route"]["estimated"] is True and c["route"]["legs"][-1]["kind"] == "하차"
        assert "info" in c and set(c["info"]) >= {"photo", "fee", "phone", "homepage", "walk"}
    assert j["dataAsOf"].startswith("2026-11-18") and j["weather"]["source"] == "override"


def test_recommend_rain_indoor(monkeypatch):
    monkeypatch.setenv("AIGO_WEATHER", "비")
    j = rec(cond(basic={"want": "바람 쐬기"}))
    assert j["candidates"]
    assert all(c["place"]["kind"] != "공원" for c in j["candidates"])
    items = fp.filter_places(cond(), config.now(), "비", [])
    assert items and all(it["place"]["inout"] != "바깥" for it in items)


def test_recommend_no_db_no_invented(monkeypatch, tmp_path):
    monkeypatch.setenv("AIGO_SNAPSHOT_PATH", str(tmp_path / "none.db"))
    loader.clear_cache()
    j = rec(cond())
    assert j == {"candidates": [], "notFound": True, "why": "none"}


def test_filter_free_only_and_events():
    c = cond(ai=[{"q": "돈 내는 곳도 괜찮으세요?", "choices": [], "a": "무료인 곳만요"}])
    items = fp.filter_places(c, config.now(), "맑음", [])
    assert all(((it["place"].get("info") or {}).get("fee") or {}).get("free") is not False for it in items)
    today = "2026-11-21"
    for it in fp.filter_places(cond(), config.now(), "맑음", []):
        ev = it["place"].get("event")
        if ev:
            assert ev["start"] <= today <= ev["end"]


def test_filter_visited_and_exclude():
    items = fp.filter_places(cond(), config.now(), "맑음", [])
    first = items[0]["place"]["id"]
    # 다녀온 곳은 빼지 않고 표시만 해요 (다시 가고 싶을 수 있어서)
    again = {x["place"]["id"]: x for x in fp.filter_places(cond(), config.now(), "맑음", [first])}
    assert again[first].get("visited") is True
    assert first not in {x["place"]["id"] for x in fp.filter_places(cond(exclude=[first]), config.now(), "맑음", [])}


def test_open_info_rules():
    museum = {"kind": "박물관", "closed": [0], "open": "10:00", "close": "18:00", "lastEntry": "17:00",
              "hoursText": "10:00~18:00"}
    monday = datetime(2026, 11, 23, 11, 0, tzinfo=config.KST)
    assert fp.open_info(museum, monday)["why"] == "쉬는 날"
    sat = datetime(2026, 11, 21, 17, 30, tzinfo=config.KST)
    assert fp.open_info(museum, sat)["why"] == "입장 마감"
    early = datetime(2026, 11, 21, 9, 0, tzinfo=config.KST)
    assert fp.open_info(museum, early)["why"] == "아직 열지 않음"
    market = {"kind": "시장"}
    assert fp.open_info(market, sat)["today"].startswith("보통 09:00~19:00")
    assert fp.open_info({"kind": "시장"}, datetime(2026, 11, 21, 18, 30, tzinfo=config.KST))["why"] == "곧 닫음"
    night = {"kind": "행사", "event": {"hours": "20:00~25:30"}}
    assert fp.open_info(night, datetime(2026, 11, 21, 21, 0, tzinfo=config.KST))["ok"] is True
    assert fp.open_info({"source": "kakao"}, sat)["ok"] is None


def test_dong_origin_walk_not_counted():
    gu = loader.districts()[0]
    dong = gu["dongs"][0]
    c = cond(origin={"id": dong["id"], "name": dong["name"], "type": "동"}, range={"oneWayMin": 30, "walk": "보통"})
    st, walk, frm = fp.start_station(c)
    assert frm == dong["name"] and walk >= 1
    items = fp.filter_places(c, config.now(), "맑음", [])
    assert items
    for it in items:
        r = it["route"]
        assert r["startWalkMin"] == walk and r["totalMin"] - walk <= 30
        assert r["legs"][0]["tip"].startswith(f"{dong['name']}에서 {st}까지 걸어서 약")


def test_named_place_first_and_grandchild():
    c = cond(extra={"place": "서울숲"})
    items = fp.filter_places(c, config.now(), "맑음", [])
    ranked = rank_by_rule(items, c)
    top = ranked[0]
    assert any("서울숲" in x["place"]["name"] for x in ranked[:3])
    assert rule_reason(top, c).startswith("말씀하신 서울숲 쪽이에요.")


def test_market_food_first():
    c = cond(basic={"want": "맛있는 것"})
    items = [x for x in fp.filter_places(c, config.now(), "맑음", []) if x["place"]["kind"] == "시장"]
    ranked = rank_by_rule(items, c)
    foods = [int(x["place"]["market"]["food"]) for x in ranked[:3]]
    assert max(foods) >= 10


def test_diverse_pool_mixes_kinds():
    c = cond(basic={"want": "구경하기"})
    items = fp.filter_places(c, config.now(), "맑음", [])
    pool = diverse_pool(items, c, 20)
    assert len(pool) <= 20
    assert len({x["place"]["kind"] for x in pool}) >= 3
    picks = pick_by_rule(items, c)
    assert len(picks) == 3 and len({p["item"]["place"]["kind"] for p in picks}) >= 2


def _item(transfers=0, total=18, walk=5, inout="바깥"):
    return {"place": {"id": "X", "inout": inout, "walkMin": walk, "terrain": []},
            "route": {"totalMin": total, "transfers": transfers,
                      "legs": [{"kind": "탑승"}, {"kind": "하차", "walkMin": walk}]}}


def test_verify_check_rules():
    assert check("갈아타지 않고 18분이면 가요", _item())
    assert not check("갈아타지 않고 18분이면 가요", _item(transfers=1))
    assert not check("한 번만 갈아타면 돼요", _item(transfers=0))
    assert not check("2번 갈아타요", _item(transfers=1))
    assert not check("20분이면 가요", _item())
    assert check("역에서 5분 걸어요", _item())
    assert not check("실내라 편해요", _item(inout="바깥"))
    assert not check("야외에서 쉬어요", _item(inout="실내"))
    assert not check("엘리베이터가 있어요", _item())
    assert not check("", _item()) and not check("가" * 61, _item())
    it = _item()
    over = {**it, "overEstimate": True}
    assert verify_picks([{"id": "X", "reason": "좋아요"}], [over]) == []
    assert len(verify_picks([{"id": "X", "reason": "좋아요"}, {"id": "X", "reason": "좋아요"}], [it])) == 1


def test_recommend_ai_picks_verified(monkeypatch):
    c = cond(basic={"want": "구경하기"})
    items = fp.filter_places(c, config.now(), "맑음", [])
    pool = diverse_pool(items, c, 20)
    good, bad = pool[0], pool[1]

    async def fake(system, payload, schema, timeout, max_tokens=2000):
        assert "lat" not in str(payload) and "37.5" not in str(payload)
        return {"picks": [{"id": good["place"]["id"], "reason": "구경하기 좋은 곳이에요"},
                          {"id": bad["place"]["id"], "reason": "999분이면 가요"},
                          {"id": "NOPE", "reason": "없는 곳"}]}

    monkeypatch.setattr(llm, "ask_json", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    j = rec(c)
    assert j["by"] == "ai"
    ids = [x["place"]["id"] for x in j["candidates"]]
    assert ids == [good["place"]["id"]]


def test_recommend_ai_all_wrong_falls_back(monkeypatch):
    async def fake(system, payload, schema, timeout, max_tokens=2000):
        return {"picks": [{"id": "NOPE", "reason": "x"}]}

    monkeypatch.setattr(llm, "ask_json", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    j = rec(cond(basic={"want": "구경하기"}))
    assert j["by"] == "rule" and len(j["candidates"]) == 3


def test_expand_only_when_missing(monkeypatch):
    c = cond(extra={"wish": ["공룡 구경"]})
    items = fp.filter_places(c, config.now(), "맑음", [])
    assert ex.needs_expand(c, items)
    assert not ex.needs_expand(cond(), items)
    assert not ex.needs_expand(cond(extra={"place": "서울숲"}), items)
    assert ex.tidy_words(["자연사", "화석", "박물관", "공룡 구경", "아주아주긴낱말이요"], ["공룡 구경"]) == ["자연사", "화석"]

    async def fake(system, payload, schema, timeout, max_tokens=2000):
        if "picks" in schema["properties"]:
            return None
        return {"words": ["자연사", "화석"], "places": []}

    monkeypatch.setattr(llm, "ask_json", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    j = rec(c)
    assert j["expanded"]["from"] == ["공룡 구경"] and j["expanded"]["words"] == ["자연사", "화석"]


def test_transit_choose_subway_first():
    a = {"totalMin": 30, "transfers": 0, "buses": 1}
    b = {"totalMin": 40, "transfers": 1, "buses": 0}
    c2 = {"totalMin": 35, "transfers": 1, "buses": 0}
    assert transit.choose([a, b, c2], 60, False) is c2
    assert transit.choose([a, {"totalMin": 90, "transfers": 0, "buses": 0}], 60, False) is a


def test_transit_bus_names():
    assert transit.bus_name("705") == "705번 버스"
    assert transit.bus_name("노원08") == "노원08번 버스"
    assert transit.bus_name("9600광주") == "9600번 버스(광주)"


def test_tmap_to_route():
    data = {"metaData": {"plan": {"itineraries": [{"transferCount": 1, "legs": [
        {"mode": "WALK", "distance": 335}, {"mode": "BUS", "route": "간선:173", "sectionTime": 600,
                                            "start": {"name": "A"}, "end": {"name": "B"}},
        {"mode": "SUBWAY", "route": "수도권1호선", "sectionTime": 300, "start": {"name": "B"}, "end": {"name": "C"},
         "passStopList": {"stationList": [1, 2, 3]}},
        {"mode": "WALK", "distance": 134}]}]}}}
    r = transit.tmap_to_route(data, config.now())
    assert [lg["line"] for lg in r["legs"][:2]] == ["173번 버스", "1호선"]
    assert r["transfers"] == 1 and r["buses"] == 1 and r["source"] == "tmap" and r["legs"][-1]["walkMin"] == 2
    assert r["totalMin"] == round(15 + 469 / 67)


def test_refine_uses_measured(monkeypatch):
    monkeypatch.setenv("TMAP_APP_KEY", "x")
    c = cond(basic={"want": "구경하기"})
    items = fp.filter_places(c, config.now(), "맑음", [])

    async def fake_find(start, place, now, limit, from_dong):
        return {"totalMin": 99, "transfers": 0, "legs": [{"kind": "탑승", "station": "서울역"}, {"kind": "하차"}],
                "source": "tmap", "firstWalkMin": 0, "buses": 0}

    monkeypatch.setattr(transit, "find", fake_find)
    pool, stats = asyncio.run(transit.refine(items, c, config.now(), 2.0))
    assert stats["asked"] == 6 and stats["measured"] == 0  # 99분 → 범위 밖이라 빠짐
    assert all(x["route"].get("source") != "tmap" for x in pool)


def test_jev_cooldown(monkeypatch):
    import httpx

    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    jev.reset()
    calls = []

    async def fake_post(body, timeout):
        calls.append(1)
        return httpx.Response(429)

    monkeypatch.setattr(jev, "_post", fake_post)
    assert asyncio.run(jev.ask_yes({}, "q", 1.0)) is None
    assert asyncio.run(jev.ask_yes({}, "q", 1.0)) is None
    assert len(calls) == 1
    jev.reset()


def test_jev_no_key_no_call():
    assert asyncio.run(jev.ask_yes({}, "q", 1.0)) is None


def test_place_open_endpoint():
    pid = loader.places()[0]["id"]
    j = client.get(f"/places/{pid}/open").json()
    assert set(j) == {"open", "today", "lastEntry"}
    assert client.get("/places/NOPE/open").status_code == 404


def test_relax_when_empty():
    c = cond(range={"oneWayMin": 1, "walk": "보통"})
    j = rec(c)
    assert j.get("relaxed") is True or j["notFound"] is True

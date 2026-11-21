"""구체적인 바람(공룡 · 자전거): 넓은 말로 엉뚱한 곳을 맞추지 않고, 맞는 곳이 오늘 쉬면 여는 요일을 알려요."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import config
from app.data import loader
from app.llm import client as llm
from app.main import app
from app.recommend import expand as ex
from app.recommend import service as svc
from app.recommend.wish import direct_specific, matched_wish, specific_terms
from app.schemas import Conditions

client = TestClient(app)
ORIGIN = {"id": "1120059000", "name": "금호1가동", "type": "동", "lat": 37.553669, "lng": 127.025056}


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    # 2026-11-21은 토요일이에요. 대학 자연사박물관 두 곳은 토 · 일에 쉬어요
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")


def cond(**extra) -> Conditions:
    return Conditions.model_validate({
        "origin": ORIGIN, "body": "보통이에요", "time": "한나절",
        "range": {"oneWayMin": 45, "walk": "보통", "avoid": []},
        "basic": {"want": "구경하기", "walk": None, "inout": None},
        "extra": {"who": "손주", "wish": ["공룡 구경"], **extra},
    })


def place(name: str, **kw) -> dict:
    return {"id": name, "name": name, "kind": kw.pop("kind", "박물관"), "mood": kw.pop("mood", ["전시"]), **kw}


def item(p: dict, reason: str = "") -> dict:
    return {"item": {"place": p, "route": {"totalMin": 30, "transfers": 0, "legs": []}}, "reason": reason}


def test_specific_terms_only_for_specific_wishes():
    assert "자연사" in specific_terms(["공룡 구경"])
    assert specific_terms(["바람 쐬기"]) == []


def test_broad_expansion_does_not_match_dinosaur():
    sewer = place("서울하수도과학관")
    assert matched_wish(sewer, ["공룡 구경"], ["과학관"]) is None
    assert matched_wish(place("경희대학교 자연사박물관"), ["공룡 구경"]) == "공룡 구경"
    # 구체적이지 않은 바람은 예전처럼 넓힌 말로 맞춰요
    assert matched_wish(place("북촌 고택 전시"), ["한옥 구경"], ["고택"]) == "한옥 구경"


def test_bicycle_parks_count_as_direct():
    assert direct_specific(place("뚝섬한강공원", kind="공원", mood=["물가"]), ["자전거 타기"])


def test_expand_keeps_only_direct_words_for_specific_wish(monkeypatch):
    async def fake(system, payload, schema, timeout):
        return {"words": ["과학관", "자연사"], "places": ["서울하수도과학관", "서대문자연사박물관"]}

    monkeypatch.setattr(llm, "ask_json", fake)
    words, places = asyncio.run(ex.expand(cond(), 3.0))
    assert "과학관" not in words and "자연사" in words
    assert places == ["서대문자연사박물관"]


def test_open_days_and_particle():
    assert svc._open_days([5, 6]) == "월~금"
    assert svc._open_days([0]) == "화~일"
    assert svc._open_days([0, 2]) == "화 · 목~일"
    assert svc._eun("자연사박물관") == "은"
    assert svc._eun("놀이터 나무") == "는"


def test_wish_later_names_closed_museum_and_open_days():
    shown = [item(place("성북어린이미술관 꿈자람", kind="미술관"))]
    later = svc._wish_later(cond(), shown, config.now())
    assert later is not None
    assert "자연사박물관" in later["place"]["name"]
    assert later["openDays"] == "월~금"
    assert "오늘 쉬어요. 월~금요일에 가 보세요" in later["note"]


def test_no_wish_later_when_a_direct_place_is_shown():
    shown = [item(place("경희대학교 자연사박물관"))]
    assert svc._wish_later(cond(), shown, config.now()) is None


def test_reason_drops_dinosaur_for_unrelated_place():
    shown = [item(place("서울하수도과학관"), "공룡을 만날 수 있어요")]
    fixed = svc._fix_wish_reasons(shown, cond())
    assert "공룡" not in fixed[0]["reason"]


def test_recommend_dinosaur_on_saturday_without_key():
    # 키 없이 규칙 길로도 하수도과학관을 공룡 곳으로 내지 않고, 여는 요일을 알려요
    assert any("자연사" in (p.get("name") or "") for p in loader.places())
    r = client.post("/recommend", json={"conditions": cond().model_dump(), "visited": []})
    assert r.status_code == 200
    j = r.json()
    for c in j["candidates"]:
        assert "공룡" not in c["reason"]
    if not any(direct_specific(c["place"], ["공룡 구경"]) for c in j["candidates"]):
        assert j["wishLater"]["openDays"] == "월~금"

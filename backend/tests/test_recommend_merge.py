"""질문 · 추천 에이전트를 합친 뒤 리뷰에서 나온 추천 길 문제를 지켜요."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.data import transit
from app.main import app
from app.recommend import expand as ex
from app.recommend import service as svc
from app.schemas import Conditions

client = TestClient(app)
ORIGIN = {"id": "1120059000", "name": "금호1가동", "type": "동", "lat": 37.553669, "lng": 127.025056}


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")


def cond(one_way: int = 45, **extra) -> dict:
    return Conditions.model_validate({
        "origin": ORIGIN, "body": "보통이에요", "time": "한나절",
        "range": {"oneWayMin": one_way, "walk": "보통", "avoid": []},
        "basic": {"want": "구경하기", "walk": None, "inout": None},
        "extra": extra,
    }).model_dump()


def test_code_path_refines_and_expands_together(monkeypatch):
    # 운영(AIGO_AGENT=0)은 코드 길 한도가 8초라, 길 재기와 말 넓히기를 차례로 하면 AI 고르기 시간이 모자라요
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_AGENT", "0")
    seen: dict[str, float] = {}
    real_refine = transit.refine

    async def slow_refine(items, c, now, timeout):
        seen["refine_start"] = time.monotonic()
        await asyncio.sleep(0.6)
        seen["refine_end"] = time.monotonic()
        return await real_refine(items, c, now, 0)

    async def slow_expand(c, timeout):
        seen["expand_start"] = time.monotonic()
        await asyncio.sleep(0.6)
        return ["자연사"], []

    async def no_ai(pool, c, timeout):
        return None

    monkeypatch.setattr(transit, "refine", slow_refine)
    monkeypatch.setattr(ex, "expand", slow_expand)
    monkeypatch.setattr(svc, "pick_by_ai", no_ai)
    r = client.post("/recommend", json={"conditions": cond(wish=["공룡 구경"]), "visited": []})
    assert r.status_code == 200
    assert "expand_start" in seen and "refine_end" in seen
    assert seen["expand_start"] < seen["refine_end"]  # 넓히기가 길 재기를 기다리지 않았어요


def test_agent_found_places_survive_code_path(monkeypatch):
    # 에이전트가 넓혀 찾은 곳(seen)을 고르지 못하고 코드 길로 가도, 그 곳들을 후보에서 버리지 않아요
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_AGENT", "1")
    kakao = {"place": {"id": "kakao:t1", "name": "찾은 자연사 전시", "kind": "박물관", "mood": ["전시"],
                       "source": "kakao", "lat": 37.56, "lng": 127.03},
             "route": {"totalMin": 25, "transfers": 0, "legs": [], "source": "tmap"}}
    got: dict = {}

    async def fake_agent(pool, c, visited, now, weather, timeout, everything, info=None):
        return [{"id": "없는-곳", "reason": "좋아요"}], [kakao]

    async def spy_ai(pool, c, timeout):
        got["ids"] = [x["place"]["id"] for x in pool]
        return None

    from app.recommend.agent import graph

    monkeypatch.setattr(graph, "pick_by_agent", fake_agent)
    monkeypatch.setattr(svc, "pick_by_ai", spy_ai)
    # 편도 5분이면 처음엔 0곳이라 코드 길에서 범위를 넓혀요
    r = client.post("/recommend", json={"conditions": cond(one_way=5), "visited": []})
    assert r.status_code == 200
    assert "kakao:t1" in got.get("ids", [])

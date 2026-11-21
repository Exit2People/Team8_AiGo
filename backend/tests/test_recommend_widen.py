"""exp/agent-full: 추천 에이전트의 "조건 넓혀 다시 찾기 + 고르기" (가짜 LLM)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import config
from app.data import filter_places as fp
from app.llm import agent_loop
from app.llm import client as llm
from app.main import app
from app.recommend import expand as ex
from app.recommend.agent import tools
from app.recommend.agent.graph import pick_by_agent, widen_hint
from app.recommend.agent.tools import AgentContext
from app.recommend.pick import diverse_pool
from app.recommend.wish import place_text
from app.schemas import Conditions
from tests.test_question_agent import FakeChat, call

client = TestClient(app)
ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("AIGO_AGENT")  # 브랜치 기본(켜짐) 그대로

    async def no_ai(*a, **k):
        return None

    monkeypatch.setattr(llm, "ask_json", no_ai)


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}, "basic": {"want": "구경하기"}}
    base.update(kw)
    return Conditions.model_validate(base)


def tight(**kw) -> Conditions:
    return cond(range={"oneWayMin": 1, "walk": "보통"}, **kw)


def ctx_for(c, items=None):
    every = fp.filter_places(c, config.now(), "맑음", [])
    every = [x for x in every if not x.get("overEstimate")]
    pool = diverse_pool(every, c, 20) if items is None else items
    return AgentContext(cond=c, now=config.now(), weather="맑음", visited=[], items=pool, everything=every)


def use(monkeypatch, script):
    fake = FakeChat(script)
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: fake)
    return fake


def rec(c):
    r = client.post("/recommend", json={"conditions": c.model_dump(), "visited": []})
    assert r.status_code == 200
    return r.json()


def test_agent_on_by_default():
    assert config.agent_on() is True


def test_relax_tool_only_when_needed():
    ctx = ctx_for(cond())
    assert not ctx.can_widen()
    assert tools.relax_travel(ctx) == {"error": tools.E_RELAX}
    t = ctx_for(tight())
    assert t.can_widen() and not t.everything
    found = tools.relax_travel(t)
    assert isinstance(found, list) and found and t.relaxed_used
    assert all(d["이동 범위"] == "고른 범위보다 멀어요" for d in found)
    assert tools.relax_travel(t) == {"error": tools.E_RELAX_TWICE}


def test_count_places_does_not_use_searches():
    c = cond(extra={"wish": ["공룡 구경"]})
    ctx = ctx_for(c)
    n = tools.count_places(ctx, word="한강")
    assert n["오늘 갈 수 있는 곳"] == len(ctx.everything) and "바람과 맞는 곳" in n and ctx.searches == 0
    if n["바람과 맞는 곳"] == 0:
        assert "이동 범위를 넓히면 갈 수 있는 곳" in n


def test_expand_tool_finds_by_wider_words(monkeypatch):
    c = cond(extra={"wish": ["공룡 구경"]})
    ctx = ctx_for(c)
    if not ctx.can_widen():
        pytest.skip("오늘 자료에 공룡과 맞는 곳이 있어요")
    word = next(w for w in ["한옥", "숲", "궁", "시장"] if any(w in place_text(x["place"]) for x in ctx.everything))

    async def fake_expand(cond, timeout):
        return [word], []

    monkeypatch.setattr(ex, "expand", fake_expand)
    out = asyncio.run(tools.expand_wish(ctx))
    assert out["넓힌 말"] == [word] and out["찾은 곳"]
    assert ctx.expanded["words"] == [word] and ctx.expanded["from"] == ["공룡 구경"]
    assert asyncio.run(tools.expand_wish(ctx)) == {"error": tools.E_EXPAND_TWICE}
    # 바람과 맞는 곳이 있으면 넓히지 않아요
    plain = ctx_for(cond(extra={"place": "한강"}))
    assert asyncio.run(tools.expand_wish(plain)) == {"error": tools.E_EXPAND}


def test_widen_hint():
    assert "0곳" in widen_hint(ctx_for(tight()))
    assert widen_hint(ctx_for(cond())) is None


def test_agent_relaxes_then_picks_end_to_end(monkeypatch):
    """규칙만으로 0곳 → 에이전트가 relax_travel → 넓힌 곳에서 골라요 → relaxed: true, by: agent."""
    c = tight()
    wide = AgentContext(cond=c, now=config.now(), weather="맑음", visited=[], items=[], everything=[])
    pid = tools.relax_travel(wide)[0]["id"]  # 에이전트가 받는 첫 곳
    fake = use(monkeypatch, [call("relax_travel", {}, "a"),
                             call("submit_picks", {"picks": [{"id": pid, "reason": "가 보기 좋아요"}]}, "b")])
    j = rec(c)
    assert j["by"] == "agent" and j["relaxed"] is True and j["candidates"][0]["place"]["id"] == pid
    assert len(j["candidates"]) == 3
    assert "넓혀 찾기" in fake.seen[0][1].content


def test_agent_expands_then_picks_end_to_end(monkeypatch):
    c = cond(extra={"wish": ["공룡 구경"]})
    ctx = ctx_for(c)
    if not ctx.can_widen():
        pytest.skip("오늘 자료에 공룡과 맞는 곳이 있어요")
    word = next(w for w in ["한옥", "숲", "궁", "시장"] if any(w in place_text(x["place"]) for x in ctx.everything))
    pid = next(x["place"]["id"] for x in ctx.everything if word in place_text(x["place"]))

    async def fake_expand(cond, timeout):
        return [word], []

    monkeypatch.setattr(ex, "expand", fake_expand)
    use(monkeypatch, [call("expand_wish", {}, "a"),
                      call("submit_picks", {"picks": [{"id": pid, "reason": "공룡 좋아하시면 가 보세요"}]}, "b")])
    j = rec(c)
    assert j["by"] == "agent" and j["candidates"][0]["place"]["id"] == pid
    assert j["expanded"]["words"] == [word] and j["expanded"]["from"] == ["공룡 구경"]
    assert "relaxed" not in j


def test_agent_fails_code_still_widens(monkeypatch):
    """에이전트가 실패하면 코드가 예전처럼 넓혀요 (이동 범위 +20분 → 규칙)."""
    use(monkeypatch, [RuntimeError("boom")])
    j = rec(tight())
    assert j["by"] == "rule" and j["relaxed"] is True and len(j["candidates"]) == 3


def test_agent_wrong_pick_after_relax_falls_back(monkeypatch):
    c = tight()
    use(monkeypatch, [call("relax_travel", {}, "a"), call("submit_picks", {"picks": [{"id": "NOPE", "reason": "x"}]}, "b")])
    j = rec(c)
    assert j["by"] == "rule" and j["relaxed"] is True and len(j["candidates"]) == 3


def test_agent_time_budget_keeps_screen_limit(monkeypatch):
    """에이전트가 늦어도 화면 대기(20초) − 1초 안에 규칙으로 답해요."""
    import time

    class Slow(FakeChat):
        async def ainvoke(self, messages):
            await asyncio.sleep(30)

    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: Slow([]))
    monkeypatch.setattr(config, "AGENT_TIMEOUT", 0.3)
    t0 = time.monotonic()
    j = rec(cond())
    assert j["by"] == "rule" and len(j["candidates"]) == 3
    assert time.monotonic() - t0 < config.REC_WAIT - 1.0


def test_refill_to_three_after_measured_drop(monkeypatch):
    """고른 곳이 실제 길 재기에서 빠지면 남은 시간에 몇 곳 더 재서 3곳을 채워요."""
    from app.data import transit

    c = cond()
    ctx = ctx_for(c)
    bad = ctx.items[0]["place"]["id"]

    async def refine(items, cond, now, budget):
        return ctx.items, {}

    async def measure_all(items, cond, now, budget):
        out = []
        for it in items:
            if it["place"]["id"] == bad:
                continue
            out.append({**it, "route": {**it["route"], "source": "tmap"}})
        return out

    monkeypatch.setattr(transit, "enabled", lambda: True)
    monkeypatch.setattr(transit, "refine", refine)
    monkeypatch.setattr(transit, "measure_all", measure_all)
    use(monkeypatch, [call("submit_picks", {"picks": [{"id": bad, "reason": "가 보기 좋아요"}]})])
    j = rec(c)
    assert len(j["candidates"]) == 3 and bad not in [x["place"]["id"] for x in j["candidates"]]

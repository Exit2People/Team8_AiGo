import asyncio

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from app import config
from app.data import filter_places as fp
from app.llm import agent_loop
from app.llm import client as llm
from app.main import app
from app.recommend.agent import memory, tools
from app.recommend.agent.graph import pick_by_agent
from app.recommend.agent.tools import AgentContext
from app.recommend.pick import diverse_pool
from app.schemas import Conditions
from tests.test_question_agent import FakeChat, call

client = TestClient(app)
ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_AGENT", "1")


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}, "basic": {"want": "구경하기"}}
    base.update(kw)
    return Conditions.model_validate(base)


def use(monkeypatch, script):
    fake = FakeChat(script)
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: fake)
    return fake


def ctx_for(c, visited=None, items=None):
    every = fp.filter_places(c, config.now(), "맑음", visited or [])
    pool = diverse_pool(every, c, 20) if items is None else items
    return AgentContext(cond=c, now=config.now(), weather="맑음", visited=visited or [], items=pool, everything=every)


def rec(c, visited=None):
    r = client.post("/recommend", json={"conditions": c.model_dump(), "visited": visited or []})
    assert r.status_code == 200
    return r.json()


def test_search_then_submit_passes_checks(monkeypatch):
    c = cond()
    pool = diverse_pool(fp.filter_places(c, config.now(), "맑음", []), c, 20)
    a, b = pool[0]["place"]["id"], pool[1]["place"]["id"]
    fake = use(monkeypatch, [call("search_places", {}),
                             call("submit_picks", {"picks": [{"id": a, "reason": "구경하기 좋아요"},
                                                             {"id": b, "reason": "999분이면 가요"}]}, "t2")])
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("한 번 호출 안 해요")))
    j = rec(c)
    assert j["by"] == "agent" and j["candidates"][0]["place"]["id"] == a and len(j["candidates"]) == 3
    assert b not in [x["place"]["id"] for x in j["candidates"][:1]]
    first = fake.seen[0][1].content
    assert "37.5" not in first and "lat" not in first and "다녀온 곳 요약" in first


def test_visited_hidden_and_history(monkeypatch):
    c = cond()
    every = fp.filter_places(c, config.now(), "맑음", [])
    v = every[0]["place"]["id"]
    ctx = ctx_for(c, visited=[v])
    assert v not in [d["id"] for d in tools.search_places(ctx)]
    h = tools.get_visit_history(ctx, 5)
    assert h and set(h[0]) == {"이름", "종류", "구"}
    assert memory.profile_text([]) == "다녀온 곳 기록이 없어요."
    assert memory.profile_text([v]).startswith("최근에 1곳을 다녀왔어요.")


def test_relax_only_when_empty():
    c = cond()
    assert tools.search_places(ctx_for(c), relax_travel=True) == {"error": tools.E_RELAX}
    tight = cond(range={"oneWayMin": 1, "walk": "보통"})
    ctx = ctx_for(tight, items=[])
    found = tools.search_places(ctx, relax_travel=True)
    assert isinstance(found, list) and found
    assert all(x.get("relaxed") for x in ctx.pool.values())
    assert all(d.get("이동 범위") == "고른 범위보다 멀어요" for d in found)


def test_search_limits_and_route():
    ctx = ctx_for(cond())
    assert tools.search_places(ctx, word="가" * 41) == {"error": tools.E_WORD}
    assert tools.search_places(ctx, word="숲") != {"error": tools.E_WORD}
    tools.search_places(ctx, kind="공원")
    tools.search_places(ctx, word="서울숲")
    assert tools.search_places(ctx, word="한강") == {"error": tools.E_MAX}
    some = next(iter(ctx.pool))
    assert "totalMin" in tools.get_route(ctx, some)
    assert tools.get_route(ctx, "NOPE") == {"error": tools.E_ROUTE}


def test_search_keeps_first_route():
    c = cond()
    ctx = ctx_for(c)
    first = ctx.items[0]
    tools.search_places(ctx)
    ctx.pool[first["place"]["id"]]["route"]["source"] = "tmap"  # 잰 길이라고 쳐요
    tools.search_places(ctx)
    assert ctx.pool[first["place"]["id"]]["route"]["source"] == "tmap"


def test_agent_wrong_or_missing_falls_back(monkeypatch):
    c = cond()
    use(monkeypatch, [RuntimeError("boom")])

    async def no_ai(*a, **k):
        return None

    monkeypatch.setattr(llm, "ask_json", no_ai)
    j = rec(c)
    assert j["by"] == "rule" and len(j["candidates"]) == 3
    use(monkeypatch, [call("submit_picks", {"picks": [{"id": "NOPE", "reason": "x"}]})])
    j = rec(c)
    assert j["by"] == "rule" and len(j["candidates"]) == 3


def test_text_end_means_no_picks(monkeypatch):
    c = cond()
    use(monkeypatch, [AIMessage(content="여기가 좋아요")])
    r = asyncio.run(pick_by_agent([], c, [], config.now(), "맑음", 5.0, []))
    assert r == ([], [])


def test_round_limit(monkeypatch):
    c = cond()
    script = [call("search_places", {}, f"t{i}") for i in range(8)]
    fake = use(monkeypatch, script)
    r = asyncio.run(pick_by_agent(ctx_for(c).items, c, [], config.now(), "맑음", 5.0, []))
    assert r is not None and r[0] == [] and len(fake.seen) == config.AGENT_MAX_ROUNDS + 1
    assert any(isinstance(m, ToolMessage) for m in fake.seen[-1])


def test_agent_timeout_budget(monkeypatch):
    class Slow(FakeChat):
        async def ainvoke(self, messages):
            await asyncio.sleep(1.0)
            return AIMessage(content="")

    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: Slow([]))
    assert asyncio.run(pick_by_agent([], cond(), [], config.now(), "맑음", 0.2, [])) is None


def test_health_agent_switch(monkeypatch):
    assert client.get("/health").json()["agent"] is True
    monkeypatch.setenv("AIGO_AGENT", "")
    assert client.get("/health").json()["agent"] is False


def test_agent_off_uses_single_call(monkeypatch):
    monkeypatch.setenv("AIGO_AGENT", "0")
    fake = use(monkeypatch, [])

    async def no_ai(*a, **k):
        return None

    monkeypatch.setattr(llm, "ask_json", no_ai)
    assert rec(cond())["by"] == "rule" and fake.seen == []

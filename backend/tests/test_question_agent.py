import asyncio

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.llm import agent_loop, jev
from app.question import agent as qa
from app.question import flow, service
from app.question.search import place_scores, query_words, word_ok
from app.question.themes import short_name
from app.schemas import Conditions

ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}, "basic": {"want": "구경하기"}}
    base.update(kw)
    return Conditions.model_validate(base)


class FakeChat:
    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def bind_tools(self, schemas):
        self.schemas = schemas
        return self

    async def ainvoke(self, messages):
        self.seen.append(list(messages))
        nxt = self.script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def call(name, args, i="t1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": i}])


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_QUESTION_AGENT", "1")


def use(monkeypatch, script):
    fake = FakeChat(script)
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: fake)
    return fake


def items_of(c):
    return flow.today_items(c)


def test_agent_finds_then_asks_by_name(on, monkeypatch):
    c = cond(extra={"place": "한강"})
    items = items_of(c)
    names = qa.find_places_by(items, "한강")["가까운 곳 이름"][:2]
    assert len(names) == 2
    fake = use(monkeypatch, [call("find_places", {"word": "한강"}),
                             call("submit_question", {"question": "한강 쪽은 어디가 좋으세요?", "choices": names})])
    r = asyncio.run(qa.ask_agent(c, items))
    assert r == {"done": False, "question": "한강 쪽은 어디가 좋으세요?", "choices": names, "slot": None, "source": "agent",
                 "follows": "한강"}
    tool_msgs = [m for m in fake.seen[1] if isinstance(m, ToolMessage)]
    assert tool_msgs and "찾은 곳 수" in tool_msgs[0].content
    assert "37.5" not in str(fake.seen[0][1].content)


def test_agent_theme_and_bank_choices(on, monkeypatch):
    c = cond()
    items = items_of(c)
    use(monkeypatch, [call("submit_question", {"question": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진", "궁 · 한옥"]})])
    r = asyncio.run(qa.ask_agent(c, items))
    assert r and r["source"] == "agent" and set(r["choices"]) <= {"공원", "그림 · 사진", "궁 · 한옥"}


@pytest.mark.parametrize("sub", [
    {"question": "어디가 아프세요?", "choices": ["공원", "그림 · 사진"]},
    {"question": "무엇을 보고 싶으세요?", "choices": ["우주선", "공룡"]},
    {"question": "이건 너무너무너무너무 길어서 스물다섯 자를 넘는 질문이에요?", "choices": ["공원", "그림 · 사진"]},
    {"question": "어떤 구경이 좋으세요?", "choices": ["궁 · 한옥", "공원"]},  # 이미 물음
    {"question": "뭘 하고 싶으세요?", "choices": ["바람 쐬기", "맛있는 것"]},  # want 칸이 이미 참
])
def test_check_rejects(sub):
    c = cond(ai=[{"q": "어떤 구경이 좋으세요?", "choices": [], "a": "공원 · 숲"}])
    assert qa.check_question(c, items_of(c), sub) is None


def test_slot_question_uses_bank_text():
    c = cond()
    r = qa.check_question(c, items_of(c), {"question": "걷는 건 어떠세요?", "choices": ["많이 걸어요", "조금만요"]})
    assert r == {"done": False, "question": "걷는 건 괜찮으세요?", "choices": flow.WALK_CHOICES, "slot": "walk"}
    filled = cond(basic={"want": "구경하기", "walk": "보통이에요"})
    assert qa.check_question(filled, items_of(filled), {"question": "걷는 건 어떠세요?",
                                                        "choices": ["많이 걸어요", "조금만요"]}) is None


def test_clue_names_must_match_clue():
    c = cond(extra={"place": "한강"})
    items = items_of(c)
    found = {short_name(it["place"]) for it, _ in place_scores(items, "한강")}
    other = [n for n in (short_name(it["place"]) for it in items) if n not in found][:2]
    assert len(other) == 2
    assert qa.check_question(c, items, {"question": "한강 근처 어디가 좋으세요?", "choices": other}) is None


def test_agent_done_and_no_submit(on, monkeypatch):
    c = cond()
    use(monkeypatch, [call("submit_question", {"done": True, "question": "", "choices": []})])
    assert asyncio.run(qa.ask_agent(c, items_of(c))) == {"done": True}
    use(monkeypatch, [AIMessage(content="글로만 답해요")])
    assert asyncio.run(qa.ask_agent(c, items_of(c))) is None


def test_round_limit_stops(on, monkeypatch):
    c = cond()
    fake = use(monkeypatch, [call("look_bank", {}, "a"), call("look_bank", {}, "b"), call("look_bank", {}, "c"),
                             call("look_bank", {}, "d")])
    assert asyncio.run(qa.ask_agent(c, items_of(c))) is None
    assert len(fake.seen) == 3  # 도구 2번 뒤 한 번 더 묻고 끝


def test_bad_tool_and_error(on, monkeypatch):
    c = cond()
    fake = use(monkeypatch, [call("nope", {}), call("find_places", {"wrong": 1}, "t2"),
                             call("submit_question", {"question": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진"]}, "t3")])
    r = asyncio.run(qa.ask_agent(c, items_of(c)))
    assert r is None or r["source"] == "agent"
    msgs = [m.content for m in fake.seen[-1] if isinstance(m, ToolMessage)]
    assert "없는 도구예요" in msgs[0] and "입력이 잘못됐어요" in msgs[1]
    use(monkeypatch, [RuntimeError("boom")])
    assert asyncio.run(qa.ask_agent(c, items_of(c))) is None


def test_jev_filters(on, monkeypatch):
    c = cond()
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    sub = {"question": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진"]}

    async def low_natural(state, q, t):
        return 0.3 if q == qa.JEV_NATURAL else 0.9

    use(monkeypatch, [call("submit_question", sub)])
    monkeypatch.setattr(jev, "ask_yes", low_natural)
    assert asyncio.run(qa.ask_agent(c, items_of(c))) is None

    async def none(state, q, t):
        return None

    use(monkeypatch, [call("submit_question", sub)])
    monkeypatch.setattr(jev, "ask_yes", none)
    assert asyncio.run(qa.ask_agent(c, items_of(c)))["source"] == "agent"
    monkeypatch.setenv("AIGO_QUESTION_JEV", "0")
    use(monkeypatch, [call("submit_question", sub)])
    monkeypatch.setattr(jev, "ask_yes", low_natural)
    assert asyncio.run(qa.ask_agent(c, items_of(c)))["source"] == "agent"


def test_endpoint_uses_agent_first_then_falls_back(on, monkeypatch):
    c = cond()
    use(monkeypatch, [call("submit_question", {"question": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진"]})])
    assert asyncio.run(service.next_ai(c))["source"] == "agent"
    use(monkeypatch, [call("submit_question", {"done": True, "question": "", "choices": []})])
    r = asyncio.run(service.next_ai(c))  # 질문 수 고정: done이어도 더 좁히는 질문으로 채워요
    assert r["done"] is False and r["no"] == 4 and r["total"] == 7 and r.get("source") in ("fixed", "lead")
    use(monkeypatch, [RuntimeError("x")])
    called = []

    async def no_single(*a, **k):
        called.append(1)
        return None

    from app.llm import client as llm

    monkeypatch.setattr(llm, "ask_json", no_single)
    r = asyncio.run(service.next_ai(c))
    assert called == [] and (r.get("source") in ("fixed", "lead") or r.get("fallback"))
    use(monkeypatch, [call("submit_question", {"question": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진"]})])
    j = asyncio.run(service.ask_ai(c))
    assert j["no"] == 5 and j["source"] == "agent"


def test_agent_off_switch(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_QUESTION_AGENT", "0")
    fake = use(monkeypatch, [])
    from app.llm import client as llm

    async def none(*a, **k):
        return None

    monkeypatch.setattr(llm, "ask_json", none)
    asyncio.run(service.next_ai(cond()))
    assert fake.seen == []


def test_search_words_and_limits():
    assert query_words("손주랑 한강에서 가고 싶어요") == ["손주", "한강"]
    assert word_ok("") and word_ok("가" * 41) and word_ok("공") and word_ok("숲") is None and word_ok("한강") is None
    c = cond()
    top = place_scores(items_of(c), "서울숲")
    assert top and "서울숲" in top[0][0]["place"]["name"]

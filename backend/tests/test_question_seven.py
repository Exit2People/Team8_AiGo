"""exp/agent-full: 질문 7개 고정 · 질문 에이전트가 no 3~6을 정함 · 1개 더(no 7) · 실패 대신 길."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import config
from app.llm import agent_loop
from app.main import app
from app.question import agent as qa
from app.question import flow, service
from app.question.search import place_scores
from app.question.themes import short_name
from app.schemas import AiAnswer, Conditions
from tests.test_question_agent import FakeChat, call

client = TestClient(app)
ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}}
    base.update(kw)
    return Conditions.model_validate(base)


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_QUESTION_AGENT", "1")


def use(monkeypatch, script):
    fake = FakeChat(script)
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: fake)
    return fake


def answer(c: Conditions, r: dict) -> Conditions:
    """화면처럼 답해요: 칸 질문이면 칸에, 아니면 ai에 첫 선택지."""
    c = c.model_copy(deep=True)
    a = r["choices"][0]
    if r.get("slot") in ("want", "walk", "inout"):
        setattr(c.basic, r["slot"], a)
    else:
        c.ai.append(AiAnswer(q=r["question"], choices=r["choices"], a=a))
    return c


def test_numbering_counts_question_slots_not_heard_ones():
    assert qa.numbering(cond()) == (3, 7)
    assert qa.numbering(cond(basic={"want": "구경하기"}))[0] == 4  # 질문으로 채운 칸
    assert qa.numbering(cond(basic={"want": "구경하기"}, filled=["want"]))[0] == 3  # 첫 말에서 들은 칸


def test_total_env(monkeypatch):
    monkeypatch.setenv("AIGO_QUESTION_TOTAL", "8")
    assert config.question_total() == 8
    monkeypatch.setenv("AIGO_QUESTION_TOTAL", "x")
    assert config.question_total() == 7


def test_agent_drives_all_four_then_skips_extra(on, monkeypatch):
    """no 3~6을 에이전트가 정하고, 앞 답을 이어 받아요. no 7에서 에이전트가 1개 더 필요 없다고 하면 끝."""
    c = cond(extra={"place": "한강", "who": "손주"}, filled=["place", "who"])
    items = flow.today_items(c)
    names = [short_name(it["place"]) for it, _ in place_scores(items, "한강")][:3]
    seen_no = []
    script = [
        ("손주랑 한강에서 뭘 해 보고 싶으세요?", ["물가", "자전거", "꽃 · 정원"]),
        ("물가에서는 뭘 하고 싶으세요?", ["자전거", "공원"]),  # 주제(물가) 안에서 경험 묻기 (이름만 바꿔 되묻지 않아요)
        ("한강에서 무엇을 보고 싶으세요?", ["꽃 · 정원", "전망"]),
        ("돈 내는 곳도 괜찮으세요?", ["괜찮아요", "무료인 곳만요"]),
    ]
    for i, (q, ch) in enumerate(script):
        fake = use(monkeypatch, [call("submit_question", {"question": q, "choices": ch, "follows": "한강"})])
        r = asyncio.run(service.next_ai(c))
        assert r["source"] == "agent", (i, r)
        assert r["total"] == 7 and r["no"] == 3 + i
        first = fake.seen[0][1].content
        assert "남은 질문 수" in first and "이어 받을 말" in first
        if i == 3:
            assert "마지막 질문" in first
            assert r.get("id") == "fee"  # 은행 질문을 그대로 골랐어요
        seen_no.append(r["no"])
        c = answer(c, r)
    assert seen_no == [3, 4, 5, 6]
    # 앞 답("물가")을 이어 받은 질문
    assert qa.follows(cond(extra={"place": "한강"}, ai=[{"q": "x?", "choices": [], "a": "물가"}]), items,
                      "물가는 어디가 좋으세요?") == "물가"
    use(monkeypatch, [call("submit_question", {"done": True, "question": "", "choices": [], "why": "충분히 좁혀졌어요"})])
    assert asyncio.run(service.next_ai(c)) == {"done": True}
    # no 8은 묻지 않아요
    more = c.model_copy(deep=True)
    more.ai.append(AiAnswer(q="끝?", a="x"))
    assert asyncio.run(service.next_ai(more)) == {"done": True}


def test_extra_question_when_needed(on, monkeypatch):
    c = cond(ai=[{"q": f"q{i}?", "choices": [], "a": "x"} for i in range(4)])
    assert qa.numbering(c) == (7, 7)
    items = flow.today_items(c)
    assert len(qa.narrowed(c, items)) >= config.EXTRA_MIN_LEFT
    sub = {"question": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진"], "why": "후보가 아직 많아요"}
    fake = use(monkeypatch, [call("submit_question", sub)])
    r = asyncio.run(service.next_ai(c))
    assert r["extra"] is True and r["no"] == 7 and r["total"] == 8 and r["why"] == "후보가 아직 많아요"
    assert "1개 더" in fake.seen[0][1].content
    # 이유 없이 내면 안 물어요
    use(monkeypatch, [call("submit_question", {k: v for k, v in sub.items() if k != "why"})])
    assert asyncio.run(service.next_ai(c)) == {"done": True}
    # 에이전트가 실패하면 대신 길에서는 1개 더를 묻지 않아요
    use(monkeypatch, [RuntimeError("x")])
    assert asyncio.run(service.next_ai(c)) == {"done": True}


def test_extra_skipped_when_already_narrow(on, monkeypatch):
    c = cond(ai=[{"q": f"q{i}?", "choices": [], "a": "x"} for i in range(3)]
             + [{"q": "어떤 구경이 좋으세요?", "choices": [], "a": "궁 · 한옥"}])
    items = flow.today_items(c)
    left = len(qa.narrowed(c, items))
    assert left < len(items)  # 답한 주제로 좁혀요
    monkeypatch.setattr(config, "EXTRA_MIN_LEFT", left + 1)
    fake = use(monkeypatch, [])
    assert asyncio.run(service.next_ai(c)) == {"done": True}
    assert fake.seen == []  # 에이전트를 부르지도 않아요


def test_agent_failure_still_fills_seven(on, monkeypatch):
    """에이전트가 계속 실패해도 no 3~6이 나오고 total 7을 지켜요."""
    c = cond(extra={"wish": ["꽃 구경"]}, filled=["wish"])
    got = []
    for _ in range(6):
        use(monkeypatch, [RuntimeError("boom")])
        r = asyncio.run(service.next_ai(c))
        if r.get("done"):
            break
        assert r["total"] == 7
        if r.get("fallback"):
            # 화면이 기본 칸 질문으로 대신 물어요
            slot = next(s for s in ("want", "walk", "inout") if not getattr(c.basic, s))
            r = {**flow.BANK.get(slot, flow.WANT_Q), "slot": slot, "choices": list(
                {"want": flow.WANT_CHOICES, "walk": flow.WALK_CHOICES, "inout": flow.INOUT_CHOICES}[slot])}
        assert r.get("source") != "agent"
        got.append(r["question"])
        c = answer(c, r)
    assert len(got) == 4 and len(set(got)) == 4


def test_free_choice_grounded_by_search():
    """풀어 준 것: 정해진 목록에 없는 말도 그 말로 오늘 갈 곳을 찾을 수 있으면 선택지가 돼요."""
    c = cond(extra={"who": "손주"})
    items = flow.today_items(c)
    ok = qa.check_question(c, items, {"question": "손주랑은 어디서 놀고 싶으세요?", "choices": ["한강", "만들기 체험"]})
    assert ok and ok["choices"] == ["한강", "만들기 체험"]
    assert qa.count_choices(c, items, ["한강", "스키장"])["스키장"] == "근거 없음"
    # 25자를 넘는 이어 받는 질문도 32자 안이면 돼요
    long_q = "한강 쪽이 좋으세요, 꽃 · 정원 쪽이 좋으세요?"
    assert 25 < len(long_q) <= config.QUESTION_MAX_LEN
    assert qa.check_question(c, items, {"question": long_q, "choices": ["물가", "꽃 · 정원"]})


def test_filled_slot_not_asked_again_in_other_words():
    """'자전거 타고 싶어' → 바깥을 이미 들었으면 실내 · 바깥을 다른 말로도 묻지 않아요."""
    c = cond(basic={"inout": "바깥이 좋아요"}, extra={"wish": ["자전거 타기"]}, filled=["wish", "inout"])
    items = flow.today_items(c)
    assert qa.check_question(c, items, {"question": "바깥에서 무엇을 보고 싶으세요?", "choices": ["물가", "꽃 · 정원"]}) is None
    assert qa.check_question(c, items, {"question": "실내가 좋으세요, 바깥이 좋으세요?",
                                        "choices": flow.INOUT_CHOICES}) is None
    heavy = cond(body="좀 무거워요")
    assert qa.check_question(heavy, flow.today_items(heavy),
                             {"question": "걸으면서 무엇을 보고 싶으세요?", "choices": ["물가", "꽃 · 정원"]}) is None
    assert qa.check_question(c, items, {"question": "자전거는 어디서 타고 싶으세요?", "choices": ["물가", "숲 · 산"]})


def test_safety_checks_stay():
    c = cond()
    items = flow.today_items(c)
    for sub in [{"question": "무릎은 어떠세요?", "choices": ["공원", "물가"]},
                {"question": "손주 나이는 어떻게 돼요?", "choices": ["공원", "물가"]},
                {"question": "어디 가요? 언제 가요?", "choices": ["공원", "물가"]}]:
        assert qa.check_question(c, items, sub) is None


def test_keyless_seven_questions_then_three_places():
    """키 없이: 처음 말 → 몸 · 시간 → no 3~6 → 끝 → 추천 3곳."""
    c = cond(body=None, time=None)
    o = client.post("/questions/open", json={"conditions": c.model_dump(), "text": "손주랑 공룡 보러 가고 싶어"}).json()
    assert o["next"]["id"] == "body" and o["next"]["total"] == 7
    c = cond()
    asked = []
    for _ in range(8):
        r = client.post("/questions/next", json=c.model_dump()).json()
        if r.get("done"):
            break
        assert r["total"] == 7 and r["no"] == 3 + len(asked)
        if r.get("fallback"):
            slot = next(s for s in ("want", "walk", "inout") if not getattr(c.basic, s))
            r = {"question": slot, "slot": slot, "choices": {"want": flow.WANT_CHOICES, "walk": flow.WALK_CHOICES,
                                                             "inout": flow.INOUT_CHOICES}[slot]}
        asked.append(r["question"])
        c = answer(c, r)
    assert len(asked) == 4
    j = client.post("/recommend", json={"conditions": c.model_dump(), "visited": []}).json()
    assert j["by"] == "rule" and len(j["candidates"]) == 3


def test_no_repeat_of_answers_or_same_choice_set():
    c = cond(ai=[{"q": "어떤 풍경이 좋으세요?", "choices": ["물가", "꽃 · 정원"], "a": "물가"}])
    items = flow.today_items(c)
    # 이미 고른 답은 선택지에서 빠져요 → 하나만 남으면 버려요
    assert qa.check_question(c, items, {"question": "물가 말고 어디가 좋으세요?", "choices": ["물가", "꽃 · 정원"]}) is None
    r = qa.check_question(c, items, {"question": "물가에서 무엇을 보고 싶으세요?", "choices": ["물가", "꽃 · 정원", "전망"]})
    assert r and "물가" not in r["choices"]
    same = cond(ai=[{"q": "무엇을 보고 싶으세요?", "choices": ["공원", "그림 · 사진"], "a": "잘 모르겠어요"}])
    assert qa.check_question(same, items, {"question": "오늘은 무엇이 보고 싶으세요?", "choices": ["그림 · 사진", "공원"]}) is None


def test_slow_agent_keeps_screen_time(on, monkeypatch):
    """에이전트가 늦어도 화면 기본 질문 시간 안에 발전 질문 · 은행으로 답해요."""
    import time

    class Slow(FakeChat):
        async def ainvoke(self, messages):
            await asyncio.sleep(30)

    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: Slow([]))
    monkeypatch.setattr(config, "QUESTION_SCREEN", 2.0)
    c = cond(basic={"want": "구경하기"})
    t0 = time.monotonic()
    r = asyncio.run(service.next_ai(c))
    assert time.monotonic() - t0 < 2.0
    assert r["done"] is False and r["no"] == 4 and r.get("source") != "agent"

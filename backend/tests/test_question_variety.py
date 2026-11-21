"""매번 새로운 질문 (AIGO_QUESTION_VARIETY). 키 없이, 씨앗 고정."""

import asyncio

import pytest

from app.llm import agent_loop
from app.question import agent as qa
from app.question import flow, service, variety
from app.question.lead import lead_question
from app.schemas import Conditions
from tests.test_question_agent import FakeChat, call

ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}, "basic": {"want": "구경하기"}}
    base.update(kw)
    return Conditions.model_validate(base)


@pytest.fixture()
def vary(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    monkeypatch.setenv("AIGO_QUESTION_VARIETY", "1")
    monkeypatch.setenv("AIGO_QUESTION_SEED", "7")
    variety.clear()
    yield
    variety.clear()


def test_off_means_always_same(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    c = cond()
    items = flow.today_items(c)
    qs = {flow.bank_question("sight", items)["question"] for _ in range(5)}
    assert qs == {flow.BANK["sight"]["question"]}
    assert [flow.bank_question("sight", items)["choices"] for _ in range(3)].count(flow.live_choices("sight", items)) == 3
    asyncio.run(service.next_ai(c))
    assert variety.recent() == []  # 꺼져 있으면 기억도 안 해요


def test_keyless_same_utterance_three_times_differs(vary):
    """키 없이 같은 조건을 3번: 최근에 쓴 말투를 피해서 질문 문장이 달라져요."""
    c = cond()
    got = [asyncio.run(service.next_ai(c))["question"] for _ in range(3)]
    assert len(set(got)) == 3, got
    assert all(flow.bank_id_of(q) == flow.bank_id_of(got[0]) for q in got)  # 뜻(은행 질문)은 같아요
    assert variety.recent()[-3:] == got


def test_alt_text_still_counts_as_asked_and_answers_map(vary):
    alt = flow.BANK_ALT["sight"][0]
    c = cond(ai=[{"q": alt, "choices": [], "a": "궁 · 한옥"}])
    assert "sight" in flow.asked_ids(c)
    assert "궁 · 한옥" in flow.answer_themes(c)
    items = flow.today_items(c)
    # 다른 말투로 같은 은행 질문을 또 내면 버려요
    assert qa.check_question(c, items, {"question": flow.BANK["sight"]["question"], "choices": ["궁 · 한옥", "공원 · 숲"]}) is None


def test_agent_gets_recent_and_angle(vary, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AIGO_QUESTION_AGENT", "1")
    variety.remember("어떤 구경이 좋으세요?")
    fake = FakeChat([call("submit_question", {"question": "무엇을 보러 가고 싶으세요?", "choices": ["공원", "그림 · 사진"]})])
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: fake)
    r = asyncio.run(service.next_ai(cond()))
    assert r["source"] == "agent"
    first = fake.seen[0][1].content
    assert "최근에 낸 질문" in first and "어떤 구경이 좋으세요?" in first and "이번 각도" in first
    assert variety.recent()[-1] == "무엇을 보러 가고 싶으세요?"


def test_memory_keeps_last_50(vary):
    for i in range(60):
        variety.remember(f"질문 {i}?")
    assert len(variety.recent()) == variety.RECENT_MAX and variety.recent()[0] == "질문 10?"


def test_lead_choices_shuffle_but_same_set(vary):
    c = cond(extra={"place": "한강"})
    items = flow.today_items(c)
    runs = []
    for _ in range(4):
        runs.append(lead_question(c, items))
        variety.remember(runs[-1]["question"])  # 서버가 낸 질문을 기억하는 것처럼
    assert all(r and r["question"].endswith("어디가 끌리세요?") for r in runs)
    assert len({frozenset(r["choices"]) for r in runs}) == 1
    assert len({r["question"] for r in runs}) == 2  # 두 말투를 번갈아요


def test_bank_neutral_choice_stays_last(vary):
    items = flow.today_items(cond())
    for _ in range(5):
        ch = flow.bank_question("fee", items)["choices"]
        assert ch[-1] == "잘 모르겠어요"

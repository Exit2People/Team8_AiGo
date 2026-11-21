"""앞 답을 지키는 은행 대체와 개인정보 없는 실패 진단."""

import asyncio
import logging

import pytest

from app.llm import agent_loop
from app.question import agent, flow, service
from tests.test_question_agent import FakeChat, call, cond


def items():
    return [{"place": {"name": name, "kind": kind, "info": {"fee": {"free": free}}},
             "route": {"totalMin": 10}}
            for name, kind, free in [("가시장", "시장", True), ("나시장", "시장", True),
                                      ("한강공원", "공원", False), ("남산공원", "공원", True)]]


@pytest.mark.parametrize("answer", ["시장 · 거리", "북적이는 시장"])
def test_bank_uses_selected_market_candidates(answer):
    c = cond(basic={}, ai=[{"q": "어떤 구경이 끌리세요?", "choices": ["시장 · 거리", "공원"], "a": answer}])
    assert flow.best_bank(c, items()) is None
    assert len(flow.narrowed_items(c, items())) == 2
    assert flow.q4_id(c, items()) not in ("sight", "nature", "scenery")
    assert all("풍경" not in q and "자연" not in q for q in agent.look_bank(c, items()))
    assert agent.check_question(c, items(), {"question": flow.BANK["scenery"]["question"],
                                           "choices": flow.BANK["scenery"]["choices"]}) is None


def test_bank_overlap_two_of_four_is_enough():
    c = cond(basic={}, ai=[{"q": "어떤 모습이 끌리세요?", "choices": ["물가", "숲길", "꽃", "골목"], "a": None}])
    assert flow.best_bank(c, items()) != "scenery"
    assert not flow.bank_available(c, "scenery", items())
    assert "어떤 풍경이 좋으세요?" not in agent.look_bank(c, items())


def test_unsplittable_q4_does_not_restore_original_bank():
    c = cond(basic={"want": "바람 쐬기", "walk": "보통이에요"})
    assert flow.q4_id(c, items()[:2]) is None


def test_market_with_second_theme_does_not_reask_market_or_palace():
    left = items()[:2]
    left[0]["place"]["name"] = "한옥시장"
    c = cond(basic={}, extra={"wish": ["시장 구경"]})
    assert flow.best_bank(c, left) is None
    assert "어떤 구경이 좋으세요?" not in agent.look_bank(c, left)


def test_fallback_receives_narrowed_candidates(monkeypatch):
    c = cond(basic={}, ai=[{"q": "구경은요?", "choices": [], "a": "시장 · 거리"}])
    monkeypatch.setattr(flow, "today_items", lambda _: items())
    seen = []
    monkeypatch.setattr(service, "lead_question", lambda _, left: seen.append(left))
    asyncio.run(service.next_ai(c))
    assert [it["place"]["name"] for it in seen[0]] == ["가시장", "나시장"]


def test_single_call_cannot_restore_unrelated_bank(monkeypatch):
    from app.llm import client

    c = cond(basic={}, ai=[{"q": "구경은요?", "choices": [], "a": "시장 · 거리"}])
    monkeypatch.setattr(flow, "today_items", lambda _: items())
    monkeypatch.setattr(service, "lead_question", lambda *_: None)

    async def unrelated(*_):
        return {"done": False, "question": flow.BANK["scenery"]["question"],
                "choices": flow.BANK["scenery"]["choices"], "slot": "none"}

    monkeypatch.setattr(client, "ask_json", unrelated)
    assert asyncio.run(service.next_ai(c)).get("source") != "ai"


def test_validation_log_is_reason_only(caplog):
    caplog.set_level(logging.INFO)
    secret_text = "개인정보가 들어간 자유 답"
    c = cond(ai=[{"q": "앞 질문?", "a": secret_text}])
    assert agent.check_question(c, items(), {"question": secret_text, "choices": []}) is None
    assert "reason=validation check=question_format" in caplog.text
    assert secret_text not in caplog.text


@pytest.mark.parametrize("failure, reason", [(RuntimeError("사용자 말 37.55 key-secret"), "error"),
                                           (asyncio.TimeoutError(), "timeout")])
def test_capped_failure_has_safe_reason(caplog, failure, reason):
    caplog.set_level(logging.INFO)

    async def fail():
        raise failure

    assert asyncio.run(service._capped(fail(), 0.1)) is None
    assert f"reason={reason}" in caplog.text
    assert "사용자 말" not in caplog.text and "key-secret" not in caplog.text


def test_capped_does_not_add_hidden_time_allowance():
    async def late():
        await asyncio.sleep(0.1)
        return {"question": "늦게 온 질문?"}

    assert asyncio.run(service._capped(late(), 0.01)) is None


def test_runtime_failure_has_safe_reason(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: FakeChat([RuntimeError("private key-secret")]))
    assert asyncio.run(agent.ask_agent(cond(), items())) is None
    assert "reason=error error_type=RuntimeError" in caplog.text
    assert "key-secret" not in caplog.text


def test_no_submission_has_own_reason(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(agent_loop, "make_chat", lambda *a, **k: FakeChat([call("look_bank", {})] * 3))
    assert asyncio.run(agent.ask_agent(cond(), items())) is None
    assert "reason=no_submission" in caplog.text


def test_place_list_not_repeated_when_switching_to_fallback(monkeypatch):
    parks = items()[2:]
    parks[1]["place"]["name"] = "여의도한강공원"
    names = [it["place"]["name"] for it in parks]
    c = cond(extra={"place": "한강"}, ai=[{"q": "한강에서 어느 곳으로 갈까요?", "choices": names, "a": None}])
    monkeypatch.setattr(flow, "today_items", lambda _: parks)
    r = asyncio.run(service.next_ai(c))
    assert r.get("source") != "lead"
    assert not set(names).intersection(r.get("choices", []))


def test_named_destination_survives_generic_prompt_and_fallback(monkeypatch):
    parks = items()[2:]
    forest = {"place": {"name": "서울숲", "kind": "공원"}, "route": {"totalMin": 10}}
    today = [forest, *parks]
    c = cond(extra={"place": "서울 숲"}, filled=["place"])
    other_names = [it["place"]["name"] for it in parks]
    assert agent.check_question(c, today, {"question": "어느 공원에 가고 싶으세요?", "choices": other_names}) is None
    monkeypatch.setattr(flow, "today_items", lambda _: today)
    r = asyncio.run(service.next_ai(c))
    assert r["slot"] == "walk"
    c.basic.walk = r["choices"][0]
    assert asyncio.run(service.next_ai(c))["done"]

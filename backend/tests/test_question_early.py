"""C · D: 장소 이름 목록은 한 번만 · 주제 안에서 경험 묻기 · 이미 좁혀졌으면 일찍 끝내기(early)."""

import asyncio
import logging

from app import config
from app.question import agent as qa
from app.question import flow, service
from app.question.search import place_scores
from app.question.themes import short_name, themes_of
from app.schemas import AiAnswer
from tests.test_question_agent import call
from tests.test_question_seven import _now, cond, on, use  # noqa: F401

MARKET_Q = AiAnswer(q="어떤 구경이 끌리세요?", choices=["시장 · 거리", "광장", "물가"], a="시장 · 거리")


def market_names(items, n=4):
    out = []
    for it in items:
        s = short_name(it["place"])
        if "시장 · 거리" in themes_of(it["place"]) and s not in out:
            out.append(s)
    return out[:n]


def test_theme_then_same_theme_names_rejected():
    """'시장'을 골랐는데 '어떤 시장이 끌리세요?' [시장 이름들]은 이름만 바꿔 되묻기라 버려요."""
    c = cond(ai=[MARKET_Q.model_dump()])
    items = flow.today_items(c)
    names = market_names(items)
    assert len(names) >= 2
    assert qa.check_question(c, items, {"question": "그럼 시장은 어떤 곳이 끌리세요?", "choices": names}) is None
    # 주제 안에서 경험을 묻는 질문은 돼요 (곳 수로 셀 수 없는 '구경하며 걷기'도)
    ok = qa.check_question(c, items, {"question": "시장에서는 뭘 하고 싶으세요?",
                                      "choices": ["먹거리 맛보기", "구경하며 걷기", "앉아서 먹기"]})
    assert ok and ok["choices"] == ["먹거리 맛보기", "구경하며 걷기", "앉아서 먹기"]
    # 아무 말이나 되는 건 아니에요
    assert qa.check_question(c, items, {"question": "시장에서는 뭘 보고 싶으세요?", "choices": ["우주선", "로켓"]}) is None


def test_name_list_only_once():
    c = cond(extra={"place": "한강"}, filled=["place"])
    items = flow.today_items(c)
    names = []
    for it, _ in place_scores(items, "한강"):
        if short_name(it["place"]) not in names:
            names.append(short_name(it["place"]))
    assert len(names) >= 4
    first = {"question": "한강은 어디가 좋으세요?", "choices": names[:2]}
    assert qa.check_question(c, items, first)  # 가고 싶은 곳을 말했으면 한 번은 돼요
    c.ai.append(AiAnswer(q=first["question"], choices=names[:2], a="잘 모르겠어요"))
    assert qa.names_used(c, items)
    assert qa.check_question(c, items, {"question": "한강 쪽은 어느 곳이 끌리세요?", "choices": names[2:4]}) is None


def test_prompt_and_first_message_steer_to_experience():
    assert "이름만 바꿔 되묻지 마" in qa.SYSTEM and "한 대화에서 많아야 한 번" in qa.SYSTEM
    assert "질문 수는 정해져 있어. 이미 좁혀졌어도 done 으로 끝내지 말고" not in qa.SYSTEM
    c = cond(ai=[MARKET_Q.model_dump()])
    items = flow.today_items(c)
    msg = qa.first_message(c, items, 4, 7)
    assert "앞 답 주제" in msg and "시장 · 거리" in msg["앞 답 주제"]
    assert "쓰지 마요" in msg["장소 이름 목록"]
    # 이름을 늘어놓고 싶어지지 않게 찾은 곳 이름은 보여 주지 않아요
    assert all("가까운 곳 이름" not in f for f in msg["단서 · 앞 답으로 미리 찾은 곳 (find_places 결과)"].values())


def test_early_when_place_chosen_without_calling_agent(on, monkeypatch):
    c = cond(ai=[MARKET_Q.model_dump()])
    items = flow.today_items(c)
    name = market_names(items, 1)[0]
    c.ai.append(AiAnswer(q="어느 시장이 좋으세요?", choices=[name, "광장"], a=name))
    fake = use(monkeypatch, [])
    r = asyncio.run(service.next_ai(c))
    assert r["done"] is True and r["early"] is True and r["why"] == "가고 싶은 곳을 골라 주셨어요."
    assert r["no"] == 5 and r["total"] == 7  # 진행 표시는 그대로
    assert fake.seen == []  # 에이전트를 부르지 않아 빨라요


def test_early_when_theme_cannot_be_split_further(on, monkeypatch):
    """시장 125곳은 다 시장 · 먹거리라 주제로 더 못 나눠요 → 경험을 한 번 물은 뒤 끝내요."""
    c = cond(ai=[MARKET_Q.model_dump()])
    items = flow.today_items(c)
    assert qa.unsplit(c, items)
    assert qa.early_done(c, items, 4) is None  # 주제를 막 고른 바로 뒤에는 그 안의 경험을 한 번 물어요
    c.ai.append(AiAnswer(q="시장에서는 뭘 하고 싶으세요?", choices=["먹거리 맛보기", "구경하며 걷기"], a="먹거리 맛보기"))
    fake = use(monkeypatch, [])
    r = asyncio.run(service.next_ai(c))
    assert r["early"] is True and "시장 · 거리" in r["why"] and r["no"] == 5
    assert fake.seen == []


def test_early_when_narrowed_small(on, monkeypatch):
    c = cond(ai=[{"q": "어떤 구경이 좋으세요?", "choices": [], "a": "궁 · 한옥"}])
    items = flow.today_items(c)
    monkeypatch.setattr(config, "EARLY_LEFT", len(qa.narrowed(c, items)))
    use(monkeypatch, [])
    r = asyncio.run(service.next_ai(c))
    assert r["early"] is True and "곳으로 좁혀졌어요" in r["why"]


def test_agent_may_end_early_from_no4_only(on, monkeypatch, caplog):
    c = cond(extra={"place": "서울숲"}, filled=["place"])
    done = {"done": True, "question": "", "choices": [], "why": "서울숲으로 가고 싶은 곳이 정해졌어요."}
    # no 3에서는 끝내지 않아요 (질문 수를 채우는 길로)
    use(monkeypatch, [call("submit_question", done)])
    r = asyncio.run(service.next_ai(c))
    assert r.get("done") is not True and r["no"] == 3
    c.ai.append(AiAnswer(q="서울숲에서는 뭘 하고 싶으세요?", choices=["산책하기", "꽃 구경"], a="꽃 구경"))
    use(monkeypatch, [call("submit_question", done)])
    with caplog.at_level(logging.INFO, logger="aigo.question.agent"):
        r = asyncio.run(service.next_ai(c))
    assert r == {"done": True, "early": True, "why": done["why"], "no": 4, "total": 7}
    assert "서울숲" not in caplog.text and "agent_done" in caplog.text  # why 원문은 로그에 남기지 않아요


def test_agent_done_ignored_when_still_wide(on, monkeypatch):
    """좁혀지지 않았으면 에이전트가 done 을 내도 일찍 끝내지 않아요."""
    c = cond(ai=[{"q": "어떤 날씨가 좋으세요?", "choices": [], "a": "잘 모르겠어요"}])
    items = flow.today_items(c)
    assert not qa.may_end_early(c, items, 4)
    use(monkeypatch, [call("submit_question", {"done": True, "question": "", "choices": [], "why": "다 됐어요."})])
    r = asyncio.run(service.next_ai(c))
    assert r.get("done") is not True


def test_extra_no7_is_not_early():
    c = cond(ai=[{"q": f"q{i}?", "choices": [], "a": "x"} for i in range(4)])
    assert qa.numbering(c)[0] == config.question_total()
    assert qa.early_done(c, flow.today_items(c), 7) is None
    assert config.EARLY_LEFT < config.EXTRA_MIN_LEFT

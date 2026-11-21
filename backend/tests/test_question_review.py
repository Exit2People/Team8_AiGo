"""질문 에이전트 리뷰(Codex 1~3번)에서 나온 것을 지켜요."""

import pytest

from app import config
from app.data import filter_places as fp
from app.question import agent as qa
from app.question import flow
from app.schemas import Conditions

ORIGIN = {"id": "1120059000", "name": "금호1가동", "type": "동", "lat": 37.553669, "lng": 127.025056}
SIGHT = flow.BANK["sight"]["choices"]


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-23T11:00")


def cond(ai=None) -> Conditions:
    return Conditions.model_validate({
        "origin": ORIGIN, "body": "보통이에요", "time": "한나절",
        "range": {"oneWayMin": 60, "walk": "제한 없음", "avoid": []},
        "basic": {"want": "구경하기", "walk": None, "inout": None},
        "ai": ai or [],
    })


def items_for(c: Conditions) -> list[dict]:
    return fp.filter_places(c, config.now(), "맑음", [])


def test_bank_question_is_fine_the_first_time():
    c = cond()
    r = qa.check_question(c, items_for(c), {"question": flow.BANK["sight"]["question"], "choices": SIGHT})
    assert r is not None and len(r["choices"]) >= 2


def test_bank_question_not_repeated_in_other_words():
    # 앞에서 다른 말투로 같은 선택지를 물었으면, 은행 문장 그대로여도 되풀이로 봐요
    c = cond(ai=[{"q": "오늘 어떤 구경을 하실래요?", "choices": [*SIGHT, "잘 모르겠어요"], "a": "잘 모르겠어요"}])
    r = qa.check_question(c, items_for(c), {"question": flow.BANK["sight"]["question"], "choices": SIGHT})
    assert r is None


def test_bank_question_drops_choices_with_no_place_today():
    # 오늘 후보가 공원 한 곳뿐이면 구경 종류로 나눌 수 없어요. 0곳 선택지를 보여 주지 않아요
    c = cond()
    park = [x for x in items_for(c) if x["place"].get("kind") == "공원"][:1]
    assert park
    r = qa.check_question(c, park, {"question": flow.BANK["sight"]["question"], "choices": SIGHT})
    assert r is None


def test_numbering_counts_unsure_answers_sent_in_ai():
    # 화면이 기본 칸 질문의 '잘 모르겠어요'를 ai 에 넣어 보내면 번호가 올라가요 (FE에 넘긴 약속)
    before = qa.numbering(cond())
    after = qa.numbering(cond(ai=[{"q": "걷는 건 괜찮으세요?", "choices": ["많이 걸어요", "보통이에요"], "a": "잘 모르겠어요"}]))
    assert after[0] == before[0] + 1

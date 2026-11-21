import asyncio

from fastapi.testclient import TestClient

from app.llm import client as llm
from app.main import app
from app.question import flow, opening, service
from app.question.lead import eun_neun, lead_question
from app.question.themes import short_name, themes_of
from app.schemas import Conditions

client = TestClient(app)

ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}}
    base.update(kw)
    return Conditions.model_validate(base)


def test_question_open_first_then_empty_fixed():
    c = cond(body=None, time=None)
    assert flow.next_step(c, [])["id"] == "open"
    assert flow.next_step(c, [0])["id"] == "body"
    assert flow.next_step(c, [0, 1])["id"] == "time"
    c2 = cond()  # body · time 찼음
    assert flow.next_step(c2, [0])["id"] == "want"


def test_question_order_to_done():
    c = cond(basic={"want": "구경하기"})
    q4 = flow.next_step(c, [0, 1, 2, 3])
    assert q4["no"] == 4 and q4["source"] in ("fixed", "lead")
    q5 = flow.next_step(c, [0, 1, 2, 3, 4])
    assert q5 == {"done": False, "no": 5, "needsAi": True, "fallback": None}
    assert flow.next_step(c, [0, 1, 2, 3, 4, 5]) == {"done": True}


def test_question_fixed_mode(monkeypatch):
    monkeypatch.setenv("AIGO_QUESTION_START", "fixed")
    c = cond(body=None, time=None)
    assert flow.next_step(c, [])["id"] == "want"


def test_question_q4_pool_by_want():
    c = cond(basic={"want": "구경하기"})
    assert flow.q4_id(c, None) == "sight"
    heavy = cond(body="좀 무거워요", basic={"want": "바람 쐬기"})
    assert flow.q4_id(heavy, None) == "nature"  # 몸이 무거우면 walk 건너뜀


def test_question_live_choices_hide_empty():
    items = flow.today_items(cond())
    assert items, "오늘 후보가 있어야 해요"
    ch = flow.live_choices("sight", items)
    counts = flow.bank_counts("sight", items)
    assert all(counts[c] > 0 for c in ch if c in counts)


def test_question_compute_range():
    r = opening.compute_range("좀 무거워요", "하루 종일", None)
    assert r.oneWayMin == 30 and r.walk == "조금만" and r.avoid == ["산", "버스 환승"]
    assert opening.compute_range("보통이에요", "한나절", "많이 걸어요").walk == "보통"
    assert opening.compute_range("가뿐해요", "반나절", "조금만요").walk == "조금만"
    assert opening.compute_range(None, None, None).oneWayMin == 60


def test_question_clean_hint():
    assert opening.clean_hint(" 한강! ") == "한강"
    assert opening.clean_hint("무릎 아픈데") is None
    assert opening.clean_hint("어디든") is None
    assert opening.clean_hint("010 1234") is None
    assert opening.clean_hint("12345") is None
    assert opening.clean_hint("아주아주아주아주긴말입니다") is None


def test_question_apply_does_not_overwrite():
    c = cond(basic={"want": "구경하기"})
    v = {"body": "좀 무거워요", "time": "반나절", "want": "맛있는 것", "walk": "모름", "inout": "모름",
         "place": "한강", "who": "손주", "wish": ["사진 찍기", "사진 찍기"], "wish_where": "둘 다"}
    new, filled = opening.apply(c, v)
    assert new.body == "보통이에요" and new.basic.want == "구경하기"
    assert new.extra.place == "한강" and new.extra.who == "손주" and new.extra.wish == ["사진 찍기"]
    assert set(filled) == {"place", "who", "wish"} and new.basic.inout is None


def test_question_apply_fills_and_range():
    c = cond(body=None, time=None)
    v = {"body": "좀 무거워요", "time": "모름", "want": "모름", "walk": "모름", "inout": "모름",
         "place": "", "who": "모름", "wish": ["자전거 타기"], "wish_where": "모름"}
    new, filled = opening.apply(c, v)
    assert new.body == "좀 무거워요" and new.range.oneWayMin == 30
    assert new.basic.inout == "바깥이 좋아요" and "inout" in filled


def test_question_heard_and_forget():
    c = cond(time="반나절", extra={"place": "한강", "who": "손주", "wish": ["사진 찍기"]},
             filled=["place", "who", "wish", "time"])
    h = opening.heard(c, c.filled)
    assert h["text"] == "이렇게 들었어요: 한강 · 손주랑 · 사진 찍기 · 3시간쯤"
    assert opening.heard(c, [])["items"] == []
    f = opening.forget(c, "time", None)
    assert f.time is None and "time" not in f.filled and f.range.oneWayMin == 60
    f2 = opening.forget(c, "wish", "사진 찍기")
    assert f2.extra.wish == [] and "wish" not in f2.filled
    assert opening.forget(c, "nope", None) == c


def test_question_open_endpoint_without_key():
    body = {"conditions": cond(body=None, time=None).model_dump(), "text": "손주랑 한강 가고 싶어요"}
    r = client.post("/questions/open", json=body)
    j = r.json()
    assert r.status_code == 200 and j["filled"] == []
    assert j["heard"]["title"] == "몇 가지만 여쭤볼게요"
    assert j["next"]["id"] == "body"
    assert client.post("/questions/open", json={**body, "text": "가" * 501}).status_code == 422


def test_question_open_endpoint_with_fake_ai(monkeypatch):
    async def fake(system, payload, schema, timeout, max_tokens=2000):
        assert "37." not in str(payload)
        return {"body": "모름", "time": "반나절", "want": "모름", "walk": "모름", "inout": "모름", "place": "한강",
                "who": "손주", "wish": ["사진 찍기"], "wish_where": "둘 다"}

    monkeypatch.setattr(llm, "ask_json", fake)
    body = {"conditions": cond(body=None, time=None).model_dump(), "text": "손주랑 한강 가서 사진 찍고 싶어요"}
    j = client.post("/questions/open", json=body).json()
    assert j["heard"]["text"] == "이렇게 들었어요: 한강 · 손주랑 · 사진 찍기 · 3시간쯤"
    assert j["conditions"]["range"]["oneWayMin"] == 30
    assert j["next"]["id"] == "body"


def test_question_forget_endpoint():
    c = cond(time="반나절", extra={"who": "손주"}, filled=["who", "time"])
    j = client.post("/questions/open/forget", json={"conditions": c.model_dump(), "key": "who", "value": None}).json()
    assert j["conditions"]["extra"]["who"] is None and j["heard"]["text"] == "이렇게 들었어요: 3시간쯤"


def test_question_next_answered_body():
    c = cond()
    j = client.post("/questions/next", json={"conditions": c.model_dump(), "answered": [0]}).json()
    assert j["id"] == "want"


def test_question_next_conditions_only_no_key():
    c = cond(basic={"want": "구경하기"})
    j = client.post("/questions/next", json=c.model_dump()).json()
    assert j["done"] is False and (j.get("question") or j.get("fallback"))
    full = cond(ai=[{"q": "a?", "choices": [], "a": "x"}] * 3)
    assert client.post("/questions/next", json=full.model_dump()).json() == {"done": True}
    fb = cond(fallback=True)
    assert client.post("/questions/next", json=fb.model_dump()).json() == {"done": False, "fallback": True}


def test_question_next_ai_validates(monkeypatch):
    async def fake(system, payload, schema, timeout, max_tokens=2000):
        return {"done": False, "question": "어떤 분위기가 좋으세요?", "choices": ["조용한 곳", "북적이는 곳", "탁 트인 곳", "아늑한 곳"],
                "slot": "none"}

    monkeypatch.setattr(llm, "ask_json", fake)
    c = cond(basic={"want": "구경하기"})
    j = asyncio.run(service.next_ai(c))
    assert j["question"] == "어떤 분위기가 좋으세요?" and j["slot"] is None and j["source"] == "ai"

    async def bad(system, payload, schema, timeout, max_tokens=2000):
        return {"done": False, "question": "어디가 아프세요?", "choices": ["a", "b", "c", "d"], "slot": "none"}

    monkeypatch.setattr(llm, "ask_json", bad)
    j = asyncio.run(service.next_ai(c))
    assert j.get("source") != "ai"


def test_question_next_ai_walk_slot_uses_bank(monkeypatch):
    async def fake(system, payload, schema, timeout, max_tokens=2000):
        return {"done": False, "question": "많이 걸으셔도 돼요?", "choices": ["네", "아니요"], "slot": "walk"}

    monkeypatch.setattr(llm, "ask_json", fake)
    j = asyncio.run(service.next_ai(cond(basic={"want": "구경하기"})))
    assert j["question"] == "걷는 건 괜찮으세요?" and j["choices"] == flow.WALK_CHOICES and j["slot"] == "walk"


def test_question_ai_graph_without_key():
    j = client.post("/questions/ai", json=cond(basic={"want": "구경하기"}).model_dump()).json()
    assert j.get("fallback") or (j["no"] == 5 and j["source"] == "fixed" and len(j["choices"]) >= 2)


def test_question_lead_from_place():
    c = cond(extra={"place": "한강"})
    items = flow.today_items(c)
    q = lead_question(c, items)
    assert q and q["question"] == "한강 쪽, 어디가 끌리세요?" and 2 <= len(q["choices"]) <= 3
    again = cond(extra={"place": "한강"}, ai=[{"q": q["question"], "choices": q["choices"], "a": q["choices"][0]}])
    assert lead_question(again, items) is None


def test_question_eun_neun_and_short_name():
    assert eun_neun("공룡") == "은" and eun_neun("사진 찍기") == "는"
    assert short_name({"name": "[서울시립미술관] 2026 찾아가는 미술감상 교실"}) == "찾아가는 미술감상 교실"


def test_question_themes():
    assert "물가" in themes_of({"name": "여의도한강공원", "kind": "공원"})
    assert "궁 · 한옥" in themes_of({"name": "경복궁", "kind": "박물관"})

"""추천 · 질문 · 톡방 품질 보강 시험."""

import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import chat_safety, config, db
from app.data import loader, places_db, route
from app.main import app
from app.question import opening
from app.recommend.pick import rule_reason
from app.recommend.verify import check
from app.schemas import Conditions
from tests.fakedb import FakeDB

client = TestClient(app)
ORIGIN = {"id": "SM-0150", "name": "서울역", "type": "역"}


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")


def cond(**kw) -> Conditions:
    base = {"origin": ORIGIN, "body": "보통이에요", "time": "하루 종일",
            "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}}
    base.update(kw)
    return Conditions.model_validate(base)


def _item(free=None):
    return {"place": {"id": "X", "inout": "실내", "walkMin": 5, "terrain": [], "info": {"fee": {"free": free}}},
            "route": {"totalMin": 18, "transfers": 0, "legs": [{"kind": "하차", "walkMin": 5}]}}


def test_reason_check_fee_and_hours():
    assert check("무료라 부담 없어요", _item(free=True))
    assert not check("무료라 부담 없어요", _item(free=False))
    assert not check("무료라 부담 없어요", _item(free=None))
    assert not check("편도 18분, 3천원이에요", _item(free=False))
    assert not check("1시간이면 다 봐요", _item())
    assert check("갈아타지 않고 18분이면 가요", _item())


def test_question_body_check():
    assert opening.asks_body("오늘 몸은 좀 어떠세요?")
    assert opening.asks_body("컨디션은 괜찮으세요?")
    assert opening.asks_body("무릎은 괜찮으세요?")
    assert opening.asks_body("어디가 좋으세요?", ["허리 편한 곳", "물가"])
    assert not opening.asks_body("어떤 풍경이 좋으세요?", ["물가", "숲길"])


def test_weekly_closed_day_fixed():
    p = {"closed": [], "museum": {"closedText": "매년 1월1일, 매주 월요일"}}
    places_db._fix_closed(p)
    assert p["closed"] == [0]
    q = {"closed": [6], "museum": {"closedText": "매주 둘째 넷째 일요일"}}
    places_db._fix_closed(q)
    assert q["closed"] == [6]
    ids = {x["id"]: x for x in loader.places()}
    for pid in ("CS1503b961", "CSa63548af"):
        if pid in ids:
            assert 0 in ids[pid]["closed"]


def test_outdoor_wish_without_ai_skips_inout():
    c, filled = asyncio.run(opening.parse_open(cond(), "손주랑 자전거 타고 싶어"))
    assert c.basic.inout == "바깥이 좋아요" and filled == ["inout"] and "inout" in c.filled
    c2, f2 = asyncio.run(opening.parse_open(cond(basic={"inout": "실내가 좋아요"}), "자전거 타고 싶어"))
    assert c2.basic.inout == "실내가 좋아요" and f2 == []
    c3, f3 = asyncio.run(opening.parse_open(cond(), "조용히 쉬고 싶어요"))
    assert c3.basic.inout is None and f3 == []


def test_rule_reason_food_wording():
    it = {"place": {"id": "M", "kind": "시장", "wants": ["맛있는 것"], "market": {"food": 0}},
          "route": {"totalMin": 21, "transfers": 0, "legs": []}}
    r = rule_reason(it, cond(basic={"want": "맛있는 것"}))
    assert r.startswith("먹을 것이 있는 곳이에요.") and "맛있는 것 좋은" not in r


def test_estimated_route_says_transfer():
    sts = loader.stations()
    a = sts[0]
    b = next(s for s in sts if s["name"] != a["name"] and not set(s.get("lines") or []) & set(a.get("lines") or []))
    r = route.estimate_route(a["name"], {"station": b["name"], "walkMin": 3}, datetime(2026, 11, 21, 11, 0))
    assert r["transfers"] == 1 and r["legs"][-1]["tip"] == "중간에 한 번 갈아타요"
    same = next(s for s in sts if s["name"] != a["name"] and set(s.get("lines") or []) & set(a.get("lines") or []))
    r0 = route.estimate_route(a["name"], {"station": same["name"], "walkMin": 3}, datetime(2026, 11, 21, 11, 0))
    assert r0["transfers"] == 0 and "tip" not in r0["legs"][-1]


def test_late_recommend_keeps_picks(monkeypatch):
    monkeypatch.setattr(config, "RECOMMEND_TOTAL", 0.0)
    r = client.post("/recommend", json={"conditions": cond(basic={"want": "바람 쐬기"}).model_dump(), "visited": []})
    j = r.json()
    assert r.status_code == 200 and j["notFound"] is False and j["by"] == "rule"
    assert 1 <= len(j["candidates"]) <= 3 and all("info" in c for c in j["candidates"])


def test_chat_phone_masked_before_check(monkeypatch):
    f = FakeDB()
    monkeypatch.setattr(db, "executor", f)
    seen = []

    async def fake_blocked(text, mine=None, others=None):
        seen.append(text)
        return False

    monkeypatch.setattr(chat_safety, "is_blocked", fake_blocked)
    p = loader.places()[0]["id"]
    client.post(f"/chat/{p}/join", json={"client": "client-aaaa", "nick": "봄나들이"})
    r = client.post(f"/chat/{p}/messages", json={"client": "client-aaaa", "text": "제 번호는 010-1234-5678 이에요"}).json()
    assert seen and "1234" not in seen[0]
    assert r["text"] == "제 번호는 (전화번호는 가렸어요) 이에요"


def test_env_strips_newlines(monkeypatch):
    monkeypatch.setenv("AIGO_QUESTION_AGENT", "0\n")
    assert config.env("AIGO_QUESTION_AGENT") == "0"
    monkeypatch.setenv("KAKAO_REST_API_KEY", " k \n")
    assert config.env("KAKAO_REST_API_KEY") == "k"
    monkeypatch.setenv("KAKAO_REST_API_KEY", "  ")
    assert config.env("KAKAO_REST_API_KEY", "기본") == "기본"


def test_cors_default_has_submit_url(monkeypatch):
    import re

    monkeypatch.delenv("AIGO_CORS_REGEX", raising=False)
    assert re.fullmatch(config.cors_regex(), "https://ai-go-team8.vercel.app")
    assert re.fullmatch(config.cors_regex(), "https://aigo-final-phi.vercel.app")
    assert not re.fullmatch(config.cors_regex(), "https://evil.vercel.app")


def test_link_filter_word_boundary():
    from app.routers.social import _LINK

    assert _LINK.search("abc.com 들어가 보세요") and _LINK.search("a@b.co.kr") and _LINK.search("www.x")
    assert not _LINK.search("오늘 3.cool 하네요") and not _LINK.search("1.co2 측정")


def test_kakao_places_dedup_and_visited(monkeypatch):
    from app.recommend import map_candidates as mc

    doc = {"id": "123", "place_name": "테스트공원", "x": "126.9726", "y": "37.5559",
           "address_name": "서울 중구 봉래동2가", "road_address_name": "서울 중구 한강대로 405", "category_name": "여행 > 공원"}

    async def fake(c, name):
        return doc

    monkeypatch.setattr(mc, "_lookup", fake)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "k")
    a = asyncio.run(mc.resolve(["테스트공원", "테스트 공원"], cond(), config.now(), "맑음", 3.0))
    assert [x["place"]["id"] for x in a] == ["KAKAO:123"]
    b = asyncio.run(mc.resolve(["테스트공원"], cond(), config.now(), "맑음", 3.0, ["KAKAO:123"]))
    assert [x.get("visited") for x in b] == [True]  # 다녀온 곳은 표시만


def test_relax_measures_once(monkeypatch):
    from app.data import filter_places as fp
    from app.data import transit
    from app.recommend import service

    real = fp.filter_places

    def first_empty(c, now, w, visited=None, **kw):
        # 원래 상한(30분)으로는 0곳 → 넓혀 찾기를 타게 해요
        return [] if c.range.oneWayMin == 30 else real(c, now, w, visited, **kw)

    seen = []

    async def fake_measure(items, c, now, budget):
        if items:
            seen.append(c.range.oneWayMin)
        return items

    monkeypatch.setattr(service.fp, "filter_places", first_empty)
    monkeypatch.setattr(transit, "enabled", lambda: True)
    monkeypatch.setattr(transit, "measure_all", fake_measure)
    c = cond(range={"oneWayMin": 30, "walk": "보통", "avoid": []})
    j = client.post("/recommend", json={"conditions": c.model_dump(), "visited": []}).json()
    assert j.get("relaxed") is True and seen
    # 넓힌 상한(30+20)으로 한 번만 재요. 예전에는 50+20=70으로 한 번 더 넓혀 쟀어요
    assert max(seen) == 30 + config.AGENT_RELAX_MIN


def test_visited_places_can_come_back():
    from app.recommend.pick import limit_revisits, rule_score

    def v(pid, visited=False, name="곳"):
        it = {"place": {"id": pid, "name": name, "wants": []}, "route": {"totalMin": 20, "transfers": 0, "legs": []}}
        if visited:
            it["visited"] = True
        return {"item": it, "reason": "r"}

    # 다녀온 곳은 점수만 깎여요
    a, b = v("A")["item"], v("B", True)["item"]
    assert rule_score(a, cond()) - rule_score(b, cond()) == config.VISITED_PENALTY
    # 3곳 가운데 다녀온 곳은 1곳까지, 맨 앞에는 새로운 곳
    out = limit_revisits([v("A", True), v("B", True), v("C"), v("D")], cond())
    assert [x["item"]["place"]["id"] for x in out] == ["C", "A", "D"]
    # 새로운 곳이 하나도 없으면 다녀온 곳만으로 3곳까지 채워요
    assert [x["item"]["place"]["id"] for x in limit_revisits([v("A", True), v("B", True)], cond())] == ["A", "B"]
    # 어르신이 직접 말한 곳이면 깎지도 줄이지도 않아요
    named = v("S", True, "서울숲")
    c = cond(extra={"place": "서울숲"})
    assert rule_score(named["item"], c) > rule_score(v("X")["item"], c)
    assert limit_revisits([named, v("C")], c)[0]["item"]["place"]["id"] == "S"


def test_recommend_with_visited_shows_at_most_one(monkeypatch):
    c = cond(basic={"want": "바람 쐬기"})
    first = client.post("/recommend", json={"conditions": c.model_dump(), "visited": []}).json()
    ids = [x["place"]["id"] for x in first["candidates"]]
    j = client.post("/recommend", json={"conditions": c.model_dump(), "visited": ids}).json()
    got = j["candidates"]
    assert got and sum(1 for x in got if x.get("visited")) <= config.MAX_VISITED_SHOWN
    assert not got[0].get("visited")


def test_rule_pick_keeps_one_familiar_slot():
    from app.recommend.pick import pick_by_rule

    def it(pid, kind, wants, visited=False):
        x = {"place": {"id": pid, "name": pid, "kind": kind, "wants": wants},
             "route": {"totalMin": 20, "transfers": 0, "legs": []}}
        if visited:
            x["visited"] = True
        return x

    c = cond(basic={"want": "바람 쐬기"})
    fits = [it("A", "공원", ["바람 쐬기"]), it("B", "시장", ["바람 쐬기"]), it("C", "행사", ["바람 쐬기"])]
    # 잘 맞는 다녀온 곳은 마지막 자리로 들어와요
    got = [p["item"]["place"]["id"] for p in pick_by_rule([*fits, it("V", "박물관", ["바람 쐬기"], True)], c)]
    assert "V" in got and got[0] != "V"
    # 잘 안 맞는 다녀온 곳은 억지로 넣지 않아요
    got = [p["item"]["place"]["id"] for p in pick_by_rule([*fits, it("W", "박물관", [], True)], c)]
    assert "W" not in got


def test_named_place_first_even_if_visited():
    sf = [p["id"] for p in loader.places() if p.get("name") == "서울숲"]
    assert sf
    c = cond(extra={"place": "서울숲"})
    for visited in ([], sf):  # 기록 없음 · 어제 다녀옴 모두
        j = client.post("/recommend", json={"conditions": c.model_dump(), "visited": visited}).json()
        assert j["candidates"][0]["place"]["name"] == "서울숲"
        assert j["candidates"][0]["reason"].startswith("말씀하신 서울숲")


def test_open_place_without_ai():
    from app.question.opening import place_only

    c, f = asyncio.run(opening.parse_open(cond(), "서울숲 가고 싶어"))
    assert c.extra.place == "서울숲" and "place" in f and "place" in c.filled
    assert place_only(cond(), "오늘 바람 쐬러 공원 가고 싶어요")[0].extra.place is None
    assert place_only(cond(extra={"place": "한강"}), "서울숲 가고 싶어")[1] == []  # 이미 있으면 덮지 않아요


def test_daily_jitter_is_small_and_stable(monkeypatch):
    from app.recommend.pick import daily_jitter

    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    a = [daily_jitter(f"P{i}") for i in range(200)]
    assert a == [daily_jitter(f"P{i}") for i in range(200)]  # 같은 날엔 늘 같아요
    assert all(abs(x) <= config.DAILY_JITTER / 2 for x in a)
    monkeypatch.setenv("AIGO_NOW", "2026-11-22T11:00")
    assert a != [daily_jitter(f"P{i}") for i in range(200)]  # 날이 바뀌면 달라져요


def test_recently_shown_goes_back():
    from app.recommend.pick import rule_score
    from app.recommend.service import _mark_shown

    def it(pid):
        return {"place": {"id": pid, "name": pid, "wants": []}, "route": {"totalMin": 20, "transfers": 0, "legs": []}}

    items = _mark_shown([it("A"), it("B"), it("C")], {"A", "B"}, {"B"})
    assert items[0].get("shownRecent") and not items[1].get("shownRecent") and not items[2].get("shownRecent")
    assert rule_score(it("C"), cond()) - rule_score(items[0], cond()) == config.SHOWN_PENALTY


def test_recommend_accepts_shown_and_changes_list():
    c = cond(basic={"want": "구경하기"})
    first = client.post("/recommend", json={"conditions": c.model_dump(), "visited": []}).json()["candidates"]
    ids = [x["place"]["id"] for x in first]
    again = client.post("/recommend", json={"conditions": c.model_dump(), "visited": [], "shown": ids}).json()["candidates"]
    assert again and [x["place"]["id"] for x in again] != ids  # 어제 보여 준 곳이 그대로 반복되지 않아요


def test_paraphrased_question_is_rejected():
    from app.question.agent import same_as_asked

    c = cond(ai=[{"q": "손주와 자전거 타러 어디로 갈까요?", "choices": ["서울숲", "뚝섬한강공원", "여의도한강공원"], "a": "서울숲"}])
    assert same_as_asked(c, ["서울숲", "뚝섬한강공원", "여의도한강공원"])  # 글만 바꾼 같은 질문
    assert same_as_asked(c, ["서울숲", "여의도한강공원"])
    assert not same_as_asked(c, ["숲길", "물가", "탁 트인 광장"])  # 다른 질문
    assert not same_as_asked(c, ["서울숲", "숲길", "물가"])  # 하나만 겹치면 괜찮아요


def test_dont_know_slot_question_not_asked_again():
    from app.question import flow

    walk_q = flow.BANK["walk"]
    # 화면은 '잘 모르겠어요'로 답한 걷기 질문을 a=None 기록으로 보내요
    c = cond(ai=[{"q": walk_q["question"], "choices": walk_q["choices"], "a": None}])
    assert "walk" in flow.asked_ids(c)
    for _ in range(3):
        q = client.post("/questions/next", json=c.model_dump()).json()
        if q.get("done") or q.get("fallback"):
            break
        assert q.get("question") != walk_q["question"]
        c = cond(ai=[*[x.model_dump() for x in c.ai], {"q": q["question"], "choices": q.get("choices") or [], "a": None}])


def test_bank_question_fits_want():
    from app.question import agent, flow

    food = cond(basic={"want": "맛있는 것"})
    assert not flow.bank_fits_want(food, "sight") and flow.bank_fits_want(food, "walk") and flow.bank_fits_want(food, "budget")
    assert flow.bank_fits_want(cond(), "sight")  # 하고 싶은 것을 모르면 다 돼요
    # 에이전트가 맞지 않는 은행 질문(구경)을 내면 걸러요
    sight = flow.BANK["sight"]
    assert agent.bank_id_of("어떤 구경이 좋으세요?", ["궁 · 한옥", "시장 · 거리"]) == "sight"
    assert agent.check_question(food, [], {"question": sight["question"], "choices": sight["choices"]}) is None
    assert sight["question"] not in agent.look_bank(food, [])
    # 은행 질문으로 갈 때도 맞는 질문만
    items = flow.today_items(food) or []
    assert flow.best_bank(food, items) in (None, *flow.ANY_WANT, *flow.Q4_POOL["맛있는 것"])


def test_expanded_words_lead_rule_pick(monkeypatch):
    from app.data import filter_places as fp
    from app.llm import client as llm
    from app.recommend.wish import place_text

    s = loader.station_by_name("종로3가역")
    c = cond(origin={"id": s["id"], "name": s["name"], "type": "역"}, extra={"wish": ["공룡 구경"]},
             range={"oneWayMin": 45, "walk": "보통", "avoid": []})
    words = ["자연사", "화석", "과학관"]
    near = [x for x in fp.filter_places(c, config.now(), "맑음", []) if any(w in place_text(x["place"]) for w in words)]
    assert near  # 이 출발지 · 범위에 과학관이 있어야 이 시험이 뜻이 있어요

    async def fake(system, payload, schema, timeout, max_tokens=2000):
        if "picks" in schema["properties"]:
            return None  # AI 고르기는 실패 → 규칙으로
        return {"words": words, "places": []}

    monkeypatch.setattr(llm, "ask_json", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    j = client.post("/recommend", json={"conditions": c.model_dump(), "visited": []}).json()
    assert j["by"] == "rule" and j["expanded"]["words"] == words
    top = j["candidates"][0]["place"]["name"]
    assert any(w in top for w in words), top  # 넓힌 말(과학관)에 맞는 곳이 맨 앞


@pytest.mark.parametrize("text,bad", [
    ("이따 저녁에 우리 집 놀러 와요", True), ("제 집으로 오세요", True), ("집에 한번 놀러 와", True),
    ("돈 좀 빌려줄 수 있어요? 꼭 갚을게요", True), ("5만 원만 보내 주세요", True), ("계좌번호 알려 드릴게요", True),
    ("송금 좀 부탁해요", True),
    ("집에 가서 좀 쉬어야겠어요", False), ("우리 집 근처예요", False), ("돈 아끼려고 걸어왔어요", False),
    ("교통비가 많이 들어요", False), ("책 빌려 주세요", False), ("집이 어디세요? 저는 성수동이에요", False),
])
def test_chat_blocks_home_invite_and_money(text, bad):
    assert chat_safety.has_banned_word(text) is bad

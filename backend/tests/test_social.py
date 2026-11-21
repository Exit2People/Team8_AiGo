import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import chat_safety, config, db
from app.data import loader
from app.llm import jev
from app.main import app
from tests.fakedb import FakeDB

client = TestClient(app)
A = "client-aaaa"
B = "client-bbbb"


@pytest.fixture()
def fdb(monkeypatch):
    f = FakeDB()
    monkeypatch.setattr(db, "executor", f)
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    return f


def pid():
    return loader.places()[0]["id"]


def test_social_no_db_503():
    r = client.get(f"/places/{pid()}/social")
    assert r.status_code == 503 and r.json()["detail"] == "DB가 설정되지 않았어요"


def test_social_404(fdb):
    assert client.get("/places/NOPE/social").status_code == 404
    assert client.post("/chat/NOPE/join", json={"client": A, "nick": "봄"}).status_code == 404


def test_expect_once_per_device_and_cancel(fdb):
    p = pid()
    assert client.post(f"/places/{p}/expect", json={"client": A}).json() == {"expectedToday": 1}
    assert client.post(f"/places/{p}/expect", json={"client": A}).json() == {"expectedToday": 1}
    assert client.post(f"/places/{p}/expect", json={"client": B}).json() == {"expectedToday": 2}
    assert client.post(f"/places/{p}/expect/cancel", json={"client": A}).json() == {"expectedToday": 1}
    assert client.post(f"/places/{p}/expect", json={"client": "short"}).status_code == 422
    j = client.get(f"/places/{p}/social").json()
    assert j == {"expectedToday": 1, "reviewCount": 0, "topTags": []}


def test_reviews_paging(fdb):
    p = pid()
    for i in range(6):
        fdb.reviews.append({"id": i + 1, "place_id": p, "nick": "솔", "tag": "걷기 편해요" if i % 2 else "경치가 좋아요",
                            "body": f"글{i}", "created_at": datetime(2026, 11, 20, 10, i, tzinfo=config.KST)})
    j = client.get(f"/places/{p}/reviews", params={"page": 9}).json()
    assert j["total"] == 6 and j["pages"] == 2 and j["page"] == 2 and len(j["items"]) == 2
    first = client.get(f"/places/{p}/reviews").json()
    assert first["items"][0]["text"] == "글5" and first["items"][0]["date"] == "11.20" and first["items"][0]["id"] == "6"
    assert client.get(f"/places/{p}/social").json()["topTags"] == [["걷기 편해요", 3], ["경치가 좋아요", 3]]
    empty = client.get("/places/" + loader.places()[1]["id"] + "/reviews").json()
    assert empty == {"total": 0, "page": 1, "pages": 1, "items": []}


def test_chat_join_nick_and_messages(fdb):
    p = pid()
    j = client.post(f"/chat/{p}/join", json={"client": A, "nick": "봄나들이"}).json()
    assert j["nick"] == "봄나들이" and j["joined"] and j["count"] == 1
    assert j["messages"][-1]["kind"] == "system" and j["messages"][-1]["text"] == "봄나들이 님이 들어왔어요"
    assert j["expiresAt"] == "2026-11-22T00:00:00+09:00"
    j2 = client.post(f"/chat/{p}/join", json={"client": B, "nick": "봄나들이"}).json()
    assert j2["nick"] == "봄나들이2"
    again = client.post(f"/chat/{p}/join", json={"client": A, "nick": "다른이름"}).json()
    assert again["nick"] == "봄나들이"
    r = client.post(f"/chat/{p}/messages", json={"client": A, "text": "반가워요"}).json()
    assert r["kind"] == "quick" and r["mine"] is True
    r = client.post(f"/chat/{p}/messages", json={"client": A, "text": "제 번호는 010-1234-5678 이에요"}).json()
    assert r["text"] == "제 번호는 (전화번호는 가렸어요) 이에요"
    st = client.get(f"/chat/{p}", params={"client": B, "after": 0}).json()
    assert [m["mine"] for m in st["messages"] if m["kind"] != "system"] == [False, False]
    last = st["messages"][-1]["id"]
    assert client.get(f"/chat/{p}", params={"client": B, "after": last}).json()["messages"] == []


def test_chat_send_rules(fdb):
    p = pid()
    assert client.post(f"/chat/{p}/messages", json={"client": A, "text": "안녕"}).status_code == 403
    client.post(f"/chat/{p}/join", json={"client": A, "nick": "솔바람"})
    r = client.post(f"/chat/{p}/messages", json={"client": A, "text": "   "})
    assert r.status_code == 400 and r.json()["detail"] == "보낼 글이 없어요"
    r = client.post(f"/chat/{p}/messages", json={"client": A, "text": "여기 보세요 www.abc.kr"})
    assert r.status_code == 400 and r.json()["detail"] == "링크는 보낼 수 없어요"
    r = client.post(f"/chat/{p}/messages", json={"client": A, "text": "씨1발"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "blocked"
    assert client.post(f"/chat/{p}/messages", json={"client": A, "text": "가" * 201}).status_code == 422


def test_chat_split_message_blocked(fdb):
    p = pid()
    client.post(f"/chat/{p}/join", json={"client": A, "nick": "솔바람"})
    assert client.post(f"/chat/{p}/messages", json={"client": A, "text": "씨"}).status_code == 200
    assert client.post(f"/chat/{p}/messages", json={"client": A, "text": "발"}).status_code == 400


def test_chat_leave_report_and_next_day(fdb, monkeypatch):
    p = pid()
    client.post(f"/chat/{p}/join", json={"client": A, "nick": "솔바람"})
    client.post(f"/chat/{p}/join", json={"client": B, "nick": "꽃마중"})
    assert client.post(f"/chat/{p}/report", json={"client": "client-zzzz", "target": "꽃마중"}).status_code == 403
    assert client.post(f"/chat/{p}/report", json={"client": A, "target": "꽃마중"}).json() == {"ok": True}
    assert fdb.reports[0] == {"day": config.now().date(), "place_id": p, "target_nick": "꽃마중"}
    assert client.post(f"/chat/{p}/leave", json={"client": B}).json() == {"ok": True}
    st = client.get(f"/chat/{p}", params={"client": A}).json()
    assert st["members"] == ["솔바람"] and st["messages"][-1]["text"] == "꽃마중 님이 나갔어요"
    monkeypatch.setenv("AIGO_NOW", "2026-11-22T09:00")
    j = client.post(f"/chat/{p}/join", json={"client": B, "nick": "꽃마중"}).json()
    assert j["members"] == ["꽃마중"] and all(m["text"] != "솔바람 님이 들어왔어요" for m in j["messages"])
    assert fdb.reports == []


@pytest.mark.parametrize("text", ["씨발", "씨 발", "ㅅㅂ", "tlqkf", "병1신", "시.발", "18놈", "fuck", "f u c k", "fvck",
                                  "몸매가 좋으시네요", "술 한잔 하러 가요", "따로 만나요", "번호 좀 알려주세요", "카톡 아이디 알려줘",
                                  "투표하세요", "2번 찍어야 해요", "씨8", "개18", "뷰1지", "ㅗ", "야스", "국힘 싫어요"])
def test_safety_blocks(text):
    assert chat_safety.has_banned_word(text), text


@pytest.mark.parametrize("text", ["반가워요 오늘 날씨 좋네요", "18번 출구로 나오세요", "시발점에서 만나요", "몇 번 출구예요?",
                                  "버스 번호 알려주세요", "따로 앉을게요", "사진 찍어 주세요", "바보같이 길을 잃었어요",
                                  "막걸리 축제 포스터 봤어요", "4시8분에 도착해요", "hello everyone", "1시 8분이에요",
                                  "투표하고 왔어요", "개 18마리 봤어요", "Dickens 책 좋아해요", "야스쿠니 뉴스 봤어요"])
def test_safety_passes(text):
    assert not chat_safety.has_banned_word(text), text


def test_safety_clean_fullwidth_invisible():
    assert chat_safety.clean("ｆｕｃｋ") == "fuck"
    assert chat_safety.has_banned_word("씨​발")


def test_keyboard_to_korean():
    assert chat_safety.ko_from_keys("tlqkf") == "시발"
    assert chat_safety.ko_from_keys("dkssud") == "안녕"


def test_safety_jev(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    seen = {}

    async def fake(state, qs, timeout):
        seen["qs"] = set(qs)
        seen["state"] = state
        return {k: 0.5 for k in qs}

    monkeypatch.setattr(jev, "ask_many", fake)
    assert asyncio.run(chat_safety.is_blocked("시발점 마약김밥 먹어요"))
    assert seen["qs"] == {"msg"} and seen["state"]["채팅 글"] == "출발점 꼬마김밥 먹어요"
    assert asyncio.run(chat_safety.is_blocked("어디요", ["안녕"], ["하이"]))
    assert seen["qs"] == {"msg", "ctx"} and seen["state"]["새 글"] == "어디요"

    async def low(state, qs, timeout):
        return {k: 0.2 for k in qs}

    monkeypatch.setattr(jev, "ask_many", low)
    assert not asyncio.run(chat_safety.is_blocked("평범한 말"))

    async def fail(state, qs, timeout):
        return None

    monkeypatch.setattr(jev, "ask_many", fail)
    assert not asyncio.run(chat_safety.is_blocked("평범한 말"))
    monkeypatch.setenv("AIGO_CHAT_JEV", "0")
    monkeypatch.setattr(jev, "ask_many", fake)
    assert not asyncio.run(chat_safety.is_blocked("평범한 말"))

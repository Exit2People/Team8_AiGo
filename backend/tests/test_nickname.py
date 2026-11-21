import asyncio

import pytest

from app import config, nickname
from app.llm import jev
from tests.test_auth import _callback, c, fdb  # noqa: F401 (픽스처를 함께 써요)

BAD = {
    "씨발이": "욕설", "미친놈": "욕설", "tlqkf": "욕설", "시1발": "욕설", "18놈": "욕설", "ㅅㅂ맨": "욕설", "시발점": "욕설",
    "섹스왕": "성적", "sexyboy": "성적",
    "대마초": "범죄", "불법도박": "범죄",
    "국힘사랑": "정치", "좌파": "정치",
    "ㅋㅋ": "jamo", "하ㅏ": "jamo",
    "꽃🌸": "emoji", "봄 바람": "symbol", "봄!": "symbol", "a": "length", "가나다라마바사아자": "length", "12345": "digits",
    "운영자": "staff", "admin1": "staff", "": "empty",
}
GOOD = ["봄나들이", "솔바람7", "개나리", "한강", "보리", "장미꽃", "고추", "Grace", "시바견"]


@pytest.mark.parametrize("nick,code", BAD.items())
def test_rules_block_with_reason(nick, code):
    hit = nickname.check_rules(nick)
    assert hit is not None and hit[0] == code and hit[1] == nickname.MSG[code]


@pytest.mark.parametrize("nick", GOOD)
def test_rules_pass_everyday_names(nick):
    assert nickname.check_rules(nick) is None


def test_messages_tell_the_reason():
    assert nickname.MSG["욕설"] == "욕설이나 비방이 감지되어 사용할 수 없는 닉네임이에요"
    assert nickname.MSG["jamo"].startswith("완전한 단어로 닉네임을 설정해 주세요")


def test_jev_second_layer(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    calls = []

    async def high(state, qs, timeout):
        calls.append(state)
        return {k: 0.9 for k in qs}

    monkeypatch.setattr(jev, "ask_many", high)
    assert asyncio.run(nickname.check("봄나들이")) == ("jev", nickname.MSG["jev"])
    calls.clear()
    assert asyncio.run(nickname.check("씨발이"))[0] == "욕설" and calls == []  # 규칙에 걸리면 Jev 안 불러요

    async def low(state, qs, timeout):
        return {k: 0.2 for k in qs}

    monkeypatch.setattr(jev, "ask_many", low)
    assert asyncio.run(nickname.check("봄나들이")) is None

    async def fail(state, qs, timeout):
        return None

    monkeypatch.setattr(jev, "ask_many", fail)
    assert asyncio.run(nickname.check("봄나들이")) is None  # 실패하면 규칙 결과만

    monkeypatch.setattr(jev, "ask_many", high)
    monkeypatch.setenv("AIGO_NICK_JEV", "0")
    assert not config.nickname_jev_on() and asyncio.run(nickname.check("봄나들이")) is None


def test_check_api(c):
    j = c.post("/auth/nickname/check", json={"nickname": "ㅅㅂ맨"}).json()
    assert j == {"ok": False, "reason": "욕설", "message": nickname.MSG["욕설"]}
    assert c.post("/auth/nickname/check", json={"nickname": "봄나들이"}).json()["ok"] is True


def test_profile_rejects_bad_nickname(c, fdb, monkeypatch):
    fdb.add_user(kakao_id="123")
    _callback(c, monkeypatch)
    r = c.patch("/auth/profile", json={"nickname": "섹스왕"})
    assert r.status_code == 400 and r.json()["detail"] == nickname.MSG["성적"]
    r = c.patch("/auth/profile", json={"nickname": "봄🌸"})
    assert r.status_code == 400 and r.json()["detail"] == nickname.MSG["emoji"]
    assert c.patch("/auth/profile", json={"nickname": "봄나들이"}).json()["nickname"] == "봄나들이"
    assert c.patch("/auth/profile", json={"nickname": ""}).json()["nickname"] == ""


def test_chat_join_bad_nick_becomes_guest(monkeypatch):
    from fastapi.testclient import TestClient

    from app import db
    from app.data import loader
    from app.main import app
    from tests.fakedb import FakeDB

    monkeypatch.setattr(db, "executor", FakeDB())
    monkeypatch.setenv("AIGO_NOW", "2026-11-21T11:00")
    cl = TestClient(app)
    p = loader.places()[0]["id"]
    assert cl.post(f"/chat/{p}/join", json={"client": "client-aaaa", "nick": "씨발이"}).json()["nick"] == "손님"
    assert cl.post(f"/chat/{p}/join", json={"client": "client-bbbb", "nick": "봄나들이"}).json()["nick"] == "봄나들이"

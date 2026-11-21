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
    # korcen이 잡아 주는 것 · 닉네임 전용 낮춤말
    "고추": "성적", "고추왕": "성적", "큰고추": "성적", "고추장고추": "성적", "보지털": "성적", "자지왕": "성적", "개년": "욕설", "등신": "욕설", "찐따": "욕설", "애미": "욕설",
}
GOOD = ["봄나들이", "솔바람7", "개나리", "한강", "보리", "장미꽃", "고추잠자리", "청양고추", "고추장", "풋고추", "Grace", "시바견", "섹션", "대한민국", "산책왕"]


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


def test_works_without_korcen(monkeypatch):
    # korcen을 못 불러와도 우리 사전 · Jev로 그대로 돌아가요
    monkeypatch.setattr(nickname, "_KORCEN", [None])
    assert nickname.check_rules("씨발이")[0] == "욕설" and nickname.check_rules("봄나들이") is None
    assert nickname.check_rules("보지털")[0] == "성적"  # 닉네임 은어 표가 korcen 없이도 잡아요


# 평범한 닉네임 · 어르신 세대 이름 · 동네 · 꽃 이름 (은어와 글자가 겹쳐도 통과해야 해요)
EVERYDAY = ["살인미소", '봄나들이', '솔바람', '개나리', '한강', '보리', '장미꽃', '고추잠자리', '청양고추', '시바견', '수도꼭지', '젖소농장', '섹션', '떡볶이', '찹쌀떡', '떡국', '김애자', '박아름', '이정자', '최순자', '김말순', '박영희', '이철수', '정미숙', '강애순', '오복례', '한송이', '김보람', '이자영', '박지민', '이미진', '산책왕', '등산러', '꽃분이', '바다사랑', '새벽별', '하늘빛', '동네친구', '손주바보', '은빛여우', '무지개', '호로록', '새끼고양이', '강아지', '고양이', '토토로', '마약김밥', '색소폰', '한라산', '북한산', '남산', '청계천', '광화문', '경복궁', '덕수궁', '인왕산', '성수동', '왕십리', '대한민국', '서울시민', '할머니', '할아버지', '행복이', '사랑이', '복덩이', '꿀벌', '게이트볼', '게이지', '대포항', '미친듯', '꼭짓점', '정액제', '젖병', '호모사피엔스', '후레쉬', 'Grace', 'Tom', 'Anna', 'Mary', 'John', 'peace', 'hello', 'happy', 'sunny', '산들바람', '오솔길', '들국화', '해바라기', '코스모스', '진달래', '철쭉', '목련', '매화', '벚꽃', '단비', '소나기', '눈꽃', '노을빛', '은하수', '달빛', '별님', '해님']
ADJ = ["포근한", "씩씩한", "느긋한", "상냥한", "다정한", "산뜻한", "든든한", "명랑한", "향긋한", "말랑한"]
NOUN = ["햇살", "솔잎", "바람", "구름", "꽃잎", "나비", "들꽃", "단풍", "노을", "산새", "물결", "별빛"]
# 성적 · 욕설 · 비하 · 범죄 · 정치 은어 (숫자 끼우기 · 한영 키 오타 포함)
SLANG = ['고추', '꼬추', '고추왕', '큰고추', '보지털', '자지왕', '젖가슴', '빨통', '섹시녀', '쎅시', '야동왕', '변태', '꼴리네', '정액', '딸딸이', '육변기', '걸레', '창녀', '원나잇', '섹파', '69', '병신', '븅딱', '등신', '찐따', '지랄', '미친놈', '또라이', '돌아이', '개새', '개색기', '개년', '개같은', '썅년', '닥쳐', '꺼져', '뒤져라', '애미', '애비', '니미', '느금', '존나', '졸라', '좆밥', '새끼', '싸가지', '양아치', '한남충', '한녀', '김치녀', '된장녀', '틀딱', '노인네', '늙다리', '꼰대', '홍어', '쪽바리', '짱깨', '깜둥이', '장애인', '정신병자', '잼민이', '개독', '마약왕', '대마초', '필로폰', '도박왕', '토토', '카지노', '사기꾼', '살인마', '강간', '몰카', '조폭', '깡패', '일베', '메갈', '워마드', '대깨문', '개딸', '빨갱이', '좌파', '우파', '극우', '국힘', '민주당', '대통령', 'rhcn', 'tlqkf', '고1추', '병1신', 'sexy', 'fuck']


def test_everyday_nicknames_pass():
    names = EVERYDAY + [a + n + "27" for a in ADJ for n in NOUN]  # 가입 때 지어 주는 이름까지
    assert [x for x in names if nickname.check_rules(x)] == []


def test_slang_nicknames_blocked():
    assert [x for x in SLANG if not nickname.check_rules(x)] == []


@pytest.mark.parametrize("nick,code", {"노인네": "비하", "장애인": "비하", "잼민이": "비하", "꼴리네": "성적", "섹시녀": "성적",
                                        "도박왕": "범죄", "몰카": "범죄", "대통령": "정치", "일베": "정치", "싸가지": "욕설", "한남충": "비하", "김치녀": "비하", "틀딱": "비하"}.items())
def test_slang_reason_group(nick, code):
    assert nickname.check_rules(nick)[0] == code


def test_reason_from_chat_slang_group():
    # 톡방 은어 표에만 있는 말도 그 갈래로 이유를 알려요 (작대기 · 떨액 = 마약 은어 → 범죄)
    assert nickname.check_rules("작대기왕")[0] == "범죄"
    assert nickname.check_rules("떨액")[0] == "범죄"
    assert nickname.check_rules("쪽바리")[0] == "비하"


def test_flat_rate_words_pass_like_chat():
    # 톡방에서 예외인 요금 말은 닉네임에서도 통과해요
    assert nickname.check_rules("정액권") is None
    assert nickname.check_rules("정액") is not None

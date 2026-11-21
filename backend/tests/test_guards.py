import asyncio

from app.guards import scrub_pii
from app.question import opening
from app.schemas import Conditions


def test_scrub_pii():
    out = scrub_pii("010-1234-5678 로 전화 주세요. 집은 왕십리로 123 이고 메일은 a.b@test.com")
    assert "1234" not in out and "test.com" not in out and "123" not in out
    assert scrub_pii(None) is None
    assert scrub_pii("") == ""
    assert scrub_pii("010-1234-5678로 연락") == "[지움]로 연락"
    assert scrub_pii("세종대로 110") == "[지움]"
    assert scrub_pii("02-123-4567 이에요") == "[지움] 이에요"
    assert scrub_pii("900101-1234567") == "[지움]"


def test_everyday_words_stay():
    for t in ["한강 가서 바람 쐬고 싶어요", "3시간쯤 걷고 싶어요", "2번 출구 앞", "손주랑 사진 찍기", "종로3가역 쪽", "을지로 3가 시장"]:
        assert scrub_pii(t) == t


def test_open_text_is_scrubbed_before_ai(monkeypatch):
    sent = {}

    async def fake_ask(system, payload, schema, timeout):
        sent.update(payload)
        return None

    monkeypatch.setattr("app.llm.client.ask_json", fake_ask)
    c = Conditions.model_validate({"origin": {"id": "SM-0150", "name": "서울역", "type": "역"},
                                   "range": {"oneWayMin": 60, "walk": "보통", "avoid": []}})
    asyncio.run(opening.parse_open(c, "010-1234-5678 손주랑 서울숲 가고 싶어요"))
    assert "1234" not in sent["어르신의 말"] and "서울숲" in sent["어르신의 말"]

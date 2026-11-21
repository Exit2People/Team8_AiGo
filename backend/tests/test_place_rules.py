"""09_ACCEPTANCE 3.3 (모집 · 아이 전용 · 위치 어긋남) · 3.10 (손주)."""

from app.data import filter_places as fp
from app.data import loader
from app.recommend.wish import matches_who


def ev(name: str, target: str, venue: str = "") -> dict:
    return {"kind": "행사", "name": name, "event": {"target": target, "venue": venue}}


def test_recruit_and_kids_only_events_are_dropped():
    assert not fp.for_seniors(ev("시민 강사 모집", "누구나"))
    assert not fp.for_seniors(ev("[어린이박물관] 나무공예", "성인 보호자를 동반한 연나이 3~9세 어린이"))
    assert not fp.for_seniors(ev("[도서관] 어린이열람실 북큐레이션", "어린이열람실 이용자 누구나"))
    assert not fp.for_seniors(ev("아기 놀이", "36개월 미만 영아, 보호자"))
    assert not fp.for_seniors(ev("과학 교실", "초등학생"))
    assert not fp.for_seniors(ev("체험", "5~7세 유아와 보호자"))


def test_events_open_to_adults_stay():
    assert fp.for_seniors(ev("개인전", "누구나(단, 어린이는 보호자 동반 시 가능)"))
    assert fp.for_seniors(ev("[어린이박물관] 특별전시", "어린이를 동반한 전 연령"))
    assert fp.for_seniors(ev("음악회", "성인"))
    assert fp.for_seniors({"kind": "공원", "name": "어린이대공원"})


def test_snapshot_kids_only_events_are_dropped():
    ids = {p["id"] for p in loader.places() if not fp.for_seniors(p)}
    assert {"SE160085", "SE160066"} <= ids


def test_wrong_place():
    d = loader.districts()[0]
    dong = d["dongs"][0]
    assert not fp.wrong_place({"gu": d["gu"], "lat": dong["lat"], "lng": dong["lng"]})
    assert fp.wrong_place({"gu": d["gu"], "lat": 33.45, "lng": 126.57})  # 제주
    assert not fp.wrong_place({"gu": "과천시", "lat": 33.45, "lng": 126.57})  # 자료에 없는 구는 판단 안 함
    assert not any(fp.wrong_place(p) for p in loader.places())


def test_grandchild_matches_real_places():
    ps = loader.places()
    hit = [p for p in ps if matches_who(p, "손주")]
    assert hit, "손주와 맞는 장소가 스냅숏에 있어야 해요"
    assert any(p.get("kind") in ("공원", "한강공원") for p in hit)
    assert not matches_who({"mood": ["시장"]}, "손주")
    assert not matches_who({"mood": ["산책"]}, None)

from fastapi.testclient import TestClient

from app.data import geo, loader
from app.main import app
from app.schemas import Conditions, strip_for_ai

client = TestClient(app)


def test_health_without_db():
    j = client.get("/health").json()
    assert j["ok"] is True and j["ai"] is False and j["weather"] == "맑음"
    assert len(j["now"]) == 16


def test_districts_25():
    r = client.get("/districts")
    assert r.status_code == 200
    gus = r.json()
    assert len(gus) == 25 and gus == sorted(gus) and "성동구" in gus


def test_dongs_and_404():
    r = client.get("/districts/성동구/dongs")
    assert r.status_code == 200
    assert any(d["name"].startswith("성수") for d in r.json())
    assert set(r.json()[0]) == {"id", "name"}
    r = client.get("/districts/없는구/dongs")
    assert r.status_code == 404 and r.json()["detail"] == "구를 찾을 수 없어요"


def test_nearby_post_only():
    r = client.post("/stations/nearby", json={"lat": 37.5446, "lng": 127.0446})
    j = r.json()
    assert r.status_code == 200 and j["radiusKm"] == 2.0 and not j["widened"]
    assert 1 <= len(j["stations"]) <= 4
    assert j["stations"][0]["name"] == "서울숲역"
    s = j["stations"][0]
    assert s["distanceM"] % 10 == 0 and s["walkMin"] >= 1
    d = [x["distanceM"] for x in j["stations"]]
    assert d == sorted(d)
    # 좌표가 주소(접근 로그)에 남지 않게 GET은 두지 않아요
    assert client.get("/stations/nearby", params={"lat": 37.5446, "lng": 127.0446}).status_code == 405


def test_nearby_widen_and_empty():
    far = client.post("/stations/nearby", json={"lat": 33.5, "lng": 126.5}).json()
    assert far == {"radiusKm": 5.0, "widened": True, "stations": []}


def test_transfer_station_grouped():
    names = [s["name"] for s in loader.stations()]
    assert len(names) == len(set(names))
    seoul = loader.station_by_name("서울역")
    assert "1호선" in seoul["lines"] and "4호선" in seoul["lines"]


def test_group_merges_lines():
    rows = [
        {"id": "A", "name": "왕십리역", "lat": 37.0, "lng": 127.0, "lines": ["2호선"]},
        {"id": "B", "name": "왕십리역", "lat": 37.002, "lng": 127.002, "lines": ["5호선"]},
    ]
    out = loader._group_stations(rows)
    assert len(out) == 1 and out[0]["lines"] == ["2호선", "5호선"] and out[0]["lat"] == 37.001


def test_dong_stations():
    gu = client.get("/districts/성동구/dongs").json()
    r = client.get(f"/dongs/{gu[0]['id']}/stations")
    assert r.status_code == 200 and r.json()["stations"]
    assert client.get("/dongs/0000/stations").status_code == 404


def test_walk_minutes():
    assert geo.walk_minutes(0) == 1
    assert geo.walk_minutes(670) == 13  # 670 × 1.3 ÷ 67 = 13


def test_strip_for_ai_no_coords():
    c = Conditions(origin={"id": "1", "name": "성수1가1동", "type": "동", "lat": 37.5, "lng": 127.0},
                   freeText="비밀", extra={"place": "한강", "who": "손주"})
    s = strip_for_ai(c)
    text = str(s)
    assert "37.5" not in text and "비밀" not in text
    assert s["출발역"] == "성수1가1동" and s["가고 싶은 곳"] == "한강" and s["같이 가는 사람"] == "손주"


def test_data_status_reads_snapshot():
    j = client.get("/data/status").json()
    assert j["db"] == "snapshot" and j["fetchedAt"].startswith("2026-11-18")


def test_places_loaded():
    assert len(loader.places()) == 650


def test_db_api_503_without_url():
    from fastapi import HTTPException

    from app import db

    try:
        db.run("select 1")
    except HTTPException as e:
        assert e.status_code == 503 and e.detail == "DB가 설정되지 않았어요"
    else:
        raise AssertionError("503이어야 해요")


def test_maps_config_without_key():
    assert client.get("/maps/config").json() == {"enabled": False, "sdkUrl": None}


def test_places_search_no_key_503():
    r = client.get("/places/search", params={"query": "서울숲"})
    assert r.status_code == 503

from datetime import datetime, timedelta

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.routers import auth
from tests.fakedb import FakeAuthDB


@pytest.fixture()
def fdb(monkeypatch):
    f = FakeAuthDB()
    monkeypatch.setattr(db, "executor", f)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("AIGO_SESSION_SECRET", "test-secret")
    return f


def login(fdb, **kw):
    u = fdb.add_user(**kw)
    r = Response()
    auth.new_session(r, u["id"])
    c = TestClient(app)
    c.cookies.set("aigo_sid", r.headers["set-cookie"].split("aigo_sid=")[1].split(";")[0])
    return c, u


def test_guest_cannot_post(fdb):
    r = TestClient(app).post("/game/scores", json={"steps": 10})
    assert r.status_code == 401 and r.json()["detail"] == "로그인하면 랭킹에 올라가요"


def test_steps_range(fdb):
    c, _ = login(fdb, nickname="a")
    assert c.post("/game/scores", json={"steps": -1}).status_code == 422
    assert c.post("/game/scores", json={"steps": 1000000}).status_code == 422


def test_best_kept(fdb):
    c, u = login(fdb, nickname="솔바람")
    assert c.post("/game/scores", json={"steps": 100}).json() == {"rank": 1, "best": 100, "isBest": True}
    assert c.post("/game/scores", json={"steps": 50}).json() == {"rank": 1, "best": 100, "isBest": False}
    assert c.post("/game/scores", json={"steps": 150}).json()["best"] == 150


def test_ranking_guest_and_member(fdb):
    now = datetime.now(config.KST)
    a = fdb.add_user(nickname="가")
    b = fdb.add_user(nickname=None)
    banned = fdb.add_user(nickname="밴", banned_at=now)
    fdb.scores[a["id"]] = {"steps": 300, "achieved_at": now - timedelta(minutes=5)}
    fdb.scores[b["id"]] = {"steps": 300, "achieved_at": now}
    fdb.scores[banned["id"]] = {"steps": 999, "achieved_at": now}
    j = TestClient(app).get("/game/ranking").json()
    assert [e["nickname"] for e in j["top"]] == ["가", "이름 없는 회원"] and j["me"] is None and j["total"] == 2
    assert "user_id" not in str(j) and a["id"] not in str(j)
    c, me = login(fdb, nickname="나")
    c.post("/game/scores", json={"steps": 300})
    j = c.get("/game/ranking", params={"limit": 2}).json()
    assert len(j["top"]) == 2 and j["me"]["rank"] == 3 and j["me"]["entry"]["mine"] is True
    assert c.get("/game/ranking", params={"limit": 51}).status_code == 422
    assert c.get("/game/ranking", params={"limit": 0}).status_code == 422

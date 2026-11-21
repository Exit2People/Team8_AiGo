from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.routers import auth
from tests.fakedb import FakeAuthDB
from tests.test_auth import _callback


@pytest.fixture()
def fdb(monkeypatch):
    f = FakeAuthDB()
    monkeypatch.setattr(db, "executor", f)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("AIGO_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "kakao-test")
    monkeypatch.setenv("AIGO_PUBLIC_URL", "https://fe.example")
    return f


@pytest.fixture()
def c(fdb):
    return TestClient(app, base_url="https://fe.example")


def login_kakao(c, fdb, monkeypatch, kid="123", **kw):
    u = fdb.add_user(kakao_id=kid, **kw)
    assert _callback(c, monkeypatch, kid).headers["location"] == "/?login=ok"
    return u


def test_delete_needs_login(c):
    assert c.delete("/auth/account").status_code == 401


def test_delete_kakao_unlinks_and_soft_deletes(c, fdb, monkeypatch):
    monkeypatch.setenv("KAKAO_ADMIN_KEY", "admin")
    calls = []
    monkeypatch.setattr(httpx, "post", lambda url, **kw: calls.append((url, kw["data"])) or httpx.Response(200))
    u = login_kakao(c, fdb, monkeypatch)
    fdb.scores[u["id"]] = {"steps": 10}
    r = c.delete("/auth/account")
    assert r.status_code == 204 and "aigo_relogin=1" in r.headers["set-cookie"]
    assert calls[0][0] == auth.KAKAO_UNLINK and calls[0][1]["target_id"] == "123"
    row = fdb.users[u["id"]]
    assert row["deleted_at"] and (row["purge_after"] - row["deleted_at"]).days == 90
    assert fdb.sessions == {} and u["id"] not in fdb.scores
    assert c.get("/auth/me").json()["loggedIn"] is False


@pytest.mark.parametrize("mode", ["nokey", "http", "conn"])
def test_delete_continues_when_unlink_fails(c, fdb, monkeypatch, mode):
    if mode != "nokey":
        monkeypatch.setenv("KAKAO_ADMIN_KEY", "admin")

    def bad(url, **kw):
        if mode == "conn":
            raise httpx.ConnectError("x")
        return httpx.Response(500)

    monkeypatch.setattr(httpx, "post", bad)
    login_kakao(c, fdb, monkeypatch)
    assert c.delete("/auth/account").status_code == 204


def test_email_user_no_unlink(c, fdb, monkeypatch):
    monkeypatch.setenv("KAKAO_ADMIN_KEY", "admin")
    calls = []
    monkeypatch.setattr(httpx, "post", lambda url, **kw: calls.append(url) or httpx.Response(200))
    u = fdb.add_user(email="a@b.co")
    from fastapi import Response

    r = Response()
    auth.new_session(r, u["id"])
    token = r.headers["set-cookie"].split("aigo_sid=")[1].split(";")[0]
    c.cookies.set("aigo_sid", token)
    d = c.delete("/auth/account")
    assert d.status_code == 204 and calls == [] and "aigo_relogin=1" not in d.headers.get("set-cookie", "")


def test_session_ignores_deleted_and_banned(c, fdb, monkeypatch):
    u = login_kakao(c, fdb, monkeypatch)
    assert c.get("/auth/me").json()["loggedIn"]
    fdb.users[u["id"]]["banned_at"] = datetime.now(config.KST)
    assert c.get("/auth/me").json()["loggedIn"] is False


def test_restore_needs_cookie(c):
    assert c.get("/auth/restore").status_code == 401
    assert c.post("/auth/restore", json={"choice": "restore"}).status_code == 401
    assert c.post("/auth/restore", json={"choice": "other"}).status_code == 422


def _deleted_kakao(c, fdb, monkeypatch, **kw):
    now = datetime.now(config.KST)
    u = fdb.add_user(kakao_id="d1", nickname="솔바람", deleted_at=now, purge_after=now + timedelta(days=90), **kw)
    r = _callback(c, monkeypatch, "d1")
    assert r.headers["location"] == "/?restore=1"
    return u


def test_restore_flow(c, fdb, monkeypatch):
    u = _deleted_kakao(c, fdb, monkeypatch)
    j = c.get("/auth/restore").json()
    assert j["pending"] and j["provider"] == "kakao" and j["nickname"] == "솔바람" and len(j["purgeAfter"]) == 10
    j = c.post("/auth/restore", json={"choice": "restore"}).json()
    assert j == {"restored": True, "id": u["id"], "provider": "kakao"}
    assert fdb.users[u["id"]]["deleted_at"] is None
    assert c.get("/auth/me").json()["loggedIn"] is True


def test_restore_fresh_deletes(c, fdb, monkeypatch):
    u = _deleted_kakao(c, fdb, monkeypatch)
    j = c.post("/auth/restore", json={"choice": "fresh"}).json()
    assert j["restored"] is False and u["id"] not in fdb.users
    assert c.get("/auth/me").json()["signupPending"] is True
    assert c.post("/auth/signup", json={"agree": True}).status_code == 204


def test_restore_banned_403(c, fdb, monkeypatch):
    u = _deleted_kakao(c, fdb, monkeypatch)
    fdb.users[u["id"]]["banned_at"] = datetime.now(config.KST)
    assert c.get("/auth/restore").status_code == 403


def test_purge_expired_before_lookup(c, fdb, monkeypatch):
    old = datetime.now(config.KST) - timedelta(days=100)
    u = fdb.add_user(kakao_id="old", deleted_at=old, purge_after=old + timedelta(days=90))
    r = _callback(c, monkeypatch, "old")
    assert r.headers["location"] == "/?signup=1" and u["id"] not in fdb.users

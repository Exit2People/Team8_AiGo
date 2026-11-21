from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.routers import auth
from tests.fakedb import FakeAuthDB


@pytest.fixture()
def fdb(monkeypatch):
    f = FakeAuthDB()
    monkeypatch.setattr(db, "executor", f)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")  # configured() 만 참으로 (실제로 붙지 않아요)
    monkeypatch.setenv("AIGO_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "kakao-test")
    monkeypatch.setenv("AIGO_PUBLIC_URL", "https://fe.example")
    return f


@pytest.fixture()
def c(fdb):
    return TestClient(app, base_url="https://fe.example")


def start(c):
    r = c.get("/auth/kakao/start", follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    return r, q


def test_sign_roundtrip(fdb):
    t = auth.sign("abc", 60)
    assert auth.unsign(t) == "abc"
    assert auth.unsign(t[:-1] + ("0" if t[-1] != "0" else "1")) is None
    assert auth.unsign(auth.sign("abc", -1)) is None


def test_kakao_start_without_key_503(monkeypatch):
    monkeypatch.setenv("AIGO_SESSION_SECRET", "x")
    r = TestClient(app).get("/auth/kakao/start", follow_redirects=False)
    assert r.status_code == 503 and r.json()["detail"] == "카카오 로그인 설정이 아직 안 됐어요"


def test_kakao_start_params_and_relogin(c):
    r, q = start(c)
    assert q["redirect_uri"] == ["https://fe.example/api/auth/kakao/callback"]
    assert q["response_type"] == ["code"] and "prompt" not in q and "scope" not in q
    sc = r.headers["set-cookie"]
    assert "aigo_state=" in sc and "HttpOnly" in sc and "Secure" in sc and "samesite=lax" in sc.lower()
    c.cookies.set("aigo_relogin", "1")
    _, q2 = start(c)
    assert q2["prompt"] == ["login"]


def test_callback_bad_state_fails(c, monkeypatch):
    monkeypatch.setattr(auth, "kakao_user_id", lambda code: "123")
    start(c)
    r = c.get("/auth/kakao/callback", params={"code": "x", "state": "wrong"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/?login=fail"


def _callback(c, monkeypatch, kid="123"):
    monkeypatch.setattr(auth, "kakao_user_id", lambda code: kid)
    _, q = start(c)
    return c.get("/auth/kakao/callback", params={"code": "x", "state": q["state"][0]}, follow_redirects=False)


def test_new_user_signup_flow(c, fdb, monkeypatch):
    c.cookies.set("aigo_relogin", "1")
    r = _callback(c, monkeypatch)
    assert r.headers["location"] == "/?signup=1"
    assert 'aigo_relogin=""' in r.headers["set-cookie"] or "aigo_relogin=;" in r.headers["set-cookie"]
    assert c.get("/auth/me").json() == {"loggedIn": False, "signupPending": True, "restorePending": False}
    assert c.post("/auth/signup", json={"agree": False}).status_code == 400
    assert c.post("/auth/signup", json={"agree": True, "homeDong1": "없는구 없는동"}).status_code == 400
    r = c.post("/auth/signup", json={"agree": True, "homeDong1": "성동구 성수1가1동"})
    assert r.status_code == 204
    me = c.get("/auth/me").json()
    assert me["loggedIn"] and me["provider"] == "kakao" and me["homeDong1"] == "성동구 성수1가1동"
    assert len(fdb.consents) == 2 and {x["doc_version"] for x in fdb.consents} == {"2026-11-20"}
    assert all(len(k) == 64 for k in fdb.sessions)  # 토큰이 아니라 해시만


def test_existing_user_login_and_logout(c, fdb, monkeypatch):
    fdb.add_user(kakao_id="123", nickname="솔바람")
    r = _callback(c, monkeypatch)
    assert r.headers["location"] == "/?login=ok"
    assert c.get("/auth/me").json()["nickname"] == "솔바람"
    assert c.post("/auth/logout").status_code == 204
    assert c.get("/auth/me").json()["loggedIn"] is False and fdb.sessions == {}


def test_banned_and_deleted_branches(c, fdb, monkeypatch):
    from datetime import datetime, timedelta

    from app import config

    now = datetime.now(config.KST)
    fdb.add_user(kakao_id="b1", banned_at=now)
    assert _callback(c, monkeypatch, "b1").headers["location"] == "/?login=banned"
    fdb.add_user(kakao_id="d1", deleted_at=now, purge_after=now + timedelta(days=90))
    r = _callback(c, monkeypatch, "d1")
    assert r.headers["location"] == "/?restore=1" and "aigo_restore=" in r.headers["set-cookie"]
    assert c.get("/auth/me").json()["restorePending"] is True
    assert c.post("/auth/signup", json={"agree": True}).status_code == 409


def test_signup_needs_cookie(c):
    r = c.post("/auth/signup", json={"agree": True})
    assert r.status_code == 401


def test_profile_patch(c, fdb, monkeypatch):
    fdb.add_user(kakao_id="123")
    _callback(c, monkeypatch)
    j = c.patch("/auth/profile", json={"nickname": "솔바람", "age": "72"}).json()
    assert j["nickname"] == "솔바람" and j["age"] == "72" and j["name"] == ""
    assert c.patch("/auth/profile", json={"age": "abc"}).status_code == 400
    assert c.patch("/auth/profile", json={"nickname": "가" * 13}).status_code == 422
    j = c.patch("/auth/profile", json={"nickname": ""}).json()
    assert j["nickname"] == "" and j["age"] == "72"


def test_profile_needs_login(c):
    assert c.patch("/auth/profile", json={"name": "a"}).status_code == 401


def test_me_guest_without_db():
    j = TestClient(app).get("/auth/me").json()
    assert j == {"loggedIn": False, "signupPending": False, "restorePending": False}

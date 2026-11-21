from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.routers import auth
from tests.fakedb import FakeAuthDB

PW = "goodpass1"


@pytest.fixture()
def fdb(monkeypatch):
    f = FakeAuthDB()
    monkeypatch.setattr(db, "executor", f)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("AIGO_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("AIGO_SMTP_USER", "sender")
    monkeypatch.setenv("AIGO_SMTP_PASSWORD", "app pass")
    monkeypatch.setenv("AIGO_PUBLIC_URL", "https://fe.example")
    return f


@pytest.fixture()
def sent(monkeypatch):
    box = []
    monkeypatch.setattr(auth, "send_code", lambda to, code: box.append((to, code)) or True)
    return box


@pytest.fixture()
def c(fdb):
    return TestClient(app, base_url="https://fe.example")


def test_password_hash():
    h = auth.hash_password(PW)
    assert h.startswith("scrypt$") and PW not in h
    assert auth.check_password(PW, h) and not auth.check_password("wrong", h)


def test_start_validation(c, fdb, sent, monkeypatch):
    assert c.post("/auth/email/start", json={"email": "nope", "password": PW}).status_code == 400
    assert c.post("/auth/email/start", json={"email": "a@b.co", "password": "short"}).status_code == 422
    fdb.add_user(email="taken@b.co")
    assert c.post("/auth/email/start", json={"email": "Taken@B.co", "password": PW}).status_code == 409
    fdb.add_user(email="ban@b.co", banned_at=datetime.now(config.KST))
    assert c.post("/auth/email/start", json={"email": "ban@b.co", "password": PW}).status_code == 403
    monkeypatch.setenv("AIGO_SMTP_PASSWORD", "")
    assert c.post("/auth/email/start", json={"email": "new@b.co", "password": PW}).status_code == 503


def test_send_fail_502(c, fdb, monkeypatch):
    monkeypatch.setattr(auth, "send_code", lambda to, code: False)
    assert c.post("/auth/email/start", json={"email": "a@b.co", "password": PW}).status_code == 502


def test_full_signup_and_login(c, fdb, sent):
    assert c.post("/auth/email/start", json={"email": "Me@Ex.com", "password": PW}).status_code == 204
    to, code = sent[0]
    assert to == "me@ex.com" and len(code) == 6 and fdb.codes[to]["code_hash"] != code
    assert c.post("/auth/email/finish", json={}).status_code == 400
    wrong = "000000" if code != "000000" else "111111"
    r = c.post("/auth/email/verify", json={"code": wrong})
    assert r.status_code == 400 and r.json()["detail"] == "숫자가 맞지 않아요"
    assert c.post("/auth/email/verify", json={"code": code}).json() == {"email": "me@ex.com", "restorable": False}
    assert c.post("/auth/email/finish", json={"age": "abc"}).status_code == 400
    r = c.post("/auth/email/finish", json={"name": "김", "nickname": "솔바람", "age": "70", "homeDong1": "성동구 성수1가1동"})
    assert r.status_code == 204
    me = c.get("/auth/me").json()
    assert me["provider"] == "email" and me["email"] == "me@ex.com" and me["age"] == "70" and len(fdb.consents) == 2
    assert fdb.codes == {}
    c.post("/auth/logout")
    assert c.post("/auth/email/login", json={"email": "me@ex.com", "password": "badpass1"}).status_code == 401
    assert c.post("/auth/email/login", json={"email": "ME@ex.com", "password": PW}).status_code == 204
    assert c.get("/auth/me").json()["loggedIn"] is True


def test_verify_tries_and_expiry(c, fdb, sent):
    c.post("/auth/email/start", json={"email": "a@b.co", "password": PW})
    code = sent[0][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert c.post("/auth/email/verify", json={"code": wrong}).status_code == 400
    assert c.post("/auth/email/verify", json={"code": code}).status_code == 429
    c.post("/auth/email/start", json={"email": "a@b.co", "password": PW})  # 다시 받으면 처음부터
    code = sent[1][1]
    fdb.codes["a@b.co"]["expires_at"] = datetime.now(config.KST) - timedelta(minutes=1)
    assert c.post("/auth/email/verify", json={"code": code}).status_code == 400


def test_verify_needs_cookie(c):
    assert c.post("/auth/email/verify", json={"code": "123456"}).status_code == 401


def test_deleted_email_restorable_and_login_blocked(c, fdb, sent):
    now = datetime.now(config.KST)
    old_hash = auth.hash_password("oldpass11")
    u = fdb.add_user(email="old@b.co", password_hash=old_hash, deleted_at=now, purge_after=now + timedelta(days=90))
    r = c.post("/auth/email/login", json={"email": "old@b.co", "password": "oldpass11"})
    assert r.status_code == 401 and "탈퇴한 계정" in r.json()["detail"]
    assert c.post("/auth/email/start", json={"email": "old@b.co", "password": PW}).status_code == 204
    j = c.post("/auth/email/verify", json={"code": sent[0][1]}).json()
    assert j["restorable"] is True
    assert c.post("/auth/email/finish", json={}).status_code == 409
    assert c.post("/auth/restore", json={"choice": "restore"}).json()["restored"] is True
    assert auth.check_password(PW, fdb.users[u["id"]]["password_hash"])
    assert c.get("/auth/me").json()["loggedIn"] is True


def test_banned_login_403(c, fdb):
    fdb.add_user(email="ban@b.co", password_hash=auth.hash_password(PW), banned_at=datetime.now(config.KST))
    assert c.post("/auth/email/login", json={"email": "ban@b.co", "password": PW}).status_code == 403

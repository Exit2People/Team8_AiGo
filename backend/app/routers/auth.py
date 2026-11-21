"""로그인 · 회원 (07_AUTH.md). 화면은 자기 주소의 /api/auth/* 로 불러요 (쿠키가 화면 주소에 붙어요).

SQL 앞 /*이름*/ 은 테스트 가짜 DB가 알아봐요. 카카오 토큰 · 회원 번호 · 비밀 값은 저장 · 로그하지 않아요.
"""

import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app import config, db
from app.data import loader

log = logging.getLogger("aigo.auth")
router = APIRouter()

SID, STATE, SIGNUP, ESIGNUP, RESTORE, RELOGIN = (
    "aigo_sid", "aigo_state", "aigo_signup", "aigo_esignup", "aigo_restore", "aigo_relogin")
AGE = {SID: config.SESSION_DAYS * 86400, STATE: 600, SIGNUP: 900, ESIGNUP: 1800, RESTORE: 900, RELOGIN: 30 * 86400}
RELOGIN_DAYS = 30

BANNED = "이용이 제한된 계정이에요. 궁금한 점은 운영자에게 문의해 주세요"
NO_SETUP = "로그인 설정이 아직 안 됐어요"
NO_KAKAO = "카카오 로그인 설정이 아직 안 됐어요"
NEED_LOGIN = "로그인해 주세요"
BAD_DONG = "사는 곳을 목록에서 다시 골라 주세요"
RESTORE_FIRST = "전에 쓰던 기록이 남아 있어요. 불러올지 새로 시작할지 먼저 골라 주세요"
CONSENT_DOCS = ("이용약관", "개인정보 처리방침")

KAKAO_AUTH = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN = "https://kauth.kakao.com/oauth/token"
KAKAO_ME = "https://kapi.kakao.com/v2/user/me"
KAKAO_UNLINK = "https://kapi.kakao.com/v1/user/unlink"


# ---------- 쿠키 · 서명 ----------

def _secret() -> str:
    s = config.env("AIGO_SESSION_SECRET")
    if not s:
        raise HTTPException(503, NO_SETUP)
    return s


def _mac(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def sign(value: str, ttl: int) -> str:
    body = f"{value}|{int(time.time()) + ttl}"
    return f"{body}|{_mac(_secret(), body)}"


def unsign(token: str | None) -> str | None:
    s = config.env("AIGO_SESSION_SECRET")
    if not token or not s:
        return None
    parts = token.rsplit("|", 2)
    if len(parts) != 3:
        return None
    value, exp, mac = parts
    if not hmac.compare_digest(_mac(s, f"{value}|{exp}"), mac):
        return None
    try:
        if int(exp) < time.time():
            return None
    except ValueError:
        return None
    return value


def _secure() -> bool:
    return config.public_url().startswith("https://")


def set_cookie(resp: Response, name: str, value: str) -> None:
    resp.set_cookie(name, value, max_age=AGE[name], httponly=True, samesite="lax", secure=_secure(), path="/")


def del_cookie(resp: Response, name: str) -> None:
    resp.delete_cookie(name, path="/", httponly=True, samesite="lax", secure=_secure())


# ---------- 세션 ----------

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(resp: Response, user_id) -> None:
    token = secrets.token_urlsafe(32)
    db.run("/*session_add*/ insert into sessions (id, user_id, expires_at) values (%s, %s, %s)",
           (_hash(token), user_id, datetime.now(config.KST) + timedelta(days=config.SESSION_DAYS)))
    db.run("/*user_touch*/ update users set last_login_at = now() where id = %s", (user_id,))
    set_cookie(resp, SID, token)


def session_user(request: Request) -> dict | None:
    """탈퇴 · 밴이 아닌 회원만. DB가 없으면 손님으로 봐요."""
    token = request.cookies.get(SID)
    if not token or not db.configured():
        return None
    return db.run("/*session_user*/ select u.* from sessions s join users u on u.id = s.user_id "
                  "where s.id = %s and s.expires_at > now() and u.deleted_at is null and u.banned_at is null",
                  (_hash(token),), "one")


def require_user(request: Request) -> dict:
    u = session_user(request)
    if not u:
        raise HTTPException(401, NEED_LOGIN)
    return u


def purge_expired() -> None:
    db.run("/*purge*/ delete from users where purge_after is not null and purge_after < now()")


# ---------- 사는 곳 ----------

def dong_id(label: str | None) -> str | None:
    """`성동구 성수1가1동` → 동 ID. 빈 값은 None, 목록에 없으면 400."""
    if label is None or label.strip() == "":
        return None
    hit = loader.dong_by_label(label)
    if not hit:
        raise HTTPException(400, BAD_DONG)
    return hit[1]["id"]


def dong_label(did: str | None) -> str | None:
    if not did:
        return None
    hit = loader.dong_by_id(did)
    return f"{hit[0]} {hit[1]['name']}" if hit else None


def me_view(u: dict) -> dict:
    created = u.get("created_at")
    return {
        "loggedIn": True, "id": str(u["id"]), "provider": "kakao" if u.get("kakao_id") else "email",
        "email": u.get("email") or "", "name": u.get("name") or "", "nickname": u.get("nickname") or "",
        "age": "" if u.get("age") is None else str(u["age"]),
        "homeDong1": dong_label(u.get("home_dong1_id")), "homeDong2": dong_label(u.get("home_dong2_id")),
        "joinedAt": created.astimezone(config.KST).strftime("%Y-%m-%d") if created else "",
    }


def add_consents(user_id) -> None:
    for doc in CONSENT_DOCS:
        db.run("/*consent_add*/ insert into consents (user_id, doc_type, doc_version) values (%s, %s, %s)",
               (user_id, doc, config.CONSENT_VERSION))


# ---------- 카카오 ----------

def kakao_user_id(code: str) -> str | None:
    """코드 → 토큰 → 회원 번호. 토큰은 버려요. 실패는 None (이유는 남기지 않아요)."""
    form = {"grant_type": "authorization_code", "client_id": config.env("KAKAO_REST_API_KEY"),
            "redirect_uri": f"{config.public_url()}/api/auth/kakao/callback", "code": code}
    if config.env("KAKAO_CLIENT_SECRET"):
        form["client_secret"] = config.env("KAKAO_CLIENT_SECRET")
    try:
        with httpx.Client(timeout=5.0) as c:
            t = c.post(KAKAO_TOKEN, data=form)
            if t.status_code != 200:
                return None
            access = t.json().get("access_token")
            if not access:
                return None
            me = c.get(KAKAO_ME, headers={"Authorization": f"Bearer {access}"})
            if me.status_code != 200:
                return None
            kid = me.json().get("id")
            return str(kid) if kid is not None else None
    except (httpx.HTTPError, ValueError):
        return None


@router.get("/auth/kakao/start")
def kakao_start(request: Request):
    key = config.env("KAKAO_REST_API_KEY")
    if not key or not config.env("AIGO_SESSION_SECRET"):
        raise HTTPException(503, NO_KAKAO)
    state = secrets.token_urlsafe(16)
    from urllib.parse import urlencode

    q = {"client_id": key, "redirect_uri": f"{config.public_url()}/api/auth/kakao/callback",
         "response_type": "code", "state": state}
    if request.cookies.get(RELOGIN):
        q["prompt"] = "login"
    resp = RedirectResponse(f"{KAKAO_AUTH}?{urlencode(q)}", status_code=302)
    set_cookie(resp, STATE, sign(state, AGE[STATE]))
    return resp


def _go(path: str) -> RedirectResponse:
    resp = RedirectResponse(path, status_code=302)
    del_cookie(resp, STATE)
    del_cookie(resp, RELOGIN)
    return resp


@router.get("/auth/kakao/callback")
def kakao_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    want = unsign(request.cookies.get(STATE))
    if error or not code or not state or not want or not hmac.compare_digest(want, state):
        return _go("/?login=fail")
    kid = kakao_user_id(code)
    if not kid:
        return _go("/?login=fail")
    try:
        purge_expired()
        u = db.run("/*user_by_kakao*/ select * from users where kakao_id = %s", (kid,), "one")
    except HTTPException:
        return _go("/?login=fail")
    if u and u.get("banned_at"):
        return _go("/?login=banned")
    if u and u.get("deleted_at"):
        resp = _go("/?restore=1")
        set_cookie(resp, RESTORE, sign(str(u["id"]), AGE[RESTORE]))
        set_cookie(resp, SIGNUP, sign(kid, AGE[SIGNUP]))
        return resp
    if u:
        resp = _go("/?login=ok")
        new_session(resp, u["id"])
        return resp
    resp = _go("/?signup=1")
    set_cookie(resp, SIGNUP, sign(kid, AGE[SIGNUP]))
    return resp


class SignupBody(BaseModel):
    agree: bool
    homeDong1: str | None = Field(default=None, max_length=40)
    homeDong2: str | None = Field(default=None, max_length=40)


@router.post("/auth/signup", status_code=204)
def signup(body: SignupBody, request: Request):
    _secret()
    kid = unsign(request.cookies.get(SIGNUP))
    if not kid:
        raise HTTPException(401, "카카오 확인이 끝났거나 오래됐어요. 다시 시작해 주세요")
    if not body.agree:
        raise HTTPException(400, "동의해야 가입할 수 있어요")
    d1, d2 = dong_id(body.homeDong1), dong_id(body.homeDong2)
    purge_expired()
    u = db.run("/*user_by_kakao*/ select * from users where kakao_id = %s", (kid,), "one")
    if u and u.get("banned_at"):
        raise HTTPException(403, BANNED)
    if u and u.get("deleted_at"):
        raise HTTPException(409, RESTORE_FIRST)
    resp = Response(status_code=204)
    if u:
        new_session(resp, u["id"])
    else:
        row = db.run("/*user_add_kakao*/ insert into users (kakao_id, home_dong1_id, home_dong2_id) "
                     "values (%s, %s, %s) returning id", (kid, d1, d2), "one")
        add_consents(row["id"])
        new_session(resp, row["id"])
    del_cookie(resp, SIGNUP)
    return resp


# ---------- 공통 ----------

@router.get("/auth/me")
def me(request: Request):
    u = session_user(request)
    if not u:
        return {"loggedIn": False, "signupPending": bool(unsign(request.cookies.get(SIGNUP))),
                "restorePending": bool(unsign(request.cookies.get(RESTORE)))}
    return me_view(u)


class ProfileBody(BaseModel):
    homeDong1: str | None = Field(default=None, max_length=40)
    homeDong2: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=20)
    nickname: str | None = Field(default=None, max_length=12)
    age: str | None = Field(default=None, max_length=3)


def parse_age(age: str | None) -> int | None:
    if age is None or age.strip() == "":
        return None
    a = age.strip()
    if not re.fullmatch(r"\d{1,3}", a) or not 14 <= int(a) <= 120:
        raise HTTPException(400, "나이를 숫자로 적어 주세요")
    return int(a)


@router.patch("/auth/profile")
def profile(body: ProfileBody, request: Request):
    u = require_user(request)
    cols = {"homeDong1": "home_dong1_id", "homeDong2": "home_dong2_id", "name": "name", "nickname": "nickname",
            "age": "age"}
    pairs = []
    for f in sorted(body.model_fields_set):
        v = getattr(body, f)
        if f in ("homeDong1", "homeDong2"):
            v = dong_id(v)
        elif f == "age":
            v = parse_age(v)
        else:
            v = (v or "").strip() or None
        pairs.append((cols[f], v))
    if pairs:
        db.run(f"/*user_update*/ update users set {', '.join(c + ' = %s' for c, _ in pairs)} where id = %s",
               (*[v for _, v in pairs], u["id"]))
    fresh = db.run("/*user_by_id*/ select * from users where id = %s", (u["id"],), "one")
    return me_view(fresh or u)


@router.post("/auth/logout", status_code=204)
def logout(request: Request):
    token = request.cookies.get(SID)
    if token and db.configured():
        db.run("/*session_del*/ delete from sessions where id = %s", (_hash(token),))
    resp = Response(status_code=204)
    del_cookie(resp, SID)
    return resp

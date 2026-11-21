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

from app import config, db, nickname
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


def ok_nickname(v: str | None) -> str | None:
    """빈 값은 지우기(None). 쓸 수 없는 닉네임이면 400에 이유 문장을 담아요."""
    t = (v or "").strip()
    if not t:
        return None
    hit = nickname.check_sync(t)
    if hit:
        raise HTTPException(400, hit[1])
    return t


class NicknameBody(BaseModel):
    nickname: str = Field(default="", max_length=40)


@router.post("/auth/nickname/check")
def nickname_check(body: NicknameBody):
    """저장하기 전에 미리 확인해요 (가입 중 닉네임 단계 · 내 정보). 로그인 없이 부를 수 있어요."""
    hit = nickname.check_sync(body.nickname)
    return {"ok": hit is None, "reason": hit[0] if hit else None, "message": hit[1] if hit else None}


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
        elif f == "nickname":
            v = ok_nickname(v)
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


# ---------- 탈퇴 (90일 보관) · 되살리기 ----------

def kakao_unlink(kid: str) -> None:
    """카카오 연결 끊기. 키가 없거나 실패해도 탈퇴는 이어 가요 (회원 번호는 로그에 안 남겨요)."""
    key = config.env("KAKAO_ADMIN_KEY")
    if not key:
        return
    try:
        r = httpx.post(KAKAO_UNLINK, headers={"Authorization": f"KakaoAK {key}"},
                       data={"target_id_type": "user_id", "target_id": kid}, timeout=3.0)
        if r.status_code != 200:
            log.warning("카카오 연결 끊기 실패: HTTP %s", r.status_code)
    except httpx.HTTPError as e:
        log.warning("카카오 연결 끊기 실패: %s", type(e).__name__)


@router.delete("/auth/account", status_code=204)
def delete_account(request: Request):
    u = require_user(request)
    if u.get("kakao_id"):
        kakao_unlink(u["kakao_id"])
    db.run("/*score_del*/ delete from game_scores where user_id = %s", (u["id"],))
    db.run("/*session_del_user*/ delete from sessions where user_id = %s", (u["id"],))
    db.run("/*user_soft_delete*/ update users set deleted_at = now(), purge_after = now() + make_interval(days => %s) "
           "where id = %s", (config.RETENTION_DAYS, u["id"]))
    resp = Response(status_code=204)
    del_cookie(resp, SID)
    if u.get("kakao_id"):
        set_cookie(resp, RELOGIN, "1")
    return resp


RESTORE_STALE = "확인이 끝났거나 오래됐어요. 처음부터 다시 해 주세요"
RESTORE_MISSING = "전에 쓰던 기록을 찾지 못했어요. 처음부터 다시 해 주세요"


def _restore_target(request: Request) -> dict:
    _secret()
    uid = unsign(request.cookies.get(RESTORE))
    if not uid:
        raise HTTPException(401, RESTORE_STALE)
    purge_expired()
    u = db.run("/*user_by_id*/ select * from users where id = %s", (uid,), "one")
    if not u or not u.get("deleted_at"):
        raise HTTPException(401, RESTORE_MISSING)
    if u.get("banned_at"):
        raise HTTPException(403, BANNED)
    return u


def _day(dt) -> str | None:
    return dt.astimezone(config.KST).strftime("%Y-%m-%d") if dt else None


@router.get("/auth/restore")
def restore_info(request: Request):
    u = _restore_target(request)
    return {"pending": True, "id": str(u["id"]), "provider": "kakao" if u.get("kakao_id") else "email",
            "nickname": u.get("nickname") or "", "deletedAt": _day(u.get("deleted_at")),
            "purgeAfter": _day(u.get("purge_after"))}


class RestoreBody(BaseModel):
    choice: str = Field(pattern="^(restore|fresh)$")


@router.post("/auth/restore")
def restore(body: RestoreBody, request: Request):
    u = _restore_target(request)
    provider = "kakao" if u.get("kakao_id") else "email"
    resp_body = {"restored": body.choice == "restore", "id": str(u["id"]), "provider": provider}
    from fastapi.responses import JSONResponse

    resp = JSONResponse(resp_body)
    if body.choice == "fresh":
        db.run("/*user_del*/ delete from users where id = %s", (u["id"],))
        del_cookie(resp, RESTORE)
        return resp
    db.run("/*user_undelete*/ update users set deleted_at = null, purge_after = null where id = %s", (u["id"],))
    if provider == "email" and u.get("email"):
        code = db.run("/*code_get*/ select * from email_codes where email = %s", (u["email"],), "one")
        if code and code.get("verified"):
            db.run("/*user_password*/ update users set password_hash = %s where id = %s",
                   (code["password_hash"], u["id"]))
            db.run("/*code_del*/ delete from email_codes where email = %s", (u["email"],))
    new_session(resp, u["id"])
    for n in (RESTORE, SIGNUP, ESIGNUP):
        del_cookie(resp, n)
    return resp


# ---------- 이메일 가입 (Gmail로 확인 숫자) ----------

CODE_MINUTES = 10
CODE_TRIES = 5
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
EMAIL_TAKEN = "이미 가입한 이메일이에요. 로그인해 주세요"
RESTART = "처음부터 다시 가입해 주세요"


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return f"scrypt${salt.hex()}${h.hex()}"


def check_password(pw: str, stored: str | None) -> bool:
    try:
        kind, salt, h = (stored or "").split("$")
        if kind != "scrypt":
            return False
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1)
        return hmac.compare_digest(got.hex(), h)
    except (ValueError, TypeError):
        return False


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def smtp_ready() -> bool:
    return bool(config.env("AIGO_SMTP_USER") and config.env("AIGO_SMTP_PASSWORD"))


def send_code(to: str, code: str) -> bool:
    import smtplib
    from email.message import EmailMessage

    user = config.env("AIGO_SMTP_USER") or ""
    pw = (config.env("AIGO_SMTP_PASSWORD") or "").replace(" ", "")
    msg = EmailMessage()
    msg["Subject"] = f"[AI GO] 이메일 확인 숫자 {code}"
    msg["From"] = f"AI GO <{user}>"
    msg["To"] = to
    msg.set_content(f"AI GO 가입 확인 숫자예요.\n\n{code}\n\n10분 안에 화면에 넣어 주세요. 직접 가입하지 않았다면 이 메일은 지워 주세요.")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as s:
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        log.warning("메일 보내기 실패: %s", type(e).__name__)
        return False


def _email(raw: str) -> str:
    e = (raw or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.fullmatch(e):
        raise HTTPException(400, "이메일을 다시 확인해 주세요")
    return e


class EmailStartBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=72)


@router.post("/auth/email/start", status_code=204)
def email_start(body: EmailStartBody):
    _secret()
    email = _email(body.email)
    purge_expired()
    u = db.run("/*user_by_email*/ select * from users where email = %s", (email,), "one")
    if u and u.get("banned_at"):
        raise HTTPException(403, BANNED)
    if u and not u.get("deleted_at"):
        raise HTTPException(409, EMAIL_TAKEN)
    if not smtp_ready():
        raise HTTPException(503, "메일 보내기 설정이 아직 안 됐어요")
    code = f"{secrets.randbelow(10 ** 6):06d}"
    db.run("/*code_put*/ insert into email_codes (email, code_hash, password_hash, expires_at, tries, verified) "
           "values (%s, %s, %s, %s, 0, false) on conflict (email) do update set code_hash = excluded.code_hash, "
           "password_hash = excluded.password_hash, expires_at = excluded.expires_at, tries = 0, verified = false",
           (email, _code_hash(code), hash_password(body.password),
            datetime.now(config.KST) + timedelta(minutes=CODE_MINUTES)))
    if not send_code(email, code):
        raise HTTPException(502, "확인 메일을 보내지 못했어요. 잠시 뒤에 다시 해 주세요")
    resp = Response(status_code=204)
    set_cookie(resp, ESIGNUP, sign(email, AGE[ESIGNUP]))
    return resp


class EmailVerifyBody(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/auth/email/verify")
def email_verify(body: EmailVerifyBody, request: Request):
    _secret()
    email = unsign(request.cookies.get(ESIGNUP))
    if not email:
        raise HTTPException(401, RESTART)
    purge_expired()
    row = db.run("/*code_get*/ select * from email_codes where email = %s", (email,), "one")
    if not row:
        raise HTTPException(401, RESTART)
    u = db.run("/*user_by_email*/ select * from users where email = %s", (email,), "one")
    if u and u.get("banned_at"):
        raise HTTPException(403, BANNED)
    if int(row.get("tries") or 0) >= CODE_TRIES:
        raise HTTPException(429, "여러 번 틀렸어요. 메일을 다시 받아 주세요")
    if row["expires_at"] < datetime.now(config.KST):
        raise HTTPException(400, "확인 숫자가 지났어요. 메일을 다시 받아 주세요")
    if not hmac.compare_digest(_code_hash(body.code), row["code_hash"]):
        db.run("/*code_try*/ update email_codes set tries = tries + 1 where email = %s", (email,))
        raise HTTPException(400, "숫자가 맞지 않아요")
    db.run("/*code_ok*/ update email_codes set verified = true where email = %s", (email,))
    from fastapi.responses import JSONResponse

    restorable = bool(u and u.get("deleted_at"))
    resp = JSONResponse({"email": email, "restorable": restorable})
    if restorable:
        set_cookie(resp, RESTORE, sign(str(u["id"]), AGE[RESTORE]))
    return resp


class EmailFinishBody(BaseModel):
    name: str = Field(default="", max_length=20)
    nickname: str = Field(default="", max_length=12)
    age: str = Field(default="", max_length=3)
    homeDong1: str | None = Field(default=None, max_length=40)
    homeDong2: str | None = Field(default=None, max_length=40)


@router.post("/auth/email/finish", status_code=204)
def email_finish(body: EmailFinishBody, request: Request):
    _secret()
    email = unsign(request.cookies.get(ESIGNUP))
    if not email:
        raise HTTPException(401, RESTART)
    row = db.run("/*code_get*/ select * from email_codes where email = %s", (email,), "one")
    if not row or not row.get("verified"):
        raise HTTPException(400, "이메일 확인부터 해 주세요")
    age = parse_age(body.age)
    nick = ok_nickname(body.nickname)
    d1, d2 = dong_id(body.homeDong1), dong_id(body.homeDong2)
    purge_expired()
    u = db.run("/*user_by_email*/ select * from users where email = %s", (email,), "one")
    if u and u.get("banned_at"):
        raise HTTPException(403, BANNED)
    if u and u.get("deleted_at"):
        raise HTTPException(409, RESTORE_FIRST)
    if u:
        raise HTTPException(409, EMAIL_TAKEN)
    new = db.run("/*user_add_email*/ insert into users (email, password_hash, name, nickname, age, home_dong1_id, "
                 "home_dong2_id) values (%s, %s, %s, %s, %s, %s, %s) returning id",
                 (email, row["password_hash"], body.name.strip() or None, nick, age, d1, d2),
                 "one")
    add_consents(new["id"])
    db.run("/*code_del*/ delete from email_codes where email = %s", (email,))
    resp = Response(status_code=204)
    new_session(resp, new["id"])
    del_cookie(resp, ESIGNUP)
    return resp


class EmailLoginBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=72)


@router.post("/auth/email/login", status_code=204)
def email_login(body: EmailLoginBody):
    _secret()
    email = (body.email or "").strip().lower()
    purge_expired()
    u = db.run("/*user_by_email*/ select * from users where email = %s", (email,), "one")
    if not u or not check_password(body.password, u.get("password_hash")):
        raise HTTPException(401, "이메일이나 비밀번호가 맞지 않아요")
    if u.get("banned_at"):
        raise HTTPException(403, BANNED)
    if u.get("deleted_at"):
        raise HTTPException(401, "탈퇴한 계정이에요. '처음이에요 · 가입하기'로 다시 가입하면 전에 쓰던 기록을 불러올 수 있어요")
    resp = Response(status_code=204)
    new_session(resp, u["id"])
    return resp

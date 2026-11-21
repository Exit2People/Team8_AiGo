"""도착 예정 · 방명록 읽기 · 톡방. 익명(client · nick), 좌표 안 받음. SQL 앞 /*이름*/ 은 테스트 가짜 DB가 알아봐요."""

import asyncio
import hmac
import math
import re
from datetime import timedelta

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import chat_safety, config, db
from app.data import loader

router = APIRouter()

PAGE_SIZE = 4
MAX_TEXT = 200
QUICK = ("반가워요", "고마워요", "좋아요")
CONTEXT_MINE = 3
CONTEXT_OTHERS = 3
NOT_JOINED = "톡방에 먼저 들어와 주세요"
BLOCKED = {"code": "blocked", "message": "보낼 수 없는 말이 들어 있는 것 같아요. 고쳐서 보내 주세요"}
_LINK = re.compile(r"https?://|www\.|\.com|\.net|\.kr|\.co", re.I)
_PHONE = re.compile(r"(01[016789]|0\d{1,2})[\s.\-]?\d{3,4}[\s.\-]?\d{4}")


class ClientBody(BaseModel):
    client: str = Field(min_length=6, max_length=64)


class JoinBody(ClientBody):
    nick: str = Field(min_length=1, max_length=12)


class MessageBody(ClientBody):
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class ReportBody(ClientBody):
    target: str = Field(min_length=1, max_length=12)


def today():
    return config.now().date()


def _place(pid: str) -> dict:
    p = loader.place_by_id(pid)
    if p is None:
        raise HTTPException(404, "장소를 찾을 수 없어요")
    return p


def _cleanup() -> None:
    d = today()
    for t in ("chat_messages", "chat_members", "chat_reports", "place_expects"):
        db.run(f"/*cleanup*/ delete from {t} where day < %s", (d,))


@router.get("/cron/daily-cleanup", include_in_schema=False)
def daily_cleanup(authorization: str | None = Header(None)):
    """서울 날짜가 바뀌면 Vercel Cron이 불러요 (매일 00시 KST). 어제까지의 톡방 · 멤버 · 신고 · 도착 예정을 지워요.
    Vercel은 `CRON_SECRET`을 `Authorization: Bearer …`로 붙여 보내요. 비밀이 없거나 틀리면 거절해요."""
    secret = config.env("CRON_SECRET")
    if not secret:
        raise HTTPException(503, "정리 설정이 없어요")
    if not hmac.compare_digest(authorization or "", f"Bearer {secret}"):
        raise HTTPException(401, "권한이 없어요")
    _cleanup()
    return {"ok": True, "day": today().isoformat()}


def _expected(pid: str) -> int:
    r = db.run("/*expect_count*/ select count(*) as n from place_expects where day = %s and place_id = %s",
               (today(), pid), "one")
    return int((r or {}).get("n") or 0)


@router.get("/places/{pid}/social")
def social(pid: str):
    _place(pid)
    n = _expected(pid)
    rc = db.run("/*review_count*/ select count(*) as n from place_reviews where place_id = %s", (pid,), "one")
    tags = db.run("/*review_tags*/ select tag, count(*) as n from place_reviews where place_id = %s "
                  "group by tag order by count(*) desc, tag asc limit 3", (pid,), "all") or []
    return {"expectedToday": n, "reviewCount": int((rc or {}).get("n") or 0),
            "topTags": [[t["tag"], int(t["n"])] for t in tags]}


@router.post("/places/{pid}/expect")
def expect(pid: str, body: ClientBody):
    _place(pid)
    _cleanup()
    db.run("/*expect_add*/ insert into place_expects (day, place_id, client) values (%s, %s, %s) "
           "on conflict do nothing", (today(), pid, body.client))
    return {"expectedToday": _expected(pid)}


@router.post("/places/{pid}/expect/cancel")
def expect_cancel(pid: str, body: ClientBody):
    _place(pid)
    db.run("/*expect_del*/ delete from place_expects where day = %s and place_id = %s and client = %s",
           (today(), pid, body.client))
    return {"expectedToday": _expected(pid)}


@router.get("/places/{pid}/reviews")
def reviews(pid: str, page: int = 1):
    _place(pid)
    rc = db.run("/*review_count*/ select count(*) as n from place_reviews where place_id = %s", (pid,), "one")
    total = int((rc or {}).get("n") or 0)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = db.run("/*review_page*/ select id, body, tag, nick, created_at from place_reviews where place_id = %s "
                  "order by created_at desc, id desc limit %s offset %s",
                  (pid, PAGE_SIZE, (page - 1) * PAGE_SIZE), "all") or []
    items = [{"id": str(r["id"]), "text": r["body"], "tag": r["tag"], "nick": r["nick"],
              "date": r["created_at"].astimezone(config.KST).strftime("%m.%d")} for r in rows]
    return {"total": total, "page": page, "pages": pages, "items": items}


def _member(pid: str, client: str) -> dict | None:
    return db.run("/*member_get*/ select nick from chat_members where day = %s and place_id = %s and client = %s",
                  (today(), pid, client), "one")


def _say(pid: str, client: str, nick: str, kind: str, text: str) -> dict:
    return db.run("/*msg_add*/ insert into chat_messages (day, place_id, client, nick, kind, body) "
                  "values (%s, %s, %s, %s, %s, %s) returning id, nick, kind, body, created_at",
                  (today(), pid, client, nick, kind, text), "one")


def _msg(r: dict, client: str | None) -> dict:
    return {"id": int(r["id"]), "nick": r["nick"], "kind": r["kind"], "text": r["body"],
            "at": r["created_at"].astimezone(config.KST).strftime("%H:%M"),
            "mine": client is not None and r.get("client") == client}


def _state(pid: str, client: str | None, after: int = 0) -> dict:
    d = today()
    members = db.run("/*member_list*/ select client, nick from chat_members where day = %s and place_id = %s "
                     "order by nick asc", (d, pid), "all") or []
    rows = db.run("/*msg_list*/ select id, client, nick, kind, body, created_at from chat_messages "
                  "where day = %s and place_id = %s and id > %s order by id asc limit 200", (d, pid, after), "all") or []
    tomorrow = config.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return {"members": [m["nick"] for m in members], "count": len(members),
            "joined": any(m["client"] == client for m in members), "expiresAt": tomorrow.isoformat(),
            "messages": [_msg(r, client) for r in rows]}


@router.get("/chat/{pid}")
def chat_state(pid: str, client: str | None = None, after: int = Query(0, ge=0)):
    _place(pid)
    return _state(pid, client, after)


@router.post("/chat/{pid}/join")
def chat_join(pid: str, body: JoinBody):
    _place(pid)
    _cleanup()
    m = _member(pid, body.client)
    if m:
        nick = m["nick"]
    else:
        base = body.nick.strip() or "손님"
        taken = {r["nick"] for r in db.run("/*member_list*/ select client, nick from chat_members where day = %s "
                                           "and place_id = %s order by nick asc", (today(), pid), "all") or []}
        nick, n = base, 2
        while nick in taken:
            nick, n = f"{base}{n}", n + 1
        db.run("/*member_add*/ insert into chat_members (day, place_id, client, nick) values (%s, %s, %s, %s) "
               "on conflict do nothing", (today(), pid, body.client, nick))
        _say(pid, body.client, nick, "system", f"{nick} 님이 들어왔어요")
    return {**_state(pid, body.client), "nick": nick}


@router.post("/chat/{pid}/messages")
async def chat_message(pid: str, body: MessageBody):
    await asyncio.to_thread(_place, pid)
    m = await asyncio.to_thread(_member, pid, body.client)
    if not m:
        raise HTTPException(403, NOT_JOINED)
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "보낼 글이 없어요")
    if _LINK.search(text):
        raise HTTPException(400, "링크는 보낼 수 없어요")
    kind = "quick" if text in QUICK else "text"
    if kind == "text":
        since = config.now() - timedelta(minutes=3)
        mine = await asyncio.to_thread(
            db.run, "/*msg_mine*/ select body from chat_messages where day = %s and place_id = %s and client = %s "
                    "and kind = 'text' and created_at >= %s order by id desc limit %s",
            (today(), pid, body.client, since, CONTEXT_MINE), "all")
        others = await asyncio.to_thread(
            db.run, "/*msg_others*/ select body from chat_messages where day = %s and place_id = %s and client <> %s "
                    "and kind in ('text', 'quick') order by id desc limit %s",
            (today(), pid, body.client, CONTEXT_OTHERS), "all")
        mine_t = [r["body"] for r in reversed(mine or [])]
        others_t = [r["body"] for r in reversed(others or [])]
        if await chat_safety.is_blocked(text, mine_t, others_t):
            return JSONResponse(status_code=400, content={"detail": BLOCKED})
        text = _PHONE.sub("(전화번호는 가렸어요)", text)
    r = await asyncio.to_thread(_say, pid, body.client, m["nick"], kind, text)
    return {**_msg({**r, "client": body.client}, body.client)}


@router.post("/chat/{pid}/leave")
def chat_leave(pid: str, body: ClientBody):
    _place(pid)
    m = _member(pid, body.client)
    if m:
        db.run("/*member_del*/ delete from chat_members where day = %s and place_id = %s and client = %s",
               (today(), pid, body.client))
        _say(pid, body.client, m["nick"], "system", f"{m['nick']} 님이 나갔어요")
    return {"ok": True}


@router.post("/chat/{pid}/report")
def chat_report(pid: str, body: ReportBody):
    _place(pid)
    if not _member(pid, body.client):
        raise HTTPException(403, NOT_JOINED)
    db.run("/*report_add*/ insert into chat_reports (day, place_id, target_nick) values (%s, %s, %s)",
           (today(), pid, body.target.strip()))
    return {"ok": True}

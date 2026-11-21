"""담고 달리기 랭킹. 회원만 올려요. 다른 사람 회원 번호는 내려주지 않아요. 밴 회원 줄은 빼요."""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import config, db
from app.routers.auth import session_user

router = APIRouter()

NO_NAME = "이름 없는 회원"
_VISIBLE = "u.deleted_at is null and u.banned_at is null"


class ScoreBody(BaseModel):
    steps: int = Field(ge=0, le=999999)


def _rank(steps: int, at) -> int:
    r = db.run(f"/*rank_of*/ select count(*) as n from game_scores g join users u on u.id = g.user_id "
               f"where {_VISIBLE} and (g.steps > %s or (g.steps = %s and g.achieved_at < %s))", (steps, steps, at), "one")
    return int((r or {}).get("n") or 0) + 1


def _iso(dt) -> str:
    return dt.astimezone(config.KST).isoformat(timespec="seconds")


@router.post("/game/scores")
def post_score(body: ScoreBody, request: Request):
    u = session_user(request)
    if not u:
        raise HTTPException(401, "로그인하면 랭킹에 올라가요")
    before = db.run("/*score_get*/ select steps, achieved_at from game_scores where user_id = %s", (u["id"],), "one")
    row = db.run("/*score_upsert*/ insert into game_scores (user_id, steps) values (%s, %s) "
                 "on conflict (user_id) do update set steps = excluded.steps, achieved_at = now() "
                 "where excluded.steps > game_scores.steps returning steps, achieved_at", (u["id"], body.steps), "one")
    best = row or db.run("/*score_get*/ select steps, achieved_at from game_scores where user_id = %s",
                         (u["id"],), "one")
    is_best = row is not None and (before is None or body.steps > before["steps"])
    return {"rank": _rank(best["steps"], best["achieved_at"]), "best": int(best["steps"]), "isBest": is_best}


@router.get("/game/ranking")
def ranking(request: Request, limit: int = Query(10, ge=1, le=50)):
    u = session_user(request)
    rows = db.run(f"/*rank_top*/ select g.user_id, g.steps, g.achieved_at, u.nickname from game_scores g "
                  f"join users u on u.id = g.user_id where {_VISIBLE} order by g.steps desc, g.achieved_at asc limit %s",
                  (limit,), "all") or []
    total = db.run(f"/*rank_total*/ select count(*) as n from game_scores g join users u on u.id = g.user_id "
                   f"where {_VISIBLE}", None, "one")
    me_id = str(u["id"]) if u else None

    def entry(r):
        return {"nickname": r.get("nickname") or NO_NAME, "steps": int(r["steps"]), "at": _iso(r["achieved_at"]),
                "mine": me_id is not None and str(r["user_id"]) == me_id}

    me = None
    if u:
        mine = db.run("/*score_get*/ select steps, achieved_at from game_scores where user_id = %s", (u["id"],), "one")
        if mine:
            me = {"rank": _rank(mine["steps"], mine["achieved_at"]),
                  "entry": entry({**mine, "user_id": u["id"], "nickname": u.get("nickname")})}
    return {"top": [entry(r) for r in rows], "me": me, "total": int((total or {}).get("n") or 0)}

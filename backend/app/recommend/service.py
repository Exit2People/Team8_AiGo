"""추천 전체 순서: 거르기 → (넓혀 찾기 · 실제 길) → 고르기 → 확인 → 보여 주기 전 다시 재기 → 정보 붙이기.

고르기 사슬: 추천 에이전트(AIGO_AGENT=1, 이 브랜치 기본. 화면 대기 20초 안에 끝나게 시간을 나눠요) → 실패 · 늦음이면 Claude 한 번(pick_by_ai) → 규칙.
exp/agent-full: 에이전트를 쓰면 넓혀 다시 찾기(이동 범위 +20분 · 바람 넓히기)도 에이전트가 해요. 못 쓰면 코드가 예전처럼 넓혀요.
"""

import asyncio
import logging
import time

from app import config
from app.data import filter_places as fp
from app.data import loader, places_db, sync, transit, weather
from app.recommend import expand as ex
from app.recommend import info, map_candidates
from app.recommend.pick import limit_revisits, pick_by_ai, pick_by_rule, rule_reason
from app.recommend.verify import check, confirm_by_jev, verify_picks
from app.recommend.wish import place_text
from app.schemas import Conditions

log = logging.getLogger("aigo.recommend")

AGENT_RESERVE = 8.0  # 에이전트가 실패해도 한 번 호출(6초) + 다시 재기 · 정보 붙이기가 들어갈 자리


def _https(url: str | None) -> str | None:
    if not url:
        return None
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def _candidate(v: dict) -> dict:
    it = v["item"]
    p = it["place"]
    c = {
        "place": {"id": p.get("id"), "name": p.get("name"), "kind": p.get("kind"), "gu": p.get("gu"),
                  "lat": p.get("lat"), "lng": p.get("lng")},
        "reason": v["reason"],
        "open": it.get("open") or {"today": None, "lastEntry": None},
        "route": it["route"],
    }
    if it.get("visited"):
        c["visited"] = True  # 칸 더하기: 화면이 쓰면 '다녀온 곳' 표시를 붙일 수 있어요
    return c


def _finish(c: dict, it: dict) -> None:
    p = it["place"]
    if p.get("source") == "kakao":
        c["place"]["source"] = "kakao"
    if p.get("event"):
        ev = p["event"]
        c["event"] = {"start": ev.get("start"), "end": ev.get("end"), "venue": ev.get("venue"),
                      "hours": ev.get("hours"), "sub": ev.get("sub")}
    c["place"]["photo"] = _https((c.get("info") or {}).get("photo"))


def _mark_shown(items: list[dict], shown: set[str], visited: set[str]) -> list[dict]:
    """최근에 보여 줬지만 고르지 않은 곳에 표시해요 (다녀온 곳은 '다녀온 곳' 규칙만 따라요)."""
    for x in items:
        pid = x["place"].get("id")
        if pid in shown and pid not in visited:
            x["shownRecent"] = True
    return items


def _relax(cond: Conditions, now, wtext, visited, shown_set: set[str],
           visited_set: set[str]) -> tuple[list[dict], Conditions] | None:
    """이동 범위 안에 0곳이면 상한 +20분으로 한 번 넓혀요 (코드 길)."""
    wide = cond.model_copy(deep=True)
    wide.range.oneWayMin = cond.range.oneWayMin + config.AGENT_RELAX_MIN
    items = _mark_shown([x for x in fp.filter_places(wide, now, wtext, visited) if not x.get("overEstimate")],
                        shown_set, visited_set)
    if not items:
        return None
    # cond 자체를 넓혔으니 곳마다 relaxed를 달지 않아요 (달면 다시 잴 때 +20분을 한 번 더 해요)
    return items, wide


async def _expand_by_code(cond: Conditions, items: list[dict], pool: list[dict], now, wtext,
                          left, visited) -> tuple[list[dict], Conditions, dict | None]:
    """바람이 목록에 그대로 없으면 AI 한 번으로 말을 넓혀 찾아요 (코드 길)."""
    if not (ex.needs_expand(cond, items) and config.has_ai()) or left(3.0) <= 0.5:
        return pool, cond, None
    words, places = await ex.expand(cond, left(3.0))
    if not (words or places):
        return pool, cond, None
    work_cond = cond.model_copy(deep=True)
    work_cond.extra.expanded = words
    have = {x["place"]["id"] for x in pool}
    found = [x for x in items if not x.get("overEstimate") and x["place"]["id"] not in have
             and any(wd in place_text(x["place"]) for wd in words)]
    search_all = [x for x in items if any(wd in place_text(x["place"]) for wd in words)]
    added = []
    if places:
        added = await map_candidates.resolve(places, work_cond, now, wtext, left(3.0), visited)
        added = [a for a in added if a["place"]["id"] not in have]
        if added:
            measured = await transit.measure_all(added, work_cond, now, min(config.TRANSIT_TIMEOUT, left(3.0)))
            if measured:
                added = measured
    expanded = {"from": ex.wishes_of(cond), "words": words, "places": [a["place"]["name"] for a in added],
                "found": len(search_all) + len(added)}
    return pool + found[:3] + added, work_cond, expanded


async def recommend(cond: Conditions, visited: list[str], shown: list[str] | None = None) -> dict:
    shown_set, visited_set = set(shown or []), set(visited)
    t0 = time.monotonic()
    agent_mode = config.agent_on() and config.has_ai()
    # 에이전트를 쓰면 8초 대신 화면 대기(REC_FAIL 20초) − 1초 안에서 끝내요
    total = config.REC_WAIT - 1.0 if agent_mode else config.RECOMMEND_TOTAL

    def left(margin: float = 0.0) -> float:
        return total - (time.monotonic() - t0) - margin

    def done(res: dict) -> dict:
        # 배포 환경 응답 시간을 재려고 남겨요. 글 · 조건 · 장소는 남기지 않아요
        log.info("recommend by=%s n=%d why=%s %.2fs", res.get("by", "-"), len(res["candidates"]),
                 res.get("why", "-"), time.monotonic() - t0)
        return res

    sync.refresh_in_background()
    now = config.now()
    start = transit.origin_point(cond)
    w = await asyncio.to_thread(weather.current, *(start or (None, None)))
    wtext = w.get("weather")

    items = _mark_shown(fp.filter_places(cond, now, wtext, visited), shown_set, visited_set)
    relaxed = False
    expanded = None
    work_cond = cond
    by = "rule"
    verified: list[dict] = []
    pool: list[dict] = []
    agent_info: dict = {}

    if agent_mode:
        # exp/agent-full: 넓혀 다시 찾기도 에이전트가 해요 (0곳 · 바람과 맞는 곳 없음 → relax_travel · expand_wish)
        from app.recommend.agent.graph import pick_by_agent

        if items:
            pool, _stats = await transit.refine(items, cond, now, min(config.TRANSIT_TIMEOUT, left(3.0)))
        everything = [x for x in items if not x.get("overEstimate")]
        budget = min(config.AGENT_TIMEOUT, left(AGENT_RESERVE))
        r = await pick_by_agent(pool, cond, visited, now, wtext, budget, everything, info=agent_info)
        if r is not None:
            picks, seen = r
            seen_ids = {x["place"]["id"] for x in seen}
            pool = seen + [x for x in pool if x["place"]["id"] not in seen_ids]
            if agent_info.get("expanded"):
                expanded = agent_info["expanded"]
                work_cond = cond.model_copy(deep=True)
                work_cond.extra.expanded = list(expanded.get("words") or [])
            verified = await confirm_by_jev(verify_picks(picks, seen), left(0.5))
            if verified:
                by = "agent"
                # 에이전트의 relax_travel은 곳마다 relaxed를 달아요 (cond는 그대로)
                relaxed = any(v["item"].get("relaxed") for v in verified)
        if by != "agent":
            log.info("추천 에이전트를 못 써서 코드 길로 가요")

    if by != "agent":
        if not items:
            got = _relax(cond, now, wtext, visited, shown_set, visited_set)
            if got:
                items, cond = got
                relaxed = True
                work_cond = cond.model_copy(deep=True)
                if expanded:
                    work_cond.extra.expanded = list(expanded.get("words") or [])
                pool = []
        if items and not pool:
            pool, _stats = await transit.refine(items, cond, now, min(config.TRANSIT_TIMEOUT, left(3.0)))
        # 에이전트 뒤에는 한 번 호출(6초) 자리가 남을 때만 코드로 말을 넓혀요
        if expanded is None and (not agent_mode or left() > config.RECOMMEND_AI_MAX + config.EXPAND_TIMEOUT + 2.0):
            pool, work_cond, expanded = await _expand_by_code(work_cond, items, pool, now, wtext, left, visited)

    external: list[dict] = []
    asked_external = False
    if by == "agent" and len(verified) < config.MAX_CANDIDATES:
        used = {v["item"]["place"]["id"] for v in verified}
        rest = [x for x in pool if x["place"]["id"] not in used and not x.get("overEstimate")]
        verified += pick_by_rule(rest, work_cond, config.MAX_CANDIDATES - len(verified))
    if pool and by != "agent" and not verified:
        # 에이전트 뒤라면 다시 재기 · 정보 붙이기 자리(2.5초)를 남겨요
        picks = await pick_by_ai(pool, work_cond, min(config.RECOMMEND_AI_MAX, left(2.5 if agent_mode else 0.5)))
        if picks is not None:
            by = "ai"
            verified = verify_picks(picks, pool)
            verified = await confirm_by_jev(verified, left(0.5))
            names = []
            for pk in picks:
                n = pk.get("externalName")
                if not pk.get("id") and n and 1 <= len(n) <= 100 and n not in names:
                    names.append(n)
            names = names[:3]
            if names:
                asked_external = True
                ext_items = await map_candidates.resolve(names, work_cond, now, wtext, left(0.5), visited)
                ext = verify_picks([{"id": x["place"]["id"], "reason": rule_reason(x, work_cond)} for x in ext_items],
                                   ext_items)
                have = {v["item"]["place"]["id"] for v in verified}
                external = [e for e in ext if e["item"]["place"]["id"] not in have]
                verified += external
                pool = pool + [e["item"] for e in external]
            if asked_external and len(verified) < config.MAX_CANDIDATES:
                used = {v["item"]["place"]["id"] for v in verified}
                rest = [x for x in pool if x["place"]["id"] not in used and not x.get("overEstimate")]
                if not verified:
                    by = "rule"
                verified += pick_by_rule(rest, work_cond, config.MAX_CANDIDATES - len(verified))
            if not verified:
                by = "rule"
        if by == "rule" and not verified:
            verified = pick_by_rule([x for x in pool if not x.get("overEstimate")], work_cond)

    if not verified:
        return done({"candidates": [], "notFound": True, "why": "none"})

    shown = verified[: config.MAX_CANDIDATES]
    late = time.monotonic() - t0 > total
    if not late:
        shown = await _measure_shown(shown, work_cond, now, min(config.TRANSIT_TIMEOUT, left(1.5)))
    shown = limit_revisits(shown, work_cond)  # 다녀온 곳을 줄였으면 아래에서 새로운 곳으로 채워요
    # 늦었어도 이미 고른 곳은 버리지 않아요: 길 다시 재기 · 정보 붙이기만 건너뛰어요
    if not late and len(shown) < config.MAX_CANDIDATES:
        used = {v["item"]["place"]["id"] for v in shown}
        real = [x for x in pool if x["route"].get("source") in ("tmap", "seoul") and x["place"]["id"] not in used]
        shown += pick_by_rule(real, work_cond, config.MAX_CANDIDATES - len(shown))
    if not late and len(shown) < config.MAX_CANDIDATES and left(2.0) > 1.0 and transit.enabled():
        # 재서 빠진 곳이 있으면, 남은 시간에 규칙 순서로 몇 곳 더 재서 3곳을 채워요 (실측에서 1~2곳만 나온 문제)
        used = {v["item"]["place"]["id"] for v in shown}
        more = [v["item"] for v in pick_by_rule([x for x in pool if x["place"]["id"] not in used
                                                 and not x.get("overEstimate")], work_cond, 6)]
        measured = await transit.measure_all(more, work_cond, now, min(config.TRANSIT_TIMEOUT, left(2.0)))
        shown += pick_by_rule(measured, work_cond, config.MAX_CANDIDATES - len(shown))
    if not shown:
        return done({"candidates": [], "notFound": True, "why": "none"})

    shown = limit_revisits(shown, work_cond)  # 다녀온 곳은 1곳까지, 맨 앞은 새로운 곳
    if by == "agent":
        relaxed = relaxed and any(v["item"].get("relaxed") for v in shown)
    cands = [_candidate(v) for v in shown]
    # 늦었으면 시간 0으로 불러 자료에 있는 기본 정보(사진 · 요금)만 붙여요
    await info.attach(cands, [v["item"] for v in shown], 0 if late else min(config.INFO_TIMEOUT, left(0.3)))
    for c, v in zip(cands, shown):
        _finish(c, v["item"])
    return done({
        "candidates": cands, "notFound": False, "by": by, "weather": w,
        "dataAsOf": places_db.fetched_at(), "expanded": expanded,
        **({"relaxed": True} if relaxed else {}),
    })


async def _measure_shown(shown: list[dict], cond: Conditions, now, budget: float) -> list[dict]:
    todo = [v for v in shown if v["item"]["route"].get("source") not in ("tmap", "seoul")]
    if not todo or budget <= 0.3 or not transit.enabled():
        return shown
    wide = cond.model_copy(deep=True)
    wide.range.oneWayMin = cond.range.oneWayMin + config.AGENT_RELAX_MIN
    plain = [v["item"] for v in todo if not v["item"].get("relaxed")]
    relaxed = [v["item"] for v in todo if v["item"].get("relaxed")]
    a, b = await asyncio.gather(transit.measure_all(plain, cond, now, budget),
                                transit.measure_all(relaxed, wide, now, budget))
    measured = a + [{**m, "relaxed": True} for m in b]
    if not measured:
        # 재지 못했으면 어림 길 그대로 (어림으로 범위 안인 곳만 여기까지 와요)
        return shown
    by_id = {m["place"]["id"]: m for m in measured}
    out = []
    for v in shown:
        pid = v["item"]["place"]["id"]
        if v in todo:
            m = by_id.get(pid)
            if m is None:
                continue
            reason = v["reason"] if check(v["reason"], m) else rule_reason(m, cond)
            out.append({"item": m, "reason": reason})
        else:
            out.append(v)
    return out


def place_open(place_id: str) -> dict | None:
    p = loader.place_by_id(place_id)
    if p is None:
        return None
    oi = fp.open_info(p, config.now())
    return {"open": oi["ok"], "today": oi["today"], "lastEntry": oi.get("lastEntry")}

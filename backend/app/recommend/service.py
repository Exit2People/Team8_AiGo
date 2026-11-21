"""추천 전체 순서: 거르기 → (넓혀 찾기 · 실제 길) → 고르기 → 확인 → 보여 주기 전 다시 재기 → 정보 붙이기.

고르기 사슬: 추천 에이전트(AIGO_AGENT=1, 화면 대기 20초 안에 끝나게 시간을 나눠요) → 실패 · 늦음이면 Claude 한 번(pick_by_ai) → 규칙.
"""

import asyncio
import logging
import time

from app import config
from app.data import filter_places as fp
from app.data import loader, places_db, sync, transit, weather
from app.recommend import expand as ex
from app.recommend import info, map_candidates
from app.recommend.pick import pick_by_ai, pick_by_rule, rule_reason
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


async def recommend(cond: Conditions, visited: list[str]) -> dict:
    t0 = time.monotonic()
    agent_mode = config.agent_on() and config.has_ai()
    # 에이전트를 쓰면 8초 대신 화면 대기(REC_FAIL 20초) − 1초 안에서 끝내요
    total = config.REC_WAIT - 1.0 if agent_mode else config.RECOMMEND_TOTAL

    def left(margin: float = 0.0) -> float:
        return total - (time.monotonic() - t0) - margin

    sync.refresh_in_background()
    now = config.now()
    start = transit.origin_point(cond)
    w = await asyncio.to_thread(weather.current, *(start or (None, None)))
    wtext = w.get("weather")

    items = fp.filter_places(cond, now, wtext, visited)
    relaxed = False
    if not items:
        wide = cond.model_copy(deep=True)
        wide.range.oneWayMin = cond.range.oneWayMin + config.AGENT_RELAX_MIN
        items = [x for x in fp.filter_places(wide, now, wtext, visited) if not x.get("overEstimate")]
        if items:
            relaxed = True
            for x in items:
                x["relaxed"] = True
            cond = wide

    expanded = None
    work_cond = cond
    do_expand = ex.needs_expand(cond, items) and config.has_ai()
    refine_task = transit.refine(items, cond, now, min(config.TRANSIT_TIMEOUT, left(3.0)))
    if do_expand:
        (pool, _stats), (words, places) = await asyncio.gather(refine_task, ex.expand(cond, left(3.0)))
    else:
        pool, _stats = await refine_task
        words, places = [], []
    if words or places:
        work_cond = cond.model_copy(deep=True)
        work_cond.extra.expanded = words
        have = {x["place"]["id"] for x in pool}
        found = [x for x in items if not x.get("overEstimate") and x["place"]["id"] not in have
                 and any(wd in place_text(x["place"]) for wd in words)]
        search_all = [x for x in items if any(wd in place_text(x["place"]) for wd in words)]
        added = []
        if places:
            added = await map_candidates.resolve(places, work_cond, now, wtext, left(3.0))
            added = [a for a in added if a["place"]["id"] not in have]
            if added:
                measured = await transit.measure_all(added, work_cond, now, min(config.TRANSIT_TIMEOUT, left(3.0)))
                if measured:
                    added = measured
        pool = pool + found[:3] + added
        expanded = {"from": ex.wishes_of(cond), "words": words, "places": [a["place"]["name"] for a in added],
                    "found": len(search_all) + len(added)}

    by = "rule"
    verified: list[dict] = []
    external: list[dict] = []
    asked_external = False
    if agent_mode:
        from app.recommend.agent.graph import pick_by_agent

        everything = [x for x in items if not x.get("overEstimate")]
        budget = min(config.AGENT_TIMEOUT, left(AGENT_RESERVE))
        r = await pick_by_agent(pool, work_cond, visited, now, wtext, budget, everything)
        if r is not None:
            by = "agent"
            picks, seen = r
            seen_ids = {x["place"]["id"] for x in seen}
            pool = seen + [x for x in pool if x["place"]["id"] not in seen_ids]
            verified = await confirm_by_jev(verify_picks(picks, seen))
            if len(verified) < config.MAX_CANDIDATES:
                used = {v["item"]["place"]["id"] for v in verified}
                rest = [x for x in pool if x["place"]["id"] not in used and not x.get("overEstimate")]
                if not verified:
                    by = "rule"
                verified += pick_by_rule(rest, work_cond, config.MAX_CANDIDATES - len(verified))
    if pool and by != "agent" and not verified:
        picks = await pick_by_ai(pool, work_cond, min(config.RECOMMEND_AI_MAX, left(0.5)))
        if picks is not None:
            by = "ai"
            verified = verify_picks(picks, pool)
            verified = await confirm_by_jev(verified)
            names = []
            for pk in picks:
                n = pk.get("externalName")
                if not pk.get("id") and n and 1 <= len(n) <= 100 and n not in names:
                    names.append(n)
            names = names[:3]
            if names:
                asked_external = True
                ext_items = await map_candidates.resolve(names, work_cond, now, wtext, left(0.5))
                ext = verify_picks([{"id": x["place"]["id"], "reason": map_candidates.REASON} for x in ext_items],
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
        return {"candidates": [], "notFound": True, "why": "none"}
    if time.monotonic() - t0 > total:
        return {"candidates": [], "notFound": True, "why": "timeout"}

    shown = verified[: config.MAX_CANDIDATES]
    shown = await _measure_shown(shown, work_cond, now, min(config.TRANSIT_TIMEOUT, left(1.5)))
    if len(shown) < config.MAX_CANDIDATES:
        used = {v["item"]["place"]["id"] for v in shown}
        real = [x for x in pool if x["route"].get("source") in ("tmap", "seoul") and x["place"]["id"] not in used]
        shown += pick_by_rule(real, work_cond, config.MAX_CANDIDATES - len(shown))
    if not shown:
        return {"candidates": [], "notFound": True, "why": "none"}

    cands = [_candidate(v) for v in shown]
    await info.attach(cands, [v["item"] for v in shown], min(config.INFO_TIMEOUT, left(0.3)))
    for c, v in zip(cands, shown):
        _finish(c, v["item"])
    return {
        "candidates": cands, "notFound": False, "by": by, "weather": w,
        "dataAsOf": places_db.fetched_at(), "expanded": expanded,
        **({"relaxed": True} if relaxed else {}),
    }


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

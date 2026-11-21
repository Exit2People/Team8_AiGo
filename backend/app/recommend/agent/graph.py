"""추천 에이전트 그래프: search_places · count_places · relax_travel · expand_wish · get_route · get_visit_history
· submit_picks. 도구 6번.

exp/agent-full: "조건 넓혀 다시 찾기 + 고르기". 넓혔으면 info["relaxed"] · info["expanded"]로 알려 줘요.
"""

import logging
import time

from app import config
from app.recommend.agent import memory, tools
from app.recommend.agent.tools import AgentContext
from app.schemas import Conditions, strip_for_ai

log = logging.getLogger("aigo.recommend.agent")

# 06_AI_PROMPTS 0절은 effort를 넘기지 않지만(기본 high), 화면 대기 20초 안에 끝나야 해서 low로 둬요 (docs/LANE_NOTES_BE.md)
EFFORT = "low"


def widen_hint(ctx: AgentContext) -> str | None:
    base = ctx.everything or ctx.items
    if not base:
        return "고른 이동 범위 안에 오늘 갈 곳이 0곳이에요. relax_travel 로 넓혀 다시 찾아 주세요."
    if ctx.wishes() and not ctx.wish_hits(base):
        return (f"어르신이 바란 것({', '.join(ctx.wishes())})과 맞는 곳이 고른 범위 안에 없어요. "
                "expand_wish(바람을 다른 말로) · relax_travel(이동 범위) 중 맞는 것으로 넓혀 다시 찾아 주세요.")
    return None


async def pick_by_agent(items: list[dict], cond: Conditions, visited: list[str], now, weather: str | None,
                        timeout: float, everything: list[dict],
                        info: dict | None = None) -> tuple[list[dict], list[dict]] | None:
    """(고른 곳 [{id, reason}] 앞 3곳, 에이전트에 보여 준 곳). 실패 · 늦음은 None, 제출 없음은 빈 목록.

    info 를 주면 {"relaxed": bool, "expanded": dict | None, "tools": [..]} 를 채워요.
    """
    from app.llm import agent_loop
    from app.recommend.prompts import AGENT_SYSTEM

    if not config.has_ai() or timeout <= 0:
        return None
    ctx = AgentContext(cond=cond, now=now, weather=weather, visited=list(visited), items=list(items),
                       everything=list(everything), deadline=time.monotonic() + timeout)
    fns = {
        "search_places": lambda **kw: tools.search_places(ctx, **kw),
        "count_places": lambda **kw: tools.count_places(ctx, **kw),
        "relax_travel": lambda **kw: tools.relax_travel(ctx),
        "expand_wish": lambda **kw: tools.expand_wish(ctx),
        "get_route": lambda **kw: tools.get_route(ctx, **kw),
        "get_visit_history": lambda **kw: tools.get_visit_history(ctx, **kw),
        "submit_picks": lambda **kw: {"ok": True},
    }
    first = {"조건": strip_for_ai(cond), "지금": now.strftime("%Y-%m-%d %H:%M"), "날씨": weather,
             "다녀온 곳 요약": memory.profile_text(visited),
             "곳 수": tools.count_places(ctx)}
    hint = widen_hint(ctx)
    if hint:
        first["넓혀 찾기"] = hint
    res = await agent_loop.run(AGENT_SYSTEM, first, fns, tools.SCHEMAS, "submit_picks", config.AGENT_MAX_ROUNDS,
                               timeout, config.model(), 4000, EFFORT, name="추천 에이전트")
    if info is not None:
        info["relaxed"] = ctx.relaxed_used
        info["expanded"] = ctx.expanded if ctx.expanded and ctx.expanded.get("words") else None
        info["tools"] = list(ctx.log)
    if res is None:
        return None
    picks = []
    sub = res.get("submitted") or {}
    for pk in (sub.get("picks") or [])[: config.MAX_CANDIDATES]:
        if isinstance(pk, dict):
            picks.append({"id": str(pk.get("id") or "").strip(), "reason": str(pk.get("reason") or "").strip()})
    log.info("추천 에이전트: 고른 곳 %s, 넓힘 %s", len(picks), "; ".join(ctx.log) or "없음")
    return picks, list(ctx.pool.values())

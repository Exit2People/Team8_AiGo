"""추천 에이전트 그래프: search_places · get_route · get_visit_history · submit_picks. 도구 6번."""

import logging

from app import config
from app.recommend.agent import memory, tools
from app.recommend.agent.tools import AgentContext
from app.schemas import Conditions, strip_for_ai

log = logging.getLogger("aigo.recommend.agent")

# 06_AI_PROMPTS 0절은 effort를 넘기지 않지만(기본 high), 화면 대기 20초 안에 끝나야 해서 low로 둬요 (docs/LANE_NOTES_BE.md)
EFFORT = "low"


async def pick_by_agent(items: list[dict], cond: Conditions, visited: list[str], now, weather: str | None,
                        timeout: float, everything: list[dict]) -> tuple[list[dict], list[dict]] | None:
    """(고른 곳 [{id, reason}] 앞 3곳, 에이전트에 보여 준 곳). 실패 · 늦음은 None, 제출 없음은 빈 목록."""
    from app.llm import agent_loop
    from app.recommend.prompts import AGENT_SYSTEM

    if not config.has_ai() or timeout <= 0:
        return None
    ctx = AgentContext(cond=cond, now=now, weather=weather, visited=list(visited), items=list(items),
                       everything=list(everything))
    fns = {
        "search_places": lambda **kw: tools.search_places(ctx, **kw),
        "get_route": lambda **kw: tools.get_route(ctx, **kw),
        "get_visit_history": lambda **kw: tools.get_visit_history(ctx, **kw),
        "submit_picks": lambda **kw: {"ok": True},
    }
    first = {"조건": strip_for_ai(cond), "지금": now.strftime("%Y-%m-%d %H:%M"), "날씨": weather,
             "다녀온 곳 요약": memory.profile_text(visited)}
    res = await agent_loop.run(AGENT_SYSTEM, first, fns, tools.SCHEMAS, "submit_picks", config.AGENT_MAX_ROUNDS,
                               timeout, config.model(), 4000, EFFORT, name="추천 에이전트")
    if res is None:
        return None
    picks = []
    sub = res.get("submitted") or {}
    for pk in (sub.get("picks") or [])[: config.MAX_CANDIDATES]:
        if isinstance(pk, dict):
            picks.append({"id": str(pk.get("id") or "").strip(), "reason": str(pk.get("reason") or "").strip()})
    log.info("추천 에이전트: 고른 곳 %s", len(picks))
    return picks, list(ctx.pool.values())

"""추천 에이전트 도구. 요청 한 번 동안만 쓰는 AgentContext 위에서 돌아요."""

from dataclasses import dataclass, field
from datetime import datetime

from app import config
from app.data.filter_places import filter_places
from app.question.search import place_scores
from app.question.themes import ALL_THEMES, wish_themes
from app.recommend.agent import memory
from app.recommend.pick import for_ai, rank_by_rule
from app.schemas import Conditions

SEARCH_MAX = 3
FOUND_MAX = 8
KINDS = ["공원", "행사", "시장", "박물관", "미술관"]
E_WORD = "낱말은 2~40자로 주세요 (숲 · 산 같은 한 글자 주제는 돼요)"
E_RELAX = "고른 범위 안에 갈 곳이 있어요. relax_travel 은 search_places 목록이 비었을 때만 써요"
E_MAX = "이미 3번 찾았어요. 지금까지 받은 곳에서 골라 submit_picks 를 불러 줘"
E_ROUTE = "search_places 가 준 곳의 id만 쓸 수 있어요"

SCHEMAS = [
    {"name": "search_places",
     "description": "오늘 갈 수 있는 곳을 받아요. 아무것도 안 주면 고른 20곳, word · kind 면 오늘 갈 수 있는 곳 전부에서 찾아요.",
     "input_schema": {"type": "object", "properties": {
         "word": {"type": "string", "description": "2~40자 낱말 (숲 · 산 같은 한 글자 주제는 돼요)"},
         "kind": {"type": "string", "enum": KINDS},
         "relax_travel": {"type": "boolean", "description": "목록이 비었을 때만, 편도 상한을 20분 늘려 다시 찾기"}}}},
    {"name": "get_route", "description": "search_places 가 준 곳의 길을 봐요.",
     "input_schema": {"type": "object", "properties": {"place_id": {"type": "string"}}, "required": ["place_id"]}},
    {"name": "get_visit_history", "description": "최근 다녀온 곳 (이름 · 종류 · 구).",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}}}},
    {"name": "submit_picks", "description": "고른 곳(최대 3)을 내고 끝내요.",
     "input_schema": {"type": "object", "properties": {"picks": {"type": "array", "maxItems": 3, "items": {
         "type": "object", "properties": {"id": {"type": "string"}, "reason": {"type": "string"}},
         "required": ["id", "reason"]}}}, "required": ["picks"]}},
]


@dataclass
class AgentContext:
    cond: Conditions
    now: datetime
    weather: str | None
    visited: list[str]
    items: list[dict]
    everything: list[dict]
    pool: dict[str, dict] = field(default_factory=dict)
    searches: int = 0

    def item_ids(self) -> set[str]:
        return {x["place"]["id"] for x in self.items}

    def relaxed_cond(self) -> Conditions:
        c = self.cond.model_copy(deep=True)
        c.range.oneWayMin = self.cond.range.oneWayMin + config.AGENT_RELAX_MIN
        return c

    def relaxed(self) -> list[dict]:
        out = []
        for x in filter_places(self.relaxed_cond(), self.now, self.weather, self.visited):
            if x.get("overEstimate"):
                continue
            out.append({**x, "relaxed": True})
        return out


def search_places(ctx: AgentContext, word: str | None = None, kind: str | None = None,
                  relax_travel: bool = False) -> list[dict] | dict:
    word = (word or "").strip() or None
    if word and not (2 <= len(word) <= 40) and not (wish_themes(word) or word in ALL_THEMES):
        return {"error": E_WORD}
    if relax_travel and (ctx.items or config.AGENT_RELAX_MIN <= 0):
        return {"error": E_RELAX}
    if kind is not None and kind not in KINDS:
        raise ValueError("kind")
    if word or kind:
        if ctx.searches >= SEARCH_MAX:
            return {"error": E_MAX}
        ctx.searches += 1
    if relax_travel:
        source = ctx.relaxed()
    elif word or kind:
        source = ctx.everything or ctx.items
    else:
        source = ctx.items
    if kind:
        source = [x for x in source if x["place"].get("kind") == kind]
    scores: dict[str, float] = {}
    if word:
        ranked = place_scores(source, word)
        source = [x for x, _ in ranked]
        scores = {x["place"]["id"]: s for x, s in ranked}
    elif kind and not relax_travel:
        source = rank_by_rule(source, ctx.cond)
    if word or (kind and not relax_travel):
        source = source[:FOUND_MAX]
    inside = ctx.item_ids() | {x["place"]["id"] for x in ctx.everything}
    out = []
    for x in source:
        pid = x["place"]["id"]
        x = ctx.pool.get(pid) or next((i for i in ctx.items if i["place"]["id"] == pid), None) or x
        ctx.pool[pid] = x
        d = for_ai(x)
        if pid not in inside:
            d["이동 범위"] = "고른 범위보다 멀어요"
        if pid in scores:
            d["찾은 점수"] = round(scores[pid], 1)
        out.append(d)
    return out


def get_route(ctx: AgentContext, place_id: str) -> dict:
    x = ctx.pool.get(place_id)
    if not x:
        return {"error": E_ROUTE}
    return x["route"]


def get_visit_history(ctx: AgentContext, limit: int = 10) -> list[dict]:
    limit = max(1, min(30, int(limit)))
    return memory.history(ctx.visited, limit)

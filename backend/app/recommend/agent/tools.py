"""추천 에이전트 도구. 요청 한 번 동안만 쓰는 AgentContext 위에서 돌아요.

exp/agent-full: 에이전트 일을 "조건 넓혀 다시 찾기 + 고르기"로 키웠어요.
- search_places: 오늘 갈 수 있는 곳 (고른 20곳 · 낱말 · 종류)
- count_places: 찾기 전에 곳 수만 세기 (찾기 횟수를 쓰지 않아요)
- relax_travel: 이동 범위(편도 상한)를 +20분 넓혀 다시 찾기 — 0곳이거나 바람과 맞는 곳이 없을 때만
- expand_wish: 바람을 다른 말로 넓혀 다시 찾기 (recommend/expand.py의 일) — 바람과 맞는 곳이 없을 때만
- get_route · get_visit_history · submit_picks
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app import config
from app.data.filter_places import filter_places
from app.question.search import place_scores
from app.question.themes import ALL_THEMES, wish_themes
from app.recommend.agent import memory
from app.recommend.pick import for_ai, rank_by_rule
from app.recommend.wish import matched_wish, matches_place, place_text
from app.schemas import Conditions

SEARCH_MAX = 3
FOUND_MAX = 8
KINDS = ["공원", "행사", "시장", "박물관", "미술관"]
E_WORD = "낱말은 2~40자로 주세요 (숲 · 산 같은 한 글자 주제는 돼요)"
E_RELAX = "고른 범위 안에 바람과 맞는 곳이 있어요. relax_travel 은 갈 곳이 0곳이거나 바람과 맞는 곳이 없을 때만 써요"
E_RELAX_TWICE = "이동 범위는 이미 한 번 넓혔어요"
E_EXPAND = "바란 것(가고 싶은 곳 · 하고 싶은 일)이 없거나, 이미 바람과 맞는 곳이 있어요"
E_EXPAND_TWICE = "바람은 이미 한 번 넓혔어요"
E_EXPAND_FAIL = "넓힐 말을 찾지 못했어요. 받은 곳에서 골라 주세요"
E_MAX = "이미 3번 찾았어요. 지금까지 받은 곳에서 골라 submit_picks 를 불러 줘"
E_ROUTE = "search_places 가 준 곳의 id만 쓸 수 있어요"

_RELAX_PROP = {"type": "boolean", "description": "목록이 비었을 때만, 편도 상한을 20분 늘려 다시 찾기 (relax_travel 도구와 같아요)"}

SCHEMAS = [
    {"name": "search_places",
     "description": "오늘 갈 수 있는 곳을 받아요. 아무것도 안 주면 고른 20곳, word · kind 면 오늘 갈 수 있는 곳 전부에서 찾아요.",
     "input_schema": {"type": "object", "properties": {
         "word": {"type": "string", "description": "2~40자 낱말 (숲 · 산 같은 한 글자 주제는 돼요)"},
         "kind": {"type": "string", "enum": KINDS},
         "relax_travel": _RELAX_PROP}}},
    {"name": "count_places",
     "description": "곳 수만 세요 (찾기 횟수를 쓰지 않아요). 오늘 갈 수 있는 곳 · 바람과 맞는 곳 · 이 말로 찾은 곳 · 넓히면 늘어나는 곳.",
     "input_schema": {"type": "object", "properties": {
         "word": {"type": "string", "description": "세어 볼 낱말 (없어도 돼요)"}}}},
    {"name": "relax_travel",
     "description": "이동 범위(편도 상한)를 20분 넓혀 다시 찾아요. 갈 곳이 0곳이거나 바람과 맞는 곳이 없을 때 한 번만. "
                    "넓혀 찾은 곳에는 '이동 범위' 표시가 붙어요.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "expand_wish",
     "description": "어르신의 바람(예: 공룡)을 장소 이름에 들어 있을 말(예: 자연사, 화석)로 넓혀 다시 찾아요. "
                    "바람과 맞는 곳이 없을 때 한 번만. 몇 초 걸려요.",
     "input_schema": {"type": "object", "properties": {}}},
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
    deadline: float | None = None
    relaxed_used: bool = False
    relaxed_items: list[dict] | None = None
    expanded: dict | None = None
    expanded_words: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def item_ids(self) -> set[str]:
        return {x["place"]["id"] for x in self.items}

    def relaxed_cond(self) -> Conditions:
        c = self.cond.model_copy(deep=True)
        c.range.oneWayMin = self.cond.range.oneWayMin + config.AGENT_RELAX_MIN
        return c

    def relaxed(self) -> list[dict]:
        if self.relaxed_items is None:
            out = []
            for x in filter_places(self.relaxed_cond(), self.now, self.weather, self.visited):
                if x.get("overEstimate"):
                    continue
                out.append({**x, "relaxed": True})
            self.relaxed_items = out
        return self.relaxed_items

    def wishes(self) -> list[str]:
        return [x for x in [self.cond.extra.place, *self.cond.extra.wish] if x]

    def wish_hits(self, items: list[dict]) -> list[dict]:
        ws = self.cond.extra.wish
        place = self.cond.extra.place
        return [x for x in items if matches_place(x["place"], place) or matched_wish(x["place"], ws)]

    def all_now(self) -> list[dict]:
        """지금 찾을 수 있는 곳 전부 (넓혔으면 넓힌 곳까지)."""
        base = self.everything or self.items
        if not self.relaxed_used:
            return base
        have = {x["place"]["id"] for x in base}
        return base + [x for x in self.relaxed() if x["place"]["id"] not in have]

    def can_widen(self) -> bool:
        """규칙만으로 0곳이거나, 바람이 있는데 바람과 맞는 곳이 없을 때."""
        if not (self.everything or self.items):
            return True
        return bool(self.wishes()) and not self.wish_hits(self.everything or self.items)

    def left(self) -> float:
        return 99.0 if self.deadline is None else self.deadline - time.monotonic()


def _show(ctx: AgentContext, source: list[dict], scores: dict[str, float] | None = None) -> list[dict]:
    inside = ctx.item_ids() | {x["place"]["id"] for x in ctx.everything}
    out = []
    for x in source:
        pid = x["place"]["id"]
        x = ctx.pool.get(pid) or next((i for i in ctx.items if i["place"]["id"] == pid), None) or x
        ctx.pool[pid] = x
        d = for_ai(x)
        if pid not in inside or x.get("relaxed"):
            d["이동 범위"] = "고른 범위보다 멀어요"
        if scores and pid in scores:
            d["찾은 점수"] = round(scores[pid], 1)
        out.append(d)
    return out


def search_places(ctx: AgentContext, word: str | None = None, kind: str | None = None,
                  relax_travel: bool = False) -> list[dict] | dict:
    word = (word or "").strip() or None
    if word and not (2 <= len(word) <= 40) and not (wish_themes(word) or word in ALL_THEMES):
        return {"error": E_WORD}
    if relax_travel:
        if ctx.items or config.AGENT_RELAX_MIN <= 0:
            return {"error": E_RELAX}
        ctx.relaxed_used = True
    if kind is not None and kind not in KINDS:
        raise ValueError("kind")
    if word or kind:
        if ctx.searches >= SEARCH_MAX:
            return {"error": E_MAX}
        ctx.searches += 1
    if relax_travel:
        source = ctx.relaxed()
    elif word or kind:
        source = ctx.all_now()
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
    return _show(ctx, source, scores)


def count_places(ctx: AgentContext, word: str | None = None) -> dict:
    base = ctx.everything or ctx.items
    out: dict[str, Any] = {"오늘 갈 수 있는 곳": len(base)}
    if ctx.wishes():
        out["바람과 맞는 곳"] = len(ctx.wish_hits(base))
    word = (word or "").strip()
    if word and 1 <= len(word) <= 40:
        out[f"'{word}'(으)로 찾은 곳"] = len(place_scores(ctx.all_now(), word))
    if ctx.can_widen() and not ctx.relaxed_used and config.AGENT_RELAX_MIN > 0:
        wide = ctx.relaxed()
        out["이동 범위를 넓히면 갈 수 있는 곳"] = len(wide)
        if ctx.wishes():
            out["넓히면 바람과 맞는 곳"] = len(ctx.wish_hits(wide))
    if ctx.expanded_words:
        out["넓힌 말로 찾은 곳"] = len([x for x in ctx.all_now()
                                   if any(w in place_text(x["place"]) for w in ctx.expanded_words)])
    return out


def relax_travel(ctx: AgentContext) -> list[dict] | dict:
    if config.AGENT_RELAX_MIN <= 0 or not ctx.can_widen():
        return {"error": E_RELAX}
    if ctx.relaxed_used:
        return {"error": E_RELAX_TWICE}
    ctx.relaxed_used = True
    wide = ctx.relaxed()
    have = {x["place"]["id"] for x in (ctx.everything or ctx.items)}
    new = [x for x in wide if x["place"]["id"] not in have]
    hits = ctx.wish_hits(new) if ctx.wishes() else []
    ranked = hits + [x for x in rank_by_rule(new, ctx.cond) if x not in hits]
    ctx.log.append(f"이동 범위 +{config.AGENT_RELAX_MIN}분: {len(new)}곳 더")
    return _show(ctx, ranked[:FOUND_MAX])


async def expand_wish(ctx: AgentContext) -> list[dict] | dict:
    from app.recommend import expand as ex
    from app.recommend import map_candidates

    if not ctx.wishes() or not ctx.can_widen():
        return {"error": E_EXPAND}
    if ctx.expanded is not None:
        return {"error": E_EXPAND_TWICE}
    budget = min(config.EXPAND_TIMEOUT, ctx.left() - 3.0)
    ctx.expanded = {"from": ctx.wishes(), "words": [], "places": [], "found": 0}
    if budget <= 0.5:
        return {"error": E_EXPAND_FAIL}
    words, places = await ex.expand(ctx.cond, budget)
    ctx.expanded_words = words
    ctx.expanded["words"] = words
    found = [x for x in ctx.all_now() if any(w in place_text(x["place"]) for w in words)] if words else []
    added: list[dict] = []
    if places and ctx.left() > 4.0:
        wide = ctx.cond.model_copy(deep=True)
        wide.extra.expanded = words
        got = await map_candidates.resolve(places, wide, ctx.now, ctx.weather, min(2.0, ctx.left() - 3.0))
        have = {x["place"]["id"] for x in found}
        added = [a for a in got if a["place"]["id"] not in have]
    ctx.expanded["places"] = [a["place"]["name"] for a in added]
    ctx.expanded["found"] = len(found) + len(added)
    ctx.log.append(f"바람 넓힘: 말 {len(words)}개, 찾은 곳 {len(found) + len(added)}")
    if not found and not added:
        return {"넓힌 말": words, "찾은 곳": [], "안내": E_EXPAND_FAIL}
    return {"넓힌 말": words, "찾은 곳": _show(ctx, (found[:FOUND_MAX - len(added[:3])] + added[:3]))}


def get_route(ctx: AgentContext, place_id: str) -> dict:
    x = ctx.pool.get(place_id)
    if not x:
        return {"error": E_ROUTE}
    return x["route"]


def get_visit_history(ctx: AgentContext, limit: int = 10) -> list[dict]:
    limit = max(1, min(30, int(limit)))
    return memory.history(ctx.visited, limit)

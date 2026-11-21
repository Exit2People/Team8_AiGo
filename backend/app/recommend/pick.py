"""AI 한 번 고르기 · 규칙 점수 · 종류별 고루 뽑기 · 규칙 이유 문구 (04_CONSTANTS 8절)."""

import math

from app import config
from app.recommend.wish import exact_place, matched_wish, matches_place, matches_who, place_text
from app.schemas import Conditions, strip_for_ai, want_of

FIT_TURN = 3
MUSEUM_SCORE = {"국립": 2.5, "서울시립": 2.0, "큰 사립 · 재단": 2.0, "구립 · 공공": 1.0, "대학": 0.5}


def food_score(p: dict) -> float:
    n = int((p.get("market") or {}).get("food") or 0)
    return min(2.5, math.log2(1 + n) / 2)


def museum_score(p: dict) -> float:
    return MUSEUM_SCORE.get((p.get("museum") or {}).get("operator") or "", 0.0)


def rule_score(item: dict, cond: Conditions) -> float:
    from app.question.flow import answer_themes
    from app.question.lead import lead_bonus
    from app.question.themes import themes_of

    p = item["place"]
    r = item["route"]
    s = lead_bonus(p, cond)
    if answer_themes(cond) & themes_of(p):
        s += 2.5
    want = want_of(cond)
    wants = p.get("wants") or []
    if want and want in wants:
        s += 3
        if wants and wants[0] == want:
            s += 1
        if want == "맛있는 것":
            s += food_score(p)
    if not want or want in wants:
        s += museum_score(p)
    io = cond.basic.inout
    if (io == "실내가 좋아요" and p.get("inout") == "실내") or (io == "바깥이 좋아요" and p.get("inout") == "바깥"):
        s += 2
    said = " ".join([*(x.a or "" for x in cond.ai), *cond.extra.wish])
    for m in p.get("mood") or []:
        first = m.split()[0] if m.split() else m
        if first and first in said:
            s += 1
    if matches_place(p, cond.extra.place):
        s += 5
        if cond.extra.place.replace(" ", "") in (p.get("name") or "").replace(" ", ""):
            s += 2  # 이름이 딱 맞는 곳(서울숲)을 '그 근처'(서울숲역 옆 박물관)보다 앞에
    elif item.get("visited"):
        s -= config.VISITED_PENALTY  # 다녀온 곳은 조금 뒤로 (직접 말한 곳이면 깎지 않아요)
    elif item.get("shownRecent"):
        s -= config.SHOWN_PENALTY  # 보여 줬는데 고르지 않은 곳은 조금 더 뒤로
    wishes = list(cond.extra.wish)
    if matched_wish(p, wishes):
        s += 3
    elif cond.extra.expanded and any(e in place_text(p) for e in cond.extra.expanded):
        s += 1
    if matches_who(p, cond.extra.who):
        s += 2
    s -= r.get("transfers", 0)
    s -= r.get("totalMin", 0) / 20
    return s


def daily_jitter(pid: str | None) -> float:
    """날짜와 장소로 정해지는 작은 값(±DAILY_JITTER/2). 같은 날엔 늘 같고, 날이 바뀌면 달라져요."""
    import hashlib

    day = config.now().strftime("%Y-%m-%d")
    h = int(hashlib.md5(f"{day}:{pid}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return (h - 0.5) * config.DAILY_JITTER


def rank_by_rule(items: list[dict], cond: Conditions) -> list[dict]:
    # 점수가 비슷한 곳끼리만 날마다 순서가 바뀌어요 (같은 답이면 매일 같은 목록이 되지 않게)
    return sorted(items, key=lambda it: (
        not exact_place(it["place"], cond.extra.place),
        -(rule_score(it, cond) + daily_jitter(it["place"].get("id"))),
    ))


def diverse_pool(items: list[dict], cond: Conditions, n: int = config.AI_POOL) -> list[dict]:
    ranked = rank_by_rule(items, cond)
    buckets: dict[str, list[dict]] = {}
    for it in ranked:
        buckets.setdefault(it["place"].get("kind") or "", []).append(it)
    want = want_of(cond)
    out: list[dict] = []
    while len(out) < n and any(buckets.values()):
        for kind, b in buckets.items():
            if not b:
                continue
            turn = FIT_TURN if want and want in (b[0]["place"].get("wants") or []) else 1
            for _ in range(turn):
                if b and len(out) < n:
                    out.append(b.pop(0))
    return out


def ride_phrase(r: dict) -> str:
    legs = r.get("legs") or []
    if not any(lg.get("kind") != "하차" for lg in legs):
        return "역에서 바로 걸어가요"
    t, total = r.get("transfers", 0), r.get("totalMin", 0)
    if t == 0:
        return f"갈아타지 않고 {total}분이면 가요"
    if t == 1:
        return f"한 번만 갈아타고 {total}분이면 가요"
    return f"{t}번 갈아타고 {total}분이면 가요"


# "맛있는 것 좋은 곳이에요"처럼 어색한 말을 자연스럽게 바꿔요
_WANT_HEAD = {"맛있는 것": "먹을 것이 있는 곳이에요."}


def rule_reason(item: dict, cond: Conditions) -> str:
    p = item["place"]
    want = want_of(cond)
    wants = p.get("wants") or []
    w = matched_wish(p, list(cond.extra.wish))
    if matches_place(p, cond.extra.place):
        head = f"말씀하신 {cond.extra.place} 쪽이에요."
    elif w:
        head = f"{w}에 어울리는 곳이에요."
    elif cond.extra.who == "손주" and matches_who(p, "손주"):
        head = "손주와 가기 좋은 곳이에요."
    elif want == "맛있는 것" and int((p.get("market") or {}).get("food") or 0) >= 10:
        head = "시장 안팎에 먹을 곳이 많아요."
    elif want and want in wants:
        head = _WANT_HEAD.get(want, f"{want} 좋은 곳이에요.")
    elif wants:
        head = _WANT_HEAD.get(wants[0], f"{wants[0]} 좋은 곳이에요.")
    else:
        head = "가 볼 만한 곳이에요."
    return f"{head} {ride_phrase(item['route'])}"


def limit_revisits(picks: list[dict], cond: Conditions) -> list[dict]:
    """다녀온 곳은 MAX_VISITED_SHOWN 곳까지, 맨 앞에는 두지 않아요. 어르신이 직접 말한 곳이면 그대로 둬요.
    새로운 곳이 하나도 없으면 다녀온 곳만으로 채워요 ('찾지 못했어요'보다 나아요)."""
    def revisit(v: dict) -> bool:
        it = v["item"]
        return bool(it.get("visited")) and not matches_place(it["place"], cond.extra.place)

    fresh = [v for v in picks if not revisit(v)]
    again = [v for v in picks if revisit(v)][: config.MAX_VISITED_SHOWN]
    if not fresh:
        return picks[: config.MAX_CANDIDATES]  # 새로운 곳이 없으면 다녀온 곳이라도 3곳까지
    return fresh[:1] + again + fresh[1:] if again else fresh


def pick_by_rule(items: list[dict], cond: Conditions, n: int = config.MAX_CANDIDATES) -> list[dict]:
    ranked = rank_by_rule(items, cond)
    chosen: list[dict] = []
    kinds: set[str] = set()
    for it in ranked:
        k = it["place"].get("kind") or ""
        if k not in kinds:
            chosen.append(it)
            kinds.add(k)
        if len(chosen) == n:
            break
    for it in ranked:
        if len(chosen) == n:
            break
        if it not in chosen:
            chosen.append(it)
    # 익숙한 곳 한 자리: 다녀온 곳이 하나도 안 들었으면, 잘 맞는 다녀온 곳을 마지막 자리에 넣어요
    if len(chosen) >= 2 and not any(it.get("visited") for it in chosen):
        best = next((it for it in ranked if it.get("visited") and it not in chosen), None)
        if best is not None and rule_score(best, cond) >= rule_score(chosen[-1], cond) - config.REVISIT_MARGIN:
            chosen[-1] = best
    return [{"item": it, "reason": rule_reason(it, cond)} for it in chosen]


def for_ai(item: dict) -> dict:
    p, r = item["place"], item["route"]
    measured = r.get("source") in ("tmap", "seoul")
    last = next((lg for lg in r.get("legs") or [] if lg.get("kind") == "하차"), {})
    d = {
        "id": p.get("id"), "이름": p.get("name"), "종류": p.get("kind"), "구": p.get("gu"),
        "실내 · 바깥": p.get("inout"), "하기 좋은 것": p.get("wants") or [], "분위기": p.get("mood") or [],
        "걸리는 시간(분)": r.get("totalMin"), "갈아타는 횟수": r.get("transfers"),
        "출구에서 걷는 시간(분)": last.get("walkMin", p.get("walkMin")),
        "오늘 운영": (item.get("open") or {}).get("today"),
        "길": "실제로 잰 길" if measured else "어림 길 (실제와 다를 수 있어요)",
    }
    if item.get("visited"):
        d["다녀온 곳"] = "최근 30일 안에 다녀왔어요"
    elif item.get("shownRecent"):
        d["최근에 보여 준 곳"] = "며칠 안에 추천했지만 고르지 않았어요"
    if item.get("relaxed"):
        # 에이전트가 범위를 넓혀 찾은 곳이 한 번 호출(PICK)로 넘어올 때도 멀다는 걸 알려요
        d["이동 범위"] = "고른 범위보다 멀어요. 이유에 걸리는 시간을 꼭 적어요"
    if measured:
        rides = [lg.get("line") for lg in r.get("legs") or [] if lg.get("kind") != "하차" and lg.get("line")]
        if rides:
            d["타는 것"] = rides
    fee = (p.get("info") or {}).get("fee") or {}
    if fee.get("free") is True:
        d["요금"] = "무료"
    elif fee.get("free") is False:
        d["요금"] = "유료"
    if fee.get("text") and fee.get("text") != "무료":
        d["요금 안내"] = fee["text"][:60]
    if p.get("market"):
        m = p["market"]
        d["시장"] = {"먹을 곳(시장 이름이 붙은 가게) 수": m.get("food"), "점포 수": m.get("stores"), "모양": m.get("shape")}
    if p.get("museum"):
        d["쉬는 날"] = (p["museum"].get("closedText") or "")[:60]
        d["운영"] = p["museum"].get("operator")
    if p.get("event"):
        ev = p["event"]
        d["행사"] = {"장소": ev.get("venue"), "기간": f"{ev.get('start')}~{ev.get('end')}", "시간": ev.get("hours")}
    return d


PICK_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "reason": {"type": "string"},
                               "externalName": {"type": "string"}},
                "required": ["id", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["picks"],
    "additionalProperties": False,
}


async def pick_by_ai(items: list[dict], cond: Conditions, timeout: float) -> list[dict] | None:
    from app.llm.client import ask_json
    from app.recommend.prompts import PICK_SYSTEM

    if not items:
        return None
    v = await ask_json(PICK_SYSTEM, {"조건": strip_for_ai(cond), "갈 수 있는 곳": [for_ai(it) for it in items]},
                       PICK_SCHEMA, timeout)
    if not v or not isinstance(v.get("picks"), list):
        return None
    out = []
    for pk in v["picks"][: config.MAX_CANDIDATES]:
        if not isinstance(pk, dict):
            continue
        out.append({"id": (pk.get("id") or "").strip(), "reason": (pk.get("reason") or "").strip(),
                    "externalName": (pk.get("externalName") or "").strip() or None})
    return out

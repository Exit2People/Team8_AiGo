"""AI가 끼는 질문: 조건 묶음만 온 /questions/next, /questions/ai (질문 5).

순서: 질문 에이전트(켜져 있고 오늘 후보가 있으면, 6초) → 발전 질문 → (에이전트를 못 썼을 때만) Claude 한 번 → 은행 → fallback.
"""

import asyncio
import re
import time

from app import config
from app.data import preferences, weather
from app.question import flow, variety
from app.question.lead import lead_question
from app.question.opening import BODY_WORDS, has_banned
from app.schemas import Conditions, strip_for_ai, want_of

AI_QUESTION_SYSTEM = f"""너는 'AI GO'의 질문 담당이야. AI GO는 서울에 사는 어르신이 오늘 대중교통으로 나들이 갈 곳 한 곳을 고르도록 돕는 서비스야.
어르신은 화면의 큰 버튼 하나를 눌러 답해. 글을 길게 읽기 어렵고, 낯선 말이 나오면 멈춰.

받는 값은 출발역, 오늘 컨디션, 다녀올 시간, 지금까지의 질문과 답, 그리고 어르신이 처음에 말한 단서(가고 싶은 곳 · 같이 가는 사람 · 하고 싶은 일)야.
이걸 보고 갈 곳을 고르는 데 가장 도움이 될 다음 질문 하나를 만들어.
단서가 있으면 그 말을 이어서 더 좁히는 질문을 먼저 해. 예: 하고 싶은 일 "공룡 구경" → "공룡은 어떻게 보고 싶으세요?" [화석 전시, 체험 놀이, 영상 · 그림, 상관없어요]
같이 가는 사람이 손주면 아이와 즐길 거리를, 친구면 함께 어울릴 거리를 물어.

질문을 만드는 법
- 질문은 한 문장, 25자 안쪽, 존댓말(해요체). 예: "뭘 하고 싶으세요?"
- "당기세요"처럼 뜻이 여러 가지로 읽히는 말은 쓰지 말고, 어르신이 바로 알아듣는 쉬운 말로 물어.
- 선택지는 정확히 4개, 서로 뜻이 겹치지 않게, 각각 10자 안쪽. (걷는 양 · 실내와 바깥 질문은 아래 고정 선택지 3개)
- 이미 물은 것과 겹치는 질문은 하지 마. 컨디션과 다녀올 시간은 이미 물었어.
- 장소를 고르는 데 실제로 쓰이는 것을 물어. 하고 싶은 것, 걷는 양, 실내와 바깥, 분위기(조용한 곳 · 북적이는 곳), 누구와 가는지 같은 것.
- 어디가 아픈지, 병이나 약, 이름, 나이, 주소, 연락처는 묻지 마. 어르신의 개인정보를 받지 않는 것이 이 서비스의 약속이야.

slot 정하기 (답을 장소 거르기에 바로 쓰기 위한 표시)
- 걷는 양을 묻는 질문이면 slot은 "walk", 선택지는 반드시 {flow.WALK_CHOICES} 그대로.
- 무엇을 하고 싶은지 묻는 질문이면 slot은 "want", 질문은 "뭘 하고 싶으세요?". 선택지는 자유롭게 쓰되 가능하면 {flow.WANT_CHOICES}.
- 실내와 바깥을 묻는 질문이면 slot은 "inout", 선택지는 반드시 {flow.INOUT_CHOICES} 그대로. "반반"처럼 다른 말로 바꾸지 마.
- 그 밖에는 "none".

그만 묻기
- 지금까지의 답으로 갈 곳을 고르기에 충분하면 done을 true로 하고 question은 빈 글, choices는 빈 목록으로 돌려줘.
- 기본 칸(하고 싶은 것 · 걷는 양 · 실내와 바깥)이 이미 채워져 있으면 다시 묻지 말고, 단서 · 바로 앞 답 · 분위기처럼 아직 모르는 것을 물어.
- 질문 수는 화면이 정해. 바로 앞 답이 있으면 그 답을 이어 받아 더 좁혀."""

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "done": {"type": "boolean"},
        "question": {"type": "string"},
        "choices": {"type": "array", "items": {"type": "string"}},
        "slot": {"type": "string", "enum": ["want", "walk", "inout", "none"]},
    },
    "required": ["done", "question", "choices", "slot"],
    "additionalProperties": False,
}

Q5_SYSTEM = """서울에 사는 어르신의 마지막 나들이 질문을 정해요.
질문 3의 답, 곧 물을 질문 4, 그리고 기준별 선택지와 각 선택에 남는 후보 수가 주어져요.
질문 4와 겹치지 않고, 후보를 의미 있게 나누는 기준 하나를 골라 pick에 써요.
선택 후 남는 곳이 너무 적거나 차이가 불균형한 기준보다는 지금 답에 잘 맞는 기준을 골라요.
question은 기준에 지정된 첫말로 시작하고, 한 문장 25자 안쪽의 쉬운 해요체 질문으로 써요.
선택지는 코드가 정하므로 응답에는 넣지 마세요. 개인정보나 건강 상태를 묻지 마세요."""


def norm(s: str) -> str:
    return re.sub(r"[\s?.!,·~]", "", s or "")


def _punct(s: str) -> int:
    return sum(s.count(c) for c in "?.!")


def _asked(cond: Conditions) -> set[str]:
    return {norm(x.q) for x in cond.ai}


def validate_single(cond: Conditions, v: dict) -> dict | None:
    """예전 한 번 호출 검사. 통과하면 {done, question, choices, slot}."""
    q = re.sub(r"\s+", " ", (v.get("question") or "")).strip()
    slot = v.get("slot") if v.get("slot") in ("want", "walk", "inout") else None
    if not q or len(q) > 40 or "\n" in q or _punct(q) > 1:
        return None
    if slot in ("walk", "inout"):
        if getattr(cond.basic, slot):
            return None
        b = flow.BANK[slot]
        if norm(b["question"]) in _asked(cond):
            return None
        return {"done": False, "question": b["question"], "choices": list(b["choices"]), "slot": slot}
    if slot == "want" and want_of(cond):
        return None
    choices = [c.strip() for c in v.get("choices") or []]
    if len(choices) != 4 or len({norm(c) for c in choices}) != 4 or any(not (1 <= len(c) <= 14) for c in choices):
        return None
    if norm(q) in _asked(cond):
        return None
    if has_banned(" ".join([q, *choices]), BODY_WORDS):
        return None
    return {"done": False, "question": q, "choices": choices, "slot": slot}


async def next_ai(cond: Conditions) -> dict:
    """조건 묶음만 온 /questions/next (A안 화면이 쓰는 경로).

    exp/agent-full: 질문 수 고정 total(기본 7). 이번 번호 no = 3 + 이미 물은 수.
    no < total → 질문 에이전트 → (실패 · 늦음) 발전 질문 → (에이전트를 못 썼을 때만) Claude 한 번 → 은행 → fallback.
    no == total → 에이전트가 '1개 더'(no 7)가 꼭 필요한지 판단. 대신 길에서는 묻지 않고 done.
    """
    from app.llm.client import ask_json
    from app.question import agent as qa

    if cond.fallback:
        return {"done": False, "fallback": True}
    t0 = time.monotonic()

    def budget() -> float:
        """화면 기본 질문 시간(8초) 안에 대신 길까지 끝나게 에이전트에 줄 시간."""
        return config.QUESTION_SCREEN - config.QUESTION_SCREEN_MARGIN - (time.monotonic() - t0)

    no, total = qa.numbering(cond)
    if no > total:
        return {"done": True}
    items = flow.today_items(cond)
    agent_ok = config.question_agent_on() and config.has_ai() and bool(items)
    if no == total:
        if agent_ok:
            r = await qa.ask_agent(cond, items, no, total, extra=True, timeout=budget())
            if r is not None and not r.get("done"):
                variety.remember(r.get("question"))
                return {**r, "no": no, "total": total + 1, "extra": True}
        return {"done": True}

    def stamp(q: dict) -> dict:
        variety.remember(q.get("question"))
        return {**q, "no": no, "total": total}

    if agent_ok:
        r = await qa.ask_agent(cond, items, no, total, timeout=budget())
        if r is not None and not r.get("done"):
            return stamp(r)
        # done이어도 질문 수는 채워요 → 아래의 더 좁히는 질문으로
    lead = lead_question(cond, items or [])
    if lead:
        return stamp(lead)
    v = None
    if not agent_ok:
        v = await ask_json(AI_QUESTION_SYSTEM, strip_for_ai(cond), QUESTION_SCHEMA, config.QUESTION_AI_TIMEOUT)
    if v is not None and v.get("done") is not True:
        ok = validate_single(cond, v)
        if ok:
            return stamp({**ok, "source": "ai"})
    qid = flow.best_bank(cond, items)
    if qid:
        return stamp(flow.bank_question(qid, items, None))
    return {"done": False, "fallback": True, "no": no, "total": total}


def _skip_criteria(cond: Conditions, items) -> set[str]:
    skip = set()
    q4 = flow.q4_id(cond, items)
    if q4 == "inout" or cond.basic.inout in ("실내가 좋아요", "바깥이 좋아요"):
        skip.add("inout")
    if q4 == "sight":
        skip.add("kind")
    return skip


def _q5_ok(cond: Conditions, q: str, prefix: str, q4_text: str | None) -> bool:
    if not q.startswith(prefix + " ") or not q.endswith("?") or len(q) > 25 or "\n" in q or _punct(q) != 1:
        return False
    asked = _asked(cond)
    if q4_text:
        asked.add(norm(q4_text))
    if norm(q) in asked:
        return False
    return not has_banned(q, BODY_WORDS)


async def ask_q5(cond: Conditions) -> dict:
    from app.llm import jev
    from app.llm.client import ask_json

    deadline = time.monotonic() + config.QUESTION_AI_TIMEOUT - 0.15
    o = cond.origin
    await asyncio.to_thread(weather.current, o.lat, o.lng)
    items = flow.today_items(cond) or []
    crit = preferences.criteria([it["place"] for it in items], _skip_criteria(cond, items))
    if not crit:
        return {"done": False, "fallback": True}
    q4 = flow.q4_id(cond, items)
    q4_text = flow.BANK[q4]["question"] if q4 else None
    payload = {
        "조건": strip_for_ai(cond), "질문 4": q4_text or "(없음)", "전체 후보 수": len(items),
        "기준별 첫말과 답마다 남는 곳 수": {c["id"]: {"첫말": c["prefix"], "선택지": c["counts"]} for c in crit},
    }
    schema = {"type": "object", "properties": {"pick": {"type": "string", "enum": [c["id"] for c in crit]},
                                                "question": {"type": "string"}},
              "required": ["pick", "question"], "additionalProperties": False}
    v = await ask_json(Q5_SYSTEM, payload, schema, deadline - time.monotonic())
    by = {c["id"]: c for c in crit}
    chosen = by.get((v or {}).get("pick")) or crit[0]
    text, source = chosen["question"], "fixed"
    if v and v.get("pick") in by:
        q = re.sub(r"\s+", " ", v.get("question") or "").strip()
        if _q5_ok(cond, q, chosen["prefix"], q4_text):
            text, source = q, "ai"
    if source == "ai" and config.has_jev() and deadline - time.monotonic() > 0.2:
        p = await jev.ask_yes({"새 질문": text, "선택지": chosen["choices"], "이미 물은 질문": [x.q for x in cond.ai]},
                              "개인정보를 묻거나 이미 물은 것과 같은 질문인가?",
                              min(config.JEV_TIMEOUT, deadline - time.monotonic()))
        if p is not None and p >= 0.5:
            text, source = chosen["question"], "fixed"
    return {"done": False, "no": 5, "id": chosen["id"], "question": text, "choices": chosen["choices"],
            "slot": None, "source": source, "total": config.question_total()}


async def ask_ai(cond: Conditions) -> dict:
    if cond.fallback:
        return {"done": False, "fallback": True}
    if config.question_agent_on() and config.has_ai():
        from app.question.agent import ask_agent

        items = flow.today_items(cond)
        if items:
            r = await ask_agent(cond, items)
            if r is not None:
                return {"done": True, "no": 5, "source": "agent"} if r.get("done") else {**r, "no": 5,
                                                                                           "total": config.question_total()}
    if config.question_mode() == "single":
        r = await next_ai(cond)
        if r.get("question"):
            return {**r, "no": 5}
        return {"done": False, "fallback": True}
    try:
        return await asyncio.wait_for(ask_q5(cond), timeout=config.QUESTION_AI_TIMEOUT)
    except asyncio.TimeoutError:
        return {"done": False, "fallback": True}

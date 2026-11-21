"""질문 에이전트 (LangGraph, 도구 find_places · look_bank + submit_question). 6초, 도구 2번.

낸 질문은 코드 검사(check_question) → Jev 두 번(jev_ok) → 통과하면 {done, question, choices, slot}.
실패 · 늦음 · 검사 탈락은 None → 부르는 쪽이 발전 질문 · 은행으로 가요.
"""

import asyncio
import re
import time
from collections import Counter

from app import config
from app.question import flow
from app.question.opening import asks_body
from app.question.search import place_scores, word_ok
from app.question.themes import ALL_THEMES, short_name, themes_of
from app.schemas import Conditions, strip_for_ai, want_of

SYSTEM = """너는 'AI GO'의 질문 에이전트야. 서울에 사는 어르신이 오늘 대중교통으로 갈 곳 한 곳을 고르도록, 다음 질문 하나를 정해.
어르신은 큰 버튼 하나를 눌러 답해. 쉬운 말, 존댓말(해요체), 한 문장, 25자 안쪽, 물음표로 끝내.

받는 것: 조건(컨디션 · 시간 · 기본 칸 · 처음에 한 말의 단서), 이미 물은 질문과 답, 오늘 갈 수 있는 곳 수와 주제별 곳 수,
단서로 미리 찾은 곳, 은행 질문. 대개 이것만으로 바로 submit_question 을 낼 수 있어. 다른 말로 더 찾아볼 때만 도구를 써 (어르신이 기다려).

할 일
1. 처음에 한 말의 단서(가고 싶은 곳 · 하고 싶은 일 · 같이 가는 사람)가 있으면 그걸 이어서 좁히는 질문을 먼저 생각해.
   find_places 로 그 말에 맞는 오늘의 곳을 찾아. 두 곳 이상이면 그 이름을 선택지로 쓰는 질문이 가장 좋아.
2. 단서가 없거나 맞는 곳이 없으면, 주제별 곳 수를 보고 오늘 후보를 고르게 나누는 질문을 만들어. 선택지는 주제 이름 그대로 써.
   은행 질문을 그대로 쓰거나 말만 다듬어도 되지만, 같이 가는 사람 · 하고 싶은 일에 맞게 고쳐 묻는 게 더 좋아.
   예: 손주랑 → "손주와 무엇을 해 보고 싶으세요?" [만들기 체험, 그림 · 사진, 공원]
3. submit_question 으로 내. 이미 갈 곳이 3곳 이하로 좁혀졌거나 더 물어도 달라질 게 없으면 done=true.

선택지 규칙 (코드가 확인해. 어기면 버려져)
- 2~4개, 각각 14자 안쪽. 오늘 후보에 근거가 있어야 해: find_places 가 준 이름, 주제 이름(받은 표에 있는 것), 은행 선택지,
  또는 기본 칸 선택지(하고 싶은 것 · 걷는 양 · 실내와 바깥, 아직 비어 있을 때만). "잘 모르겠어요"는 화면이 붙이니 넣지 마.
- 이미 채워진 기본 칸과 이미 물은 질문은 다시 묻지 마.
- 어디가 아픈지, 병, 약, 이름, 나이, 주소, 연락처는 묻지 마."""

JEV_NATURAL = "질문이 한 가지만 묻는, 어르신이 바로 알아듣는 자연스러운 존댓말 한 문장이면 yes."
JEV_FIT = "선택지 하나하나가 이 질문에 대한 답으로 말이 되면 yes. 장소 이름은 '어디'나 '어떤 곳'을 묻는 질문의 답이 될 수 있다."

SCHEMAS = [
    {"name": "find_places", "description": "오늘 갈 수 있는 곳을 낱말로 찾아요 (이름 조각 · 주제 · 하고 싶은 일 점수).",
     "input_schema": {"type": "object", "properties": {"word": {"type": "string", "description": "2~40자 낱말"}},
                      "required": ["word"]}},
    {"name": "look_bank", "description": "아직 안 물은 은행 질문과 선택지마다 오늘 남는 곳 수를 봐요.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "submit_question", "description": "다음 질문 하나를 내고 끝내요. 더 물을 게 없으면 done=true.",
     "input_schema": {"type": "object", "properties": {
         "done": {"type": "boolean"}, "question": {"type": "string"},
         "choices": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
         "why": {"type": "string", "description": "기록용 한 줄"}}, "required": ["question", "choices"]}},
]

NEUTRAL = {"잘 모르겠어요", "상관없어요", "다 좋아요", "둘 다 좋아요", "아무 곳이나", "괜찮아요"}
_SLOT_CHOICES = {"want": flow.WANT_CHOICES, "walk": flow.WALK_CHOICES, "inout": flow.INOUT_CHOICES}


def _norm(s: str) -> str:
    return re.sub(r"[\s?.!,·~]", "", s or "")


def find_places_by(items: list[dict], word: str) -> dict:
    err = word_ok(word)
    if err:
        return {"error": err}
    found = place_scores(items, word.strip())
    names, scores = [], {}
    for it, s in found:
        n = short_name(it["place"])
        if n in scores:
            continue
        names.append(n)
        scores[n] = round(s, 1)
        if len(names) == 6:
            break
    th = Counter(t for it, _ in found for t in themes_of(it["place"]) if t in ALL_THEMES)
    return {"찾은 곳 수": len(found), "가까운 곳 이름": names, "점수": scores,
            "찾은 곳의 주제별 수": dict(th.most_common(8))}


def look_bank(cond: Conditions, items: list[dict]) -> dict:
    asked = flow.asked_ids(cond)
    out = {}
    for qid, b in flow.BANK.items():
        if qid in asked or flow.skipped(cond, qid):
            continue
        if qid == "budget" and want_of(cond) != "맛있는 것":
            continue
        counts = flow.bank_counts(qid, items)
        out[b["question"]] = {c: (counts[c] if counts and c in counts else "셀 수 없음")
                              for c in flow.live_choices(qid, items)}
    return out


def unknown_slots(cond: Conditions) -> list[str]:
    out = []
    if not want_of(cond):
        out.append("하고 싶은 것")
    if not cond.basic.walk and cond.body != "좀 무거워요":
        out.append("걷는 양")
    if not cond.basic.inout:
        out.append("실내와 바깥")
    return out


def first_message(cond: Conditions, items: list[dict]) -> dict:
    th = Counter(t for it in items for t in themes_of(it["place"]) if t in ALL_THEMES)
    clues = [x for x in [cond.extra.place, *cond.extra.wish] if x][:3]
    return {
        "조건": strip_for_ai(cond), "아직 모르는 기본 칸": unknown_slots(cond), "오늘 갈 수 있는 곳 수": len(items),
        "주제별 곳 수": dict(th.most_common()),
        "단서로 미리 찾은 곳 (find_places 결과)": {c: find_places_by(items, c) for c in clues},
        "은행 질문 (look_bank 결과)": look_bank(cond, items),
    }


def choice_count(choice: str, cond: Conditions, items: list[dict]) -> int | None | bool:
    """곳 수 · None(셀 수 없음) · False(근거 없음)."""
    if choice in NEUTRAL:
        return None
    names = Counter(short_name(it["place"]) for it in items)
    if choice in names:
        return names[choice]
    if choice in ALL_THEMES:
        return sum(1 for it in items if choice in themes_of(it["place"]))
    for b in flow.BANK.values():
        if b["match"] and choice in b["match"]:
            ts = set(b["match"][choice])
            return sum(1 for it in items if ts & themes_of(it["place"]))
    if choice in flow.WANT_CHOICES and not want_of(cond):
        return sum(1 for it in items if choice in (it["place"].get("wants") or []))
    if choice in flow.INOUT_CHOICES and not cond.basic.inout:
        opp = {"실내가 좋아요": "바깥", "바깥이 좋아요": "실내"}.get(choice)
        return sum(1 for it in items if it["place"].get("inout") != opp)
    if choice in flow.WALK_CHOICES and not cond.basic.walk:
        return None
    for b in flow.BANK.values():  # 은행 선택지인데 셀 수 없는 것 (budget · fee)
        if choice in b["choices"]:
            return None
    return False


def same_as_asked(cond: Conditions, choices: list[str]) -> bool:
    """글은 달라도 선택지가 앞 질문과 거의 같으면 같은 질문이에요 (예: '어디로 갈까요?' → '어디서 타고 싶으세요?')."""
    new = {_norm(c) for c in choices}
    for x in cond.ai:
        old = {_norm(c) for c in x.choices}
        same = len(new & old)
        if same >= 2 and same >= len(new) - 1:
            return True
    return False


def check_question(cond: Conditions, items: list[dict], sub: dict) -> dict | None:
    if sub.get("done") is True:
        return {"done": True}
    q = re.sub(r"\s+", " ", str(sub.get("question") or "")).strip()
    raw = [re.sub(r"\s+", " ", str(c)).strip() for c in (sub.get("choices") or [])]
    choices: list[str] = []
    for ch in raw:
        if ch and ch != "잘 모르겠어요" and ch not in choices:
            choices.append(ch)
    if not q or len(q) > 25 or not q.endswith("?") or sum(q.count(x) for x in "?.!") != 1:
        return None
    if _norm(q) in {_norm(x.q) for x in cond.ai}:
        return None
    if asks_body(q, choices):
        return None
    if not 2 <= len(choices) <= 4 or any(len(c) > 14 for c in choices):
        return None
    counts = {}
    for ch in choices:
        n = choice_count(ch, cond, items)
        if n is False:
            return None
        counts[ch] = n
    choices = [c for c in choices if counts[c] != 0]
    if len(choices) < 2:
        return None
    if same_as_asked(cond, choices):
        return None
    counted = [c for c in choices if counts[c] is not None]
    if counted and len(counted) < 2:
        return None
    # 단서를 말하면서 장소 이름을 고르게 하면, 그 이름은 그 단서로 찾은 곳이어야 해요
    today_names = {short_name(it["place"]) for it in items}
    place_choices = [c for c in choices if c in today_names]
    if place_choices:
        for clue in [x for x in [cond.extra.place, *cond.extra.wish] if x]:
            first = clue.split()[0]
            if clue in q or first in q:
                ok = {short_name(it["place"]) for w in {clue, first} for it, _ in place_scores(items, w)}
                if any(c not in ok for c in place_choices):
                    return None
    slot = None
    for s, opts in _SLOT_CHOICES.items():
        if all(c in opts for c in choices):
            filled = want_of(cond) if s == "want" else getattr(cond.basic, s)
            if filled:
                return None
            slot = s
            if s in ("walk", "inout"):
                b = flow.BANK[s]
                if _norm(b["question"]) in {_norm(x.q) for x in cond.ai}:
                    return None
                q, choices = b["question"], list(b["choices"])
            break
    return {"done": False, "question": q, "choices": choices, "slot": slot}


async def jev_ok(cond: Conditions, q: dict, deadline: float) -> bool:
    from app.llm import jev

    left = deadline - time.monotonic()
    if not config.question_jev_on() or not config.has_jev_key() or left <= 0.2 or q.get("slot") in ("walk", "inout"):
        return True
    clue = {}
    if cond.extra.place:
        clue["가고 싶은 곳"] = cond.extra.place
    if cond.extra.who:
        clue["같이 가는 사람"] = cond.extra.who
    if cond.extra.wish:
        clue["하고 싶은 일"] = list(cond.extra.wish)
    state = {"질문": q["question"], "선택지": q["choices"], "단서": clue}
    t = min(config.JEV_TIMEOUT, left)
    nat, fit = await asyncio.gather(jev.ask_yes(state, JEV_NATURAL, t), jev.ask_yes(state, JEV_FIT, t))
    if nat is not None and nat < config.QUESTION_JEV_NATURAL_MIN:
        return False
    if fit is not None and fit < config.QUESTION_JEV_FIT_MIN:
        return False
    return True


async def ask_agent(cond: Conditions, items: list[dict]) -> dict | None:
    from app.llm import agent_loop

    if not config.has_ai() or not items:
        return None
    deadline = time.monotonic() + config.QUESTION_AGENT_TIMEOUT
    tools = {"find_places": lambda word: find_places_by(items, word),
             "look_bank": lambda: look_bank(cond, items),
             "submit_question": lambda **kw: {"ok": True}}
    model = config.env("AIGO_QUESTION_AGENT_MODEL") or config.model()
    res = await agent_loop.run(SYSTEM, first_message(cond, items), tools, SCHEMAS, "submit_question",
                               config.QUESTION_AGENT_ROUNDS, config.QUESTION_AGENT_TIMEOUT, model, 1500, "low",
                               name="질문 에이전트")
    if not res or not isinstance(res.get("submitted"), dict):
        return None
    q = check_question(cond, items, res["submitted"])
    if q is None:
        return None
    if q.get("done"):
        return q
    if not await jev_ok(cond, q, deadline):
        return None
    return {**q, "source": "agent"}

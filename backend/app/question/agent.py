"""질문 에이전트 (LangGraph, 도구 find_places · look_bank · count_choices + submit_question). 6초, 도구 2번.

exp/agent-full: no 3~6(꼭 필요하면 no 7 "1개 더")을 모두 이 에이전트가 정해요. 어르신 말 · 앞 답을 이어 받는 질문이 먼저예요.

낸 질문은 코드 검사(check_question) → Jev 두 번(jev_ok) → 통과하면 {done, question, choices, slot}.
실패 · 늦음 · 검사 탈락은 None → 부르는 쪽이 발전 질문 · 은행으로 가요.
"""

import asyncio
import logging
import re
import time
from collections import Counter

from app import config
from app.question import flow, variety
from app.question.opening import asks_body
from app.question.search import NAME_MIN, place_scores, word_ok
from app.question.themes import ALL_THEMES, short_name, themes_of, wish_themes
from app.schemas import Conditions, strip_for_ai, want_of

log = logging.getLogger("aigo.question.agent")

SYSTEM = """너는 'AI GO'의 질문 에이전트야. 서울에 사는 어르신과 이야기하듯 다음 질문 하나를 정해. 목표는 오늘 대중교통으로 갈 곳 한 곳을 고르는 거야.
어르신은 큰 버튼 하나를 눌러 답해. 쉬운 말, 존댓말(해요체), 한 문장, 32자 안쪽, 물음표로 끝내.

가장 중요한 것: 어르신이 한 말과 바로 앞 답을 이어 받아 물어. 정해진 칸(걷기 · 실내외 · 구경 종류)을 차례로 묻는 느낌이면 안 돼.
- 좋은 예: "손주랑 공룡 보러 가고 싶어" → "손주랑 공룡은 어떻게 보고 싶으세요?" [화석 전시, 만들기 체험, 과학 영상]
  → 앞 답이 "화석 전시"면 → "화석은 큰 박물관이 좋으세요, 가까운 곳이 좋으세요?" [찾은 곳 이름 2~3개]
- 나쁜 예: 같은 말 다음에 "실내가 좋으세요, 바깥이 좋으세요?", "걷는 건 괜찮으세요?" (말과 상관없는 칸 묻기)
- 어르신 바람과 바로 맞는 곳이 오늘 없어도 "대신" · "말고" 같은 말로 바람을 접지 마. 바람을 이어 받아 같이 가는 사람이 좋아할 것을 물어.
  좋은 예: "공룡 좋아하는 손주는 뭘 하면 신나 할까요?" [만들기 체험, 뛰어놀기, 그림 구경] / 나쁜 예: "공룡 대신 어떤 걸 볼까요?"
  (맞는 곳이 쉬는 날이면 언제 가면 되는지는 추천 화면이 따로 알려 드려요.)
- 이미 아는 것(처음 말 · 컨디션 · 시간 · 채운 칸 · 앞 답)은 다시 묻지 마. 걷기 · 실내외 같은 칸은 말에서 알 수 없고 꼭 필요할 때만, 이어지는 말 속에 섞어 물어.

받는 것: 조건(처음 말의 단서 · 컨디션 · 시간 · 채운 칸 · 앞 질문과 답), 질문 번호와 남은 질문 수, 이어 받을 말,
오늘 갈 수 있는 곳 수와 주제별 곳 수, 단서로 미리 찾은 곳, 은행 질문(선택지마다 남는 곳 수). 대개 이것만으로 바로 submit_question 을 낼 수 있어.
도구는 어르신이 기다리니 꼭 필요할 때만 써: find_places(다른 말로 찾아보기), count_choices(새로 만든 선택지마다 오늘 남는 곳 수), look_bank.

질문 고르기
1. 이어 받을 말이 있으면 그 말을 더 구체적으로 좁히는 질문을 먼저 만들어. 찾은 곳 이름이 2곳 이상이면 그 이름을 선택지로 써도 좋아.
2. 이어 받을 말이 없으면(처음 말이 "잘 모르겠어요" 등) 주제별 곳 수를 보고, 어르신이 대답하기 쉬운 것부터 물어.
3. 은행 질문이 지금 대화에 잘 맞으면 써도 돼 (그대로 쓰거나, 뜻은 두고 바꿔 말해도 돼). 아니면 새로 만들어.
4. 남은 질문이 적을수록(특히 마지막 질문) 오늘 후보를 크게 가르는 질문을 골라. 선택지마다 남는 곳 수가 고르게 나뉘면 좋아.
5. 질문 수는 정해져 있어. 이미 좁혀졌어도 done 으로 끝내지 말고, 남은 후보를 더 좁히는 질문을 내.

선택지 규칙 (코드가 확인해. 어기면 버려져)
- 2~4개, 각각 14자 안쪽, 서로 겹치지 않게. "잘 모르겠어요"는 화면이 붙이니 넣지 마.
- 앞에서 이미 고른 답 · 어르신이 처음 한 말을 선택지로 다시 내지 마 (코드가 빼). 앞 질문과 비슷한 질문을 되풀이하지 마.
- 오늘 후보에 근거가 있어야 해: 찾은 곳 이름, 주제 이름, 은행 선택지, 아직 빈 기본 칸 선택지,
  또는 그 말로 찾으면 오늘 갈 곳이 나오는 짧은 말(예: "화석", "만들기 체험", "물가"). count_choices 로 미리 확인할 수 있어.
- 어디가 아픈지, 병, 약, 몸 상태, 이름, 나이, 주소, 연락처는 묻지 마. (같이 가는 손주가 어떤 걸 좋아하는지는 물어도 돼.)"""

EXTRA_SYSTEM_NOTE = """이번은 정해진 질문이 다 끝난 뒤의 '1개 더'야. 꼭 필요할 때만 물어:
- 답으로 좁혀도 오늘 후보가 아직 많고(받은 '답으로 좁힌 곳 수'), 어르신 말의 핵심(가고 싶은 곳 · 하고 싶은 일)을 아직 하나로 좁히지 못했을 때,
- 또는 앞 답끼리 부딪혀서(예: 조용한 곳 + 축제) 무엇을 먼저 할지 모를 때.
그렇지 않으면 done=true 로 내. 물을 때는 why 에 꼭 필요한 이유를 한 줄로 적어."""

JEV_NATURAL = "질문이 한 가지만 묻는, 어르신이 바로 알아듣는 자연스러운 존댓말 한 문장이면 yes."
JEV_FIT = "선택지 하나하나가 이 질문에 대한 답으로 말이 되면 yes. 장소 이름은 '어디'나 '어떤 곳'을 묻는 질문의 답이 될 수 있다."

SCHEMAS = [
    {"name": "find_places", "description": "오늘 갈 수 있는 곳을 낱말로 찾아요 (이름 조각 · 주제 · 하고 싶은 일 점수).",
     "input_schema": {"type": "object", "properties": {"word": {"type": "string", "description": "2~40자 낱말"}},
                      "required": ["word"]}},
    {"name": "look_bank", "description": "아직 안 물은 은행 질문과 선택지마다 오늘 남는 곳 수를 봐요.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "count_choices", "description": "새로 만든 선택지마다 오늘 남는 곳 수를 세요. '근거 없음'이면 그 선택지는 못 써요.",
     "input_schema": {"type": "object", "properties": {
         "choices": {"type": "array", "items": {"type": "string"}, "maxItems": 4}}, "required": ["choices"]}},
    {"name": "submit_question", "description": "다음 질문 하나를 내고 끝내요. '1개 더'에서 물을 게 없으면 done=true.",
     "input_schema": {"type": "object", "properties": {
         "done": {"type": "boolean"}, "question": {"type": "string"},
         "choices": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
         "bank": {"type": "string", "description": "은행 질문을 그대로 썼으면 그 질문 글"},
         "follows": {"type": "string", "description": "이어 받은 말 (어르신 말 · 앞 답), 없으면 빈 글"},
         "why": {"type": "string", "description": "기록용 한 줄 (1개 더면 꼭 필요한 이유)"}},
         "required": ["question", "choices"]}},
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


def asked_count(cond: Conditions) -> int:
    """no 3부터 물은 질문 수: 칸 없는 답(ai) + 질문으로 채운 기본 칸 (첫 말에서 채운 칸은 빼요)."""
    n = len(cond.ai)
    for slot in ("want", "walk", "inout"):
        if getattr(cond.basic, slot) and slot not in cond.filled:
            n += 1
    return n


def numbering(cond: Conditions) -> tuple[int, int]:
    """(이번 질문 번호 no, 전체 질문 수 total)."""
    return config.QUESTION_FIXED + asked_count(cond), config.question_total()


_PARTICLES = ("이랑", "에서", "으로", "하고", "랑", "은", "는", "이", "가", "을", "를", "도", "와", "과")
_FOLLOW_SKIP = {"구경", "하기", "보기", "가기", "좋아요", "괜찮아요", "상관없어요", "모르겠어요", "어디", "어떤", "좋으세요",
                "싶으세요", "실내", "바깥", "보통이에요", "조금만요", "많이", "같이"}


def _tokens(text: str | None) -> list[str]:
    out = []
    for w in re.findall(r"[가-힣A-Za-z0-9]+", text or ""):
        for p in _PARTICLES:
            if w.endswith(p) and len(w) - len(p) >= 2:
                w = w[: -len(p)]
                break
        if len(w) >= 2 and w not in _FOLLOW_SKIP:
            out.append(w)
    return out


def follow_sources(cond: Conditions) -> list[str]:
    """이어 받을 말: 바로 앞 답 → 처음 말의 단서 (가고 싶은 곳 · 하고 싶은 일 · 같이 가는 사람)."""
    out: list[str] = []
    if cond.ai and cond.ai[-1].a and cond.ai[-1].a not in NEUTRAL:
        out.append(cond.ai[-1].a)
    for x in [cond.extra.place, *cond.extra.wish]:
        if x and x not in out:
            out.append(x)
    if cond.extra.who and cond.extra.who != "혼자":
        out.append(cond.extra.who)
    return out


def follows(cond: Conditions, items: list[dict], question: str, choices: list[str] | None = None) -> str | None:
    """질문이 앞 말 · 앞 답을 이어 받았으면 그 말 (질문 글에 그 말이 들어 있거나, 그 말로 찾은 곳 이름만 고르게 할 때).

    리포트 · 로그의 '이어 받은 질문 수'에 써요.
    """
    srcs = follow_sources(cond)
    for src in srcs:
        if any(t in question for t in _tokens(src)):
            return src
    if choices:
        for src in srcs:
            if src == cond.extra.who or word_ok(src):
                continue
            found = {short_name(it["place"]) for it, _ in place_scores(items, src)}
            if found and all(c in found for c in choices):
                return src
    return None


def narrowed(cond: Conditions, items: list[dict]) -> list[dict]:
    """답한 주제로 좁힌 오늘 후보 (주제 답이 없으면 그대로)."""
    ts = flow.answer_themes(cond)
    if not ts:
        return items
    left = [it for it in items if ts & themes_of(it["place"])]
    return left or items


def missing_wishes(cond: Conditions, items: list[dict]) -> list[str]:
    """구체적인 바람(공룡 · 자전거 …) 중 오늘 후보에 바로 맞는 곳이 없는 것."""
    from app.recommend.wish import direct_specific, specific_terms

    return [w for w in cond.extra.wish
            if specific_terms([w]) and not any(direct_specific(it["place"], [w]) for it in items)]


def first_message(cond: Conditions, items: list[dict], no: int | None = None, total: int | None = None,
                  extra: bool = False) -> dict:
    th = Counter(t for it in items for t in themes_of(it["place"]) if t in ALL_THEMES)
    clues = [x for x in [cond.extra.place, *cond.extra.wish] if x][:3]
    last = cond.ai[-1].a if cond.ai and cond.ai[-1].a and cond.ai[-1].a not in NEUTRAL else None
    if last and last not in clues and not word_ok(last):
        clues.append(last)
    msg = {
        "조건": strip_for_ai(cond), "아직 모르는 기본 칸": unknown_slots(cond),
        "이어 받을 말": follow_sources(cond) or ["(없어요. 처음 말이 막연했어요)"],
        "오늘 갈 수 있는 곳 수": len(items), "답으로 좁힌 곳 수": len(narrowed(cond, items)),
        "주제별 곳 수": dict(th.most_common()),
        "단서 · 앞 답으로 미리 찾은 곳 (find_places 결과)": {c: find_places_by(items, c) for c in clues},
        "은행 질문 (look_bank 결과)": look_bank(cond, items),
    }
    missing = missing_wishes(cond, items)
    if missing:
        msg["바람과 바로 맞는 곳 없음"] = (f"{', '.join(missing)}과(와) 바로 맞는 곳이 오늘은 없어요. 바람을 접지 말고 이어 받아, "
                                  "같이 가는 사람이 좋아할 것 · 비슷한 즐거움을 물어요. '대신'이라는 말은 쓰지 마요.")
    if no is not None and total is not None:
        msg["질문 번호"] = f"{no}번 (전체 {total}개 중, 0번은 처음 말)"
        msg["이번 질문 뒤 남은 질문 수"] = max(0, total - no - 1)
        if not extra and total - no - 1 == 0:
            msg["안내"] = "이번이 정해진 마지막 질문이에요. 오늘 후보를 가장 크게 가르는 질문을 골라요."
    if extra:
        msg["1개 더"] = EXTRA_SYSTEM_NOTE
    if variety.on():
        msg["매번 새롭게"] = ("최근에 다른 어르신들께 낸 질문과 같은 문장은 피해요. 같은 뜻이어도 말투 · 낱말 · 선택지 순서를 바꿔요. "
                         "은행 질문도 뜻은 그대로 두고 바꿔 말해도 돼요.")
        a = variety.angle()
        if a:
            msg["이번 각도 (어울리면)"] = a
        if variety.recent():
            msg["최근에 낸 질문"] = variety.recent()
    return msg


def _search_count(choice: str, items: list[dict]) -> int:
    """자유 선택지의 근거: 그 말의 주제가 오늘 후보에 있거나, 그 말로 찾으면 오늘 갈 곳이 나와요."""
    if word_ok(choice):
        return 0
    ts = wish_themes(choice)
    if ts:
        n = sum(1 for it in items if ts & themes_of(it["place"]))
        if n:
            return n
    # 이름이 제대로 맞은 곳만 (느슨한 '하고 싶은 일' 점수만으로는 근거가 안 돼요)
    return sum(1 for _, sc in place_scores(items, choice) if sc >= NAME_MIN)


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
    # exp/agent-full에서 풀어 준 것: 정해진 목록에 없는 말도 그 말로 오늘 갈 곳을 찾을 수 있으면 근거가 있어요
    n = _search_count(choice, items)
    return n if n > 0 else False


def count_choices(cond: Conditions, items: list[dict], choices) -> dict:
    out = {}
    for c in list(choices or [])[:4]:
        c = re.sub(r"\s+", " ", str(c)).strip()
        n = choice_count(c, cond, items)
        out[c] = "근거 없음" if n is False else ("셀 수 없음" if n is None else n)
    return out


_INOUT_WORDS = ("실내", "바깥", "야외", "밖에서", "안에서")
_WALK_WORDS = ("걷", "걸어", "걸으")


def asks_filled(cond: Conditions, q: str) -> bool:
    """첫 말 · 앞 답으로 이미 채운 칸을 다른 말로 다시 묻는지."""
    if cond.basic.inout and any(w in q for w in _INOUT_WORDS):
        return True
    if (cond.basic.walk or cond.body == "좀 무거워요") and any(w in q for w in _WALK_WORDS):
        return True
    if want_of(cond) and _norm(q) == _norm(flow.WANT_Q["question"]):
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
    if not q or len(q) > config.QUESTION_MAX_LEN or not q.endswith("?") or sum(q.count(x) for x in "?.!") != 1:
        return None
    if _norm(q) in {_norm(x.q) for x in cond.ai}:
        return None
    if asks_body(q, choices):
        return None
    if "대신" in q:
        # 어르신 바람을 접는 말이라 쓰지 않아요 ("공룡 대신 어떤 걸 볼까요?")
        return None
    # 은행 질문을 그대로 골랐으면 은행 선택지(오늘 남는 것만)를 써요. 은행 질문은 미리 검사한 거예요
    bank_id = flow.bank_id_of(q)
    if bank_id and bank_id not in ("walk", "inout"):
        if bank_id in flow.asked_ids(cond) or flow.skipped(cond, bank_id):
            return None
        live = flow.live_choices(bank_id, items)
        # 은행 질문(또는 그 다른 말투)은 은행 선택지로. 에이전트가 고른 순서를 따르고 나머지는 뒤에
        mine = [c for c in choices if c in live]
        out = mine + [c for c in live if c not in mine]
        # 같은 선택지 묶음을 다른 말투로 이미 물었으면 되풀이예요 (asked_ids 는 은행 문장 그대로일 때만 알아봐요)
        sig = {_norm(c) for c in out if c != "잘 모르겠어요"}
        if any(sig == {_norm(c) for c in x.choices if c != "잘 모르겠어요"} for x in cond.ai):
            return None
        # 오늘 갈 곳이 0곳인 선택지는 빼요. 고를 만한 선택지('잘 모르겠어요' 빼고)가 2개 미만이면 묻지 않아요
        # (live_choices 는 나눌 수 없으면 원래 선택지를 그대로 돌려줘서 0곳 선택지가 섞여요.
        #  요금처럼 셀 수 있는 선택지가 하나뿐인 은행 질문도 있어서, 셀 수 없는 선택지는 그대로 둬요)
        counts = flow.bank_counts(bank_id, items) if items is not None else None
        if counts is not None:
            out = [c for c in out if counts.get(c, 1) > 0]
            if sum(1 for c in out if c != "잘 모르겠어요") < 2:
                return None
        return {"done": False, "question": q, "choices": out, "slot": flow.BANK[bank_id]["slot"]}
    if not 2 <= len(choices) <= 4 or any(len(c) > 14 for c in choices):
        return None
    if len({_norm(c) for c in choices}) != len(choices):
        return None
    # 앞에서 이미 고른 답 · 처음 말의 단서를 선택지로 다시 내지 않아요, 앞 질문과 같은 선택지 묶음도 안 돼요
    before = {_norm(x.a) for x in cond.ai if x.a} | {_norm(w) for w in cond.extra.wish}
    choices = [c for c in choices if _norm(c) not in before]
    if any({_norm(c) for c in choices} == {_norm(c) for c in x.choices if c != "잘 모르겠어요"} for x in cond.ai):
        return None
    if len(choices) < 2:
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
    if slot is None and asks_filled(cond, q):
        return None
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
    if cond.ai and cond.ai[-1].a:
        clue["바로 앞 답"] = cond.ai[-1].a
    state = {"질문": q["question"], "선택지": q["choices"], "단서": clue}
    t = min(config.JEV_TIMEOUT, left)
    nat, fit = await asyncio.gather(jev.ask_yes(state, JEV_NATURAL, t), jev.ask_yes(state, JEV_FIT, t))
    if nat is not None and nat < config.QUESTION_JEV_NATURAL_MIN:
        return False
    if fit is not None and fit < config.QUESTION_JEV_FIT_MIN:
        return False
    return True


async def ask_agent(cond: Conditions, items: list[dict], no: int | None = None, total: int | None = None,
                    extra: bool = False, timeout: float | None = None) -> dict | None:
    """질문 하나. 통과하면 {done, question, choices, slot, source: agent, follows?, id?, why?}.

    실패 · 늦음 · 검사 탈락은 None. extra=True 는 정해진 질문이 끝난 뒤 '1개 더'(no 7) 판단이에요 —
    꼭 필요하지 않으면 {"done": True}.
    """
    from app.llm import agent_loop

    if not config.has_ai() or not items:
        return None
    if no is None or total is None:
        no, total = numbering(cond)
    if extra:
        left = len(narrowed(cond, items))
        if left < config.EXTRA_MIN_LEFT:
            log.info("질문 에이전트: 1개 더 안 물어요 (좁힌 곳 %s곳)", left)
            return {"done": True}
    budget = config.QUESTION_AGENT_TIMEOUT if timeout is None else min(config.QUESTION_AGENT_TIMEOUT, timeout)
    if budget <= 0.5:
        return None
    deadline = time.monotonic() + budget
    tools = {"find_places": lambda word: find_places_by(items, word),
             "look_bank": lambda: look_bank(cond, items),
             "count_choices": lambda choices: count_choices(cond, items, choices),
             "submit_question": lambda **kw: {"ok": True}}
    model = config.env("AIGO_QUESTION_AGENT_MODEL") or config.model()
    first = first_message(cond, items, no, total, extra)  # 곳 찾기가 들어 있어 1초쯤 걸려요 → 남은 시간만 에이전트에
    res = await agent_loop.run(SYSTEM, first, tools, SCHEMAS,
                               "submit_question", config.QUESTION_AGENT_ROUNDS, deadline - time.monotonic(), model,
                               1500, "low", name="질문 에이전트")
    if not res or not isinstance(res.get("submitted"), dict):
        return None
    sub = res["submitted"]
    why = re.sub(r"\s+", " ", str(sub.get("why") or "")).strip()[:80]
    q = check_question(cond, items, sub)
    if q is None:
        log.info("질문 에이전트: 검사에서 빠졌어요 (no %s)", no)
        return None
    if q.get("done"):
        if extra:
            log.info("질문 에이전트: 1개 더 필요 없음 (%s)", why or "이유 없음")
        return q
    if extra and not why:
        log.info("질문 에이전트: 1개 더인데 이유가 없어서 안 물어요")
        return {"done": True}
    if not await jev_ok(cond, q, deadline):
        return None
    out = {**q, "source": "agent"}
    bank_id = flow.bank_id_of(q["question"])
    if bank_id:
        out["id"] = bank_id
    f = follows(cond, items, q["question"], q["choices"])
    if f:
        out["follows"] = f
    if extra:
        out["why"] = why
        log.info("질문 에이전트: 1개 더 물어요 (%s)", why)
    else:
        log.info("질문 에이전트: no %s/%s, 은행 %s, 이어 받음 %s", no, total, bank_id or "-", bool(f))
    return out

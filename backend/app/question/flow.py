"""질문 순서 · 질문 은행(BANK) · 다음 질문 (AI 없이)."""

import logging

from app import config
from app.schemas import Conditions, want_of

log = logging.getLogger("aigo.flow")

OPEN_Q = {
    "done": False, "no": 0, "id": "open", "question": "오늘 어떤 하루 보내고 싶으세요?", "input": "text",
    "examples": ["바람 쐬고 싶어요", "구경하고 싶어요", "맛있는 거 먹고 싶어요", "조용히 쉬고 싶어요", "잘 모르겠어요"],
    "slot": None, "choices": [], "source": "fixed",
}
BODY_CHOICES = ["가뿐해요", "보통이에요", "좀 무거워요"]
TIME_CHOICES = ["반나절", "한나절", "하루 종일"]
WANT_CHOICES = ["바람 쐬기", "구경하기", "맛있는 것", "조용히 쉬기"]
WALK_CHOICES = ["많이 걸어요", "보통이에요", "조금만요"]
INOUT_CHOICES = ["실내가 좋아요", "바깥이 좋아요", "둘 다 좋아요"]
WHO_CHOICES = ["혼자", "배우자", "손주", "자녀", "친구"]

BODY_Q = {"done": False, "no": 1, "id": "body", "question": "컨디션은 어떠세요?", "choices": BODY_CHOICES,
          "slot": "body", "source": "fixed"}
TIME_Q = {"done": False, "no": 2, "id": "time", "question": "얼마나 나가 계실 건가요?", "choices": TIME_CHOICES,
          "slot": "time", "source": "fixed"}
WANT_Q = {"done": False, "no": 3, "id": "want", "question": "뭘 하고 싶으세요?",
          "choices": [*WANT_CHOICES, "잘 모르겠어요"], "slot": "want", "source": "fixed"}

BANK: dict[str, dict] = {
    "walk": {"question": "걷는 건 괜찮으세요?", "choices": WALK_CHOICES, "slot": "walk", "match": None},
    "inout": {"question": "실내가 좋으세요, 바깥이 좋으세요?", "choices": INOUT_CHOICES, "slot": "inout", "match": None},
    "sight": {"question": "어떤 구경이 좋으세요?", "choices": ["궁 · 한옥", "전시 · 작품", "시장 · 거리", "공원 · 숲"],
              "slot": None, "match": {"궁 · 한옥": ["궁 · 한옥"], "전시 · 작품": ["그림 · 사진", "박물관 · 기념관"],
                                      "시장 · 거리": ["시장 · 거리", "광장"], "공원 · 숲": ["공원"]}},
    "budget": {"question": "한 끼에 얼마까지 쓰실래요?", "choices": ["만 원 안쪽", "2만 원 안쪽", "3만 원 넘어도 돼요", "잘 모르겠어요"],
               "slot": None, "match": None},
    "scenery": {"question": "어떤 풍경이 좋으세요?", "choices": ["물가", "숲길", "높은 곳 전망", "탁 트인 광장"],
                "slot": None, "match": {"물가": ["물가"], "숲길": ["숲 · 산"], "높은 곳 전망": ["전망"], "탁 트인 광장": ["광장"]}},
    "fee": {"question": "돈 내는 곳도 괜찮으세요?", "choices": ["괜찮아요", "무료인 곳만요", "잘 모르겠어요"],
            "slot": None, "match": {"무료인 곳만요": ["무료"]}},
    "show": {"question": "어떤 걸 보고 싶으세요?", "choices": ["그림 · 사진", "음악 공연", "연극 · 영화", "만들기 체험"],
             "slot": None, "match": {"그림 · 사진": ["그림 · 사진"], "음악 공연": ["음악 공연"], "연극 · 영화": ["연극 · 영화"],
                                     "만들기 체험": ["만들기 체험"]}},
    "nature": {"question": "자연은 어디가 좋으세요?", "choices": ["숲 · 산", "물가", "꽃 · 정원", "아무 공원이나"],
               "slot": None, "match": {"숲 · 산": ["숲 · 산"], "물가": ["물가"], "꽃 · 정원": ["꽃 · 정원"], "아무 공원이나": ["공원"]}},
    "rest": {"question": "어디서 쉬고 싶으세요?", "choices": ["숲 그늘", "물가", "조용한 전시장", "음악 들으며"],
             "slot": None, "match": {"숲 그늘": ["숲 · 산"], "물가": ["물가"], "조용한 전시장": ["그림 · 사진"], "음악 들으며": ["음악 공연"]}},
    "festa": {"question": "북적이는 축제도 좋으세요?", "choices": ["축제 좋아요", "조용한 곳이 좋아요", "잘 모르겠어요"],
              "slot": None, "match": {"축제 좋아요": ["축제", "광장"], "조용한 곳이 좋아요": ["공원", "그림 · 사진"]}},
    "old": {"question": "옛것과 새것, 어느 쪽이 끌리세요?", "choices": ["궁 · 한옥", "요즘 전시", "둘 다 좋아요"],
            "slot": None, "match": {"궁 · 한옥": ["궁 · 한옥", "박물관 · 기념관"], "요즘 전시": ["그림 · 사진", "만들기 체험"]}},
}

# 매번 새로운 질문 (variety): 같은 뜻 다른 말투. 선택지 · match는 은행 그대로예요. walk · inout 칸 질문은 화면과 같게 고정
BANK_ALT: dict[str, list[str]] = {
    "sight": ["어떤 걸 구경하고 싶으세요?", "구경은 어느 쪽이 끌리세요?"],
    "budget": ["한 끼는 얼마쯤 생각하세요?", "밥값은 얼마까지 괜찮으세요?"],
    "scenery": ["어떤 경치를 보고 싶으세요?", "보고 싶은 풍경이 있으세요?"],
    "fee": ["입장료 있는 곳도 괜찮으세요?", "돈 드는 곳도 가 보실래요?"],
    "show": ["어떤 걸 보러 가고 싶으세요?", "보고 싶은 게 있으세요?"],
    "nature": ["어떤 자연이 좋으세요?", "자연 속이라면 어디가 좋으세요?"],
    "rest": ["쉬기 좋은 곳은 어디가 끌리세요?", "어떤 곳에서 쉬고 싶으세요?"],
    "festa": ["사람 많은 축제도 괜찮으세요?", "북적이는 곳은 어떠세요?"],
    "old": ["옛날 것과 요즘 것, 어느 쪽이 좋으세요?", "옛 정취와 요즘 전시, 뭐가 끌리세요?"],
}


def _key(s: str) -> str:
    import re

    return re.sub(r"[\s?.!,·~]", "", s or "")


def bank_id_of(text: str | None) -> str | None:
    """은행 질문이나 그 다른 말투면 은행 id."""
    k = _key(text or "")
    if not k:
        return None
    for qid, b in BANK.items():
        if _key(b["question"]) == k or any(_key(a) == k for a in BANK_ALT.get(qid, [])):
            return qid
    return None


Q4_POOL = {
    "바람 쐬기": ["walk", "nature", "scenery", "festa"],
    "구경하기": ["sight", "show", "old", "festa", "fee"],
    "맛있는 것": ["budget"],
    "조용히 쉬기": ["inout", "rest", "nature"],
    None: ["inout", "sight", "nature", "show"],
}
# 어느 '하고 싶은 것'에서든 물어도 되는 은행 질문
ANY_WANT = ("walk", "inout", "fee")


def bank_fits_want(cond: Conditions, qid: str) -> bool:
    """'하고 싶은 것'과 맞는 은행 질문인지. 맛있는 것을 골랐는데 궁 · 한옥 구경을 묻지 않게 해요."""
    want = want_of(cond)
    if want is None:
        return True
    return qid in ANY_WANT or qid in Q4_POOL.get(want, Q4_POOL[None])


Q5_FALLBACK = {"바람 쐬기": "scenery", "구경하기": "fee", "맛있는 것": "walk", "조용히 쉬기": "walk", None: "walk"}


def today_items(cond: Conditions) -> list[dict] | None:
    try:
        from app.data import filter_places, weather

        return filter_places.filter_places(cond, config.now(), weather.today(), [])
    except Exception as e:
        log.warning("오늘 후보 오류: %s", type(e).__name__)
        return None


def skipped(cond: Conditions, qid: str) -> bool:
    return qid == "walk" and cond.body == "좀 무거워요"


def asked_ids(cond: Conditions) -> set[str]:
    out = {qid for qid in (bank_id_of(x.q) for x in cond.ai) if qid}
    if cond.basic.walk:
        out.add("walk")
    if cond.basic.inout:
        out.add("inout")
    return out


def bank_counts(qid: str, items: list[dict]) -> dict[str, int] | None:
    from app.question.themes import themes_of

    match = BANK[qid]["match"]
    if not match:
        return None
    th = [themes_of(it["place"]) for it in items]
    counts = {c: sum(1 for t in th if set(ts) & t) for c, ts in match.items()}
    if qid == "fee":
        counts["괜찮아요"] = len(items)  # 입장료가 있어도 된다는 답은 무료인 곳도 포함해요.
    return counts


def _splits(qid: str, items: list[dict] | None) -> bool:
    if items is None:
        return True
    counts = bank_counts(qid, items)
    if counts is None:
        return True
    live = [n for n in counts.values() if n > 0]
    return len(live) >= 2 and any(n < len(items) for n in live)


def narrowed_items(cond: Conditions, items: list[dict] | None) -> list[dict] | None:
    """은행도 에이전트와 같은, 앞 답으로 좁힌 후보를 써요."""
    if items is None:
        return None
    from app.question.agent import narrowed
    from app.question.themes import themes_of, wish_themes

    left = narrowed(cond, items)
    # 에이전트가 만든 '북적이는 시장' 같은 선택지도 은행의 주제와 연결해요.
    clues = [cond.extra.place, *cond.extra.wish, *(x.a for x in cond.ai if x.a)]
    for clue in clues:
        ts = wish_themes(clue)
        if ts:
            matched = [it for it in left if ts & themes_of(it["place"])]
            if matched:
                left = matched
    return left


def overlaps_asked(cond: Conditions, choices: list[str]) -> bool:
    new = {_key(c) for c in choices if c not in ("잘 모르겠어요", "둘 다 좋아요", "상관없어요")}
    return any(len(new & {_key(c) for c in x.choices}) >= 2 for x in cond.ai)


def bank_available(cond: Conditions, qid: str, items: list[dict] | None) -> bool:
    """모든 은행 진입점의 공통 검사: 반복 · 바람 · 남은 후보를 나누는지."""
    from app.question.themes import wish_themes

    selected = answer_themes(cond)
    for clue in [cond.extra.place, *cond.extra.wish, *(x.a for x in cond.ai if x.a)]:
        selected.update(wish_themes(clue))
    # '시장'을 이미 골랐으면 시장/궁/전시를 다시 고르게 하지 않아요.
    # 한 장소가 시장과 한옥 등 여러 주제에 속해도 이 결정은 유지해요.
    repeats_topic = any(selected & set(ts) for ts in (BANK[qid]["match"] or {}).values())
    return (qid not in asked_ids(cond) and not skipped(cond, qid)
            and bank_fits_want(cond, qid)
            and not repeats_topic
            and not overlaps_asked(cond, BANK[qid]["choices"])
            and _splits(qid, narrowed_items(cond, items)))


def q4_id(cond: Conditions, items: list[dict] | None) -> str | None:
    pool = Q4_POOL.get(want_of(cond), Q4_POOL[None])
    for qid in pool:
        if bank_available(cond, qid, items):
            return qid
    return None


def q5_fallback_id(cond: Conditions, items: list[dict] | None) -> str | None:
    qid = Q5_FALLBACK.get(want_of(cond), "walk")
    if not bank_available(cond, qid, items) or qid == q4_id(cond, items):
        return None
    return qid


def live_choices(qid: str, items: list[dict] | None) -> list[str]:
    b = BANK[qid]
    if items is None:
        return list(b["choices"])
    counts = bank_counts(qid, items)
    if counts is None:
        return list(b["choices"])
    kept = [c for c in b["choices"] if c not in counts or counts[c] > 0]
    if sum(1 for c in kept if c in counts) < 2:
        return list(b["choices"])
    return kept


def bank_question(qid: str, items: list[dict] | None, no: int | None = 4) -> dict:
    from app.question import variety

    b = BANK[qid]
    text = variety.pick_text([b["question"], *BANK_ALT.get(qid, [])])
    choices = live_choices(qid, items)
    if not b["slot"]:
        # '잘 모르겠어요' 같은 고르지 않는 답은 맨 뒤에 둬요
        keep = [c for c in choices if c in ("잘 모르겠어요", "둘 다 좋아요")]
        choices = variety.shuffle([c for c in choices if c not in keep]) + keep
    q = {"done": False, "id": qid, "question": text, "choices": choices, "slot": b["slot"], "source": "fixed"}
    if no is not None:
        q = {"done": False, "no": no, **{k: v for k, v in q.items() if k != "done"}}
    return q


def answer_themes(cond: Conditions) -> set[str]:
    from app.question.themes import ALL_THEMES

    out: set[str] = set()
    for x in cond.ai:
        if not x.a:
            continue
        qid = bank_id_of(x.q)
        b = BANK[qid] if qid else None
        if b is not None:
            out.update((b["match"] or {}).get(x.a, []))
        elif x.a in ALL_THEMES:
            out.add(x.a)
        else:
            for bb in BANK.values():
                out.update((bb["match"] or {}).get(x.a, []))
    return out


def best_bank(cond: Conditions, items: list[dict] | None) -> str | None:
    from app.data.preferences import split_score

    items = narrowed_items(cond, items)
    if not items:
        return None
    best, score = None, -1.0
    for qid in BANK:
        if qid == "budget" or not bank_available(cond, qid, items):
            continue
        counts = bank_counts(qid, items)
        if counts is None or not _splits(qid, items):
            continue
        live = [n for n in counts.values() if n > 0]
        s = split_score(live, len(items))
        if s > score:
            best, score = qid, s
    return best


def next_step(cond: Conditions, answered: list[int]) -> dict:
    """번호로 진행하는 길 (AI 없이). 질문 수는 config.question_total()로 고정 (기본 7: no 0~6)."""
    from app.question.lead import lead_question

    total = config.question_total()
    ans = set(answered)
    open_mode = config.question_start() == "open"

    def stamp(q: dict) -> dict:
        return {**q, "total": total}

    if open_mode and 0 not in ans:
        return stamp(dict(OPEN_Q))
    if open_mode and not cond.body and 1 not in ans:
        return stamp(dict(BODY_Q))
    if open_mode and not cond.time and 2 not in ans:
        return stamp(dict(TIME_Q))
    if 3 not in ans and not cond.basic.want:
        return stamp(dict(WANT_Q))
    for no in range(config.QUESTION_FIXED, total):
        if no in ans:
            continue
        if no <= 4:
            # 3(하고 싶은 것을 이미 들었으면) · 4: 앞 말을 이어 받는 발전 질문 → 은행
            items = narrowed_items(cond, today_items(cond))
            lead = lead_question(cond, items or [])
            if lead:
                return stamp({"done": False, "no": no, **{k: v for k, v in lead.items() if k != "done"}})
            qid = q4_id(cond, items)
            if qid and qid not in asked_ids(cond):
                return stamp(bank_question(qid, items, no))
            if no == 3:
                continue
        fb = None
        if config.question_mode() == "single":
            items = narrowed_items(cond, today_items(cond))
            fid = q5_fallback_id(cond, items)
            fb = bank_question(fid, items, no) if fid else None
        return stamp({"done": False, "no": no, "needsAi": True, "fallback": fb})
    return {"done": True}

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

Q4_POOL = {
    "바람 쐬기": ["walk", "nature", "scenery", "festa"],
    "구경하기": ["sight", "show", "old", "festa", "fee"],
    "맛있는 것": ["budget"],
    "조용히 쉬기": ["inout", "rest", "nature"],
    None: ["inout", "sight", "nature", "show"],
}
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
    qs = {x.q for x in cond.ai}
    out = {qid for qid, b in BANK.items() if b["question"] in qs}
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
    return {c: sum(1 for t in th if set(ts) & t) for c, ts in match.items()}


def _splits(qid: str, items: list[dict] | None) -> bool:
    if items is None:
        return True
    counts = bank_counts(qid, items)
    if counts is None:
        return True
    live = [n for n in counts.values() if n > 0]
    return len(live) >= 2 and any(n < len(items) for n in live)


def q4_id(cond: Conditions, items: list[dict] | None) -> str | None:
    pool = Q4_POOL.get(want_of(cond), Q4_POOL[None])
    asked = asked_ids(cond)
    for qid in pool:
        if not skipped(cond, qid) and qid not in asked and _splits(qid, items):
            return qid
    first = pool[0]
    return None if skipped(cond, first) else first


def q5_fallback_id(cond: Conditions, items: list[dict] | None) -> str | None:
    qid = Q5_FALLBACK.get(want_of(cond), "walk")
    if skipped(cond, qid) or qid in asked_ids(cond) or qid == q4_id(cond, items):
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
    b = BANK[qid]
    q = {"done": False, "id": qid, "question": b["question"], "choices": live_choices(qid, items),
         "slot": b["slot"], "source": "fixed"}
    if no is not None:
        q = {"done": False, "no": no, **{k: v for k, v in q.items() if k != "done"}}
    return q


def answer_themes(cond: Conditions) -> set[str]:
    from app.question.themes import ALL_THEMES

    out: set[str] = set()
    by_q = {b["question"]: b for b in BANK.values()}
    for x in cond.ai:
        if not x.a:
            continue
        b = by_q.get(x.q)
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

    if not items:
        return None
    asked = asked_ids(cond)
    best, score = None, -1.0
    for qid in BANK:
        if qid == "budget" or qid in asked or skipped(cond, qid):
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
    from app.question.lead import lead_question

    ans = set(answered)
    open_mode = config.question_start() == "open"
    if open_mode and 0 not in ans:
        return dict(OPEN_Q)
    if open_mode and not cond.body and 1 not in ans:
        return dict(BODY_Q)
    if open_mode and not cond.time and 2 not in ans:
        return dict(TIME_Q)
    if 3 not in ans and not cond.basic.want:
        return dict(WANT_Q)
    if 4 not in ans:
        items = today_items(cond)
        lead = lead_question(cond, items or [])
        if lead:
            return {"done": False, "no": 4, **{k: v for k, v in lead.items() if k != "done"}}
        qid = q4_id(cond, items)
        if qid and qid not in asked_ids(cond):
            return bank_question(qid, items, 4)
    if 5 not in ans:
        fb = None
        if config.question_mode() == "single":
            items = today_items(cond)
            fid = q5_fallback_id(cond, items)
            fb = bank_question(fid, items, 5) if fid else None
        return {"done": False, "no": 5, "needsAi": True, "fallback": fb}
    return {"done": True}

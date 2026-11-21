"""질문 0(대화) 해석 · "이렇게 들었어요" · 지우기 · 이동 범위."""

import re

from app import config
from app.guards import scrub_pii
from app.question.flow import BODY_CHOICES, INOUT_CHOICES, TIME_CHOICES, WALK_CHOICES, WANT_CHOICES, WHO_CHOICES
from app.schemas import Conditions, Range

UNKNOWN = "모름"
WHERE_CHOICES = ["실내", "바깥", "둘 다"]

BANNED = ["증상", "아프", "아픈", "통증", "병원", "질환", "약 ", "이름", "성함", "나이", "연세", "주소", "어디 사",
          "연락처", "전화", "주민"]
BODY_WORDS = ["무릎", "허리", "다리", "관절", "당뇨", "혈압", "수술", "치료", "진료", "약국"]
HINT_BODY = [*BODY_WORDS, "피곤", "힘들", "불편"]
# 질문 검사에서만 더 보는 몸 이야기 (첫 말 단서는 지우지 않게 BODY_WORDS와 따로 둬요). 몸 칸은 고정 질문이 물어요
Q_BODY_WORDS = ["몸은", "몸이", "몸 상태", "컨디션", "건강", "기운"]


def asks_body(q: str, choices: list[str] | None = None) -> bool:
    return has_banned(" ".join([q, *(choices or [])]), BODY_WORDS) or has_banned(q, Q_BODY_WORDS)
VAGUE = ["어디든", "아무데나", "아무 곳", "아무거나", "그냥", "몰라", "모름"]
OUTDOOR_WORDS = ("자전거", "따릉이", "등산", "캠핑", "피크닉", "소풍", "낚시", "단풍", "꽃구경", "벚꽃")
KEYS = ["place", "who", "wish", "want", "time", "body", "walk", "inout"]

OPEN_SYSTEM = f"""서울에 사는 어르신이 오늘 나들이에 대해 편하게 한 말을 읽고, 정해진 칸을 채워요.
말에 분명히 드러난 것만 채우고, 짐작해야 하면 "{UNKNOWN}"으로 둬요. 모르는 칸은 화면이 따로 물어봐요.

- body (오늘 컨디션): {BODY_CHOICES}. 피곤하다, 다리 · 무릎이 불편하다, 몸이 무겁다 → "좀 무거워요". 컨디션이 좋다 → "가뿐해요".
- time (다녀올 시간): {TIME_CHOICES}. 잠깐 · 한두 시간 · 서너 시간 → "반나절" (오후 · 저녁이라도 잠깐이면 이쪽), 오후 내내 · 대여섯 시간 → "한나절", 하루 종일 · 저녁까지 → "하루 종일".
- want (하고 싶은 것): {WANT_CHOICES}. 산책 · 바람 · 경치 → "바람 쐬기", 궁 · 전시 · 시장 구경 → "구경하기", 먹고 싶다 → "맛있는 것", 쉬고 싶다 · 차 한잔 → "조용히 쉬기".
- walk (걷는 양): {WALK_CHOICES}. 계단이 힘들다 · 오래 못 걷는다 → "조금만요". 많이 걷고 싶다 → "많이 걸어요".
- inout (실내 · 바깥): {INOUT_CHOICES}. 실내에서 → "실내가 좋아요", 밖에서 · 야외 → "바깥이 좋아요". 말에 실내 · 바깥 이야기가 없으면 "{UNKNOWN}" (하는 일로 짐작하는 건 wish_where 칸에).

단서 (칸에 담기지 않는 구체적인 바람. 말에 나온 것만, 없으면 빈 글 · 빈 목록)
- place: 가고 싶은 곳이나 동네 이름 하나, 10자 안쪽. 예: "한강", "경복궁", "북촌", "시장". 막연하면("어디든") 빈 글.
- who: 같이 가는 사람 {WHO_CHOICES} 중 하나, 말에 없으면 "{UNKNOWN}". 손녀 · 손자 → "손주", 아들 · 딸 → "자녀", 남편 · 아내 · 영감 → "배우자".
- wish: 하고 싶은 일, 많아야 2개, 각각 10자 안쪽의 짧은 말. 예: "차 한잔", "사진 찍기", "꽃 구경". 무엇을 좋아한다고만 해도 넣어요 (공룡을 좋아해 → "공룡 구경", 기차를 좋아해 → "기차 구경"). want 칸과 똑같은 말("바람 쐬기")이면 넣지 말고, want에 담았어도 더 구체적인 말("차 한잔", "시장 구경")이면 넣어.
- wish_where: wish에 담은 일을 보통 어디서 하나요. {WHERE_CHOICES} 중 하나.
  밖에서만 하는 일(자전거 · 낚시 · 등산 · 연날리기 · 배드민턴) → "바깥", 안에서만 하는 일(영화 · 연극 · 찜질 · 볼링) → "실내",
  둘 다 되는 일(차 한잔 · 사진 찍기 · 구경) → "둘 다". wish가 비었으면 "{UNKNOWN}".

어디가 아픈지, 병, 약, 이름, 나이, 주소, 연락처는 어느 칸 · 단서에도 옮기지 마요. 칸은 정해진 값만 써요."""

OPEN_SCHEMA = {
    "type": "object",
    "properties": {
        "body": {"type": "string", "enum": [*BODY_CHOICES, UNKNOWN]},
        "time": {"type": "string", "enum": [*TIME_CHOICES, UNKNOWN]},
        "want": {"type": "string", "enum": [*WANT_CHOICES, UNKNOWN]},
        "walk": {"type": "string", "enum": [*WALK_CHOICES, UNKNOWN]},
        "inout": {"type": "string", "enum": [*INOUT_CHOICES, UNKNOWN]},
        "place": {"type": "string"},
        "who": {"type": "string", "enum": [*WHO_CHOICES, UNKNOWN]},
        "wish": {"type": "array", "items": {"type": "string"}},
        "wish_where": {"type": "string", "enum": [*WHERE_CHOICES, UNKNOWN]},
    },
    "required": ["body", "time", "want", "walk", "inout", "place", "who", "wish", "wish_where"],
    "additionalProperties": False,
}

_ORDER = ["가장 적게", "조금만", "보통", "많이", "제한 없음"]
_WALK_MAP = {"많이 걸어요": "많이", "보통이에요": "보통", "조금만요": "조금만"}


def compute_range(body: str | None, time: str | None, walk: str | None) -> Range:
    one = {"반나절": 30, "한나절": 45, "하루 종일": 60}.get(time or "", 60)
    lvl = "제한 없음"
    avoid: list[str] = []
    if body == "보통이에요":
        lvl = "보통"
    if body == "좀 무거워요":
        one = min(one, 30)
        lvl = "조금만"
        avoid = ["산", "버스 환승"]
    if walk in _WALK_MAP:
        w = _WALK_MAP[walk]
        lvl = _ORDER[min(_ORDER.index(lvl), _ORDER.index(w))]
    return Range(oneWayMin=one, walk=lvl, avoid=avoid)


def has_banned(text: str, extra: list[str] | None = None) -> bool:
    t = (text or "") + " "
    return any(w in t for w in BANNED) or any(w in t for w in (extra or []))


def clean_hint(text, limit: int = 10) -> str | None:
    if not isinstance(text, str):
        return None
    t = re.sub(r"\s+", " ", text).strip(" .,!?~\"'")
    if not t or len(t) > limit:
        return None
    if any(v in t for v in VAGUE) or re.search(r"\d{3,}", t):
        return None
    if has_banned(t, HINT_BODY):
        return None
    return t


def apply(cond: Conditions, v: dict) -> tuple[Conditions, list[str]]:
    c = cond.model_copy(deep=True)
    filled: list[str] = []
    allowed = {"body": BODY_CHOICES, "time": TIME_CHOICES, "want": WANT_CHOICES, "walk": WALK_CHOICES,
               "inout": INOUT_CHOICES}
    basic_changed = False
    for k, choices in allowed.items():
        val = v.get(k)
        if val not in choices:
            continue
        if k in ("body", "time"):
            if getattr(c, k):
                continue
            setattr(c, k, val)
        else:
            if getattr(c.basic, k):
                continue
            setattr(c.basic, k, val)
        filled.append(k)
        basic_changed = True
    place = clean_hint(v.get("place"))
    if place and not c.extra.place:
        c.extra.place = place
        filled.append("place")
    who = v.get("who")
    if who in WHO_CHOICES and not c.extra.who:
        c.extra.who = who
        filled.append("who")
    if not c.extra.wish:
        wishes: list[str] = []
        for w in v.get("wish") or []:
            w = clean_hint(w)
            if w and w not in wishes and w != c.basic.want and w != c.extra.place:
                wishes.append(w)
        wishes = wishes[:2]
        if wishes:
            c.extra.wish = wishes
            filled.append("wish")
            if not c.basic.inout:
                where = v.get("wish_where")
                io = {"실내": "실내가 좋아요", "바깥": "바깥이 좋아요"}.get(where or "")
                if io is None and where == UNKNOWN and any(w.startswith(OUTDOOR_WORDS) for w in wishes):
                    io = "바깥이 좋아요"
                if io:
                    c.basic.inout = io
                    filled.append("inout")
    if basic_changed:
        c.range = compute_range(c.body, c.time, c.basic.walk)
    for f in filled:
        if f not in c.filled:
            c.filled.append(f)
    return c, filled


async def parse_open(cond: Conditions, text: str) -> tuple[Conditions, list[str]]:
    from app.llm.client import ask_json

    t = scrub_pii(re.sub(r"\s+", " ", text or "").strip())[:200]
    if not t or t == "잘 모르겠어요" or cond.fallback:
        return cond, []
    v = await ask_json(OPEN_SYSTEM, {"어르신의 말": t}, OPEN_SCHEMA, config.OPEN_AI_TIMEOUT)
    if not v:
        c, filled = outdoor_only(cond, t)
        c, more = place_only(c, t)
        return c, filled + more
    return apply(cond, v)


def place_only(cond: Conditions, t: str) -> tuple[Conditions, list[str]]:
    """AI가 늦거나 실패해도, 자료에 있는 장소 이름(서울숲 · 경복궁 …)을 말했으면 가고 싶은 곳으로 받아요."""
    if cond.extra.place:
        return cond, []
    from app.data import loader

    said = t.replace(" ", "")
    names = {(p.get("name") or "").replace(" ", "") for p in loader.places()}
    hits = [n for n in names if 3 <= len(n) <= 12 and n in said]
    if not hits:
        return cond, []
    c = cond.model_copy(deep=True)
    c.extra.place = max(hits, key=len)
    if "place" not in c.filled:
        c.filled.append("place")
    return c, ["place"]


def outdoor_only(cond: Conditions, t: str) -> tuple[Conditions, list[str]]:
    """AI가 늦거나 실패해도, 밖에서만 하는 일(자전거 · 등산 …)을 말했으면 실내 · 바깥은 다시 묻지 않아요."""
    if cond.basic.inout or not any(w in t for w in OUTDOOR_WORDS):
        return cond, []
    c = cond.model_copy(deep=True)
    c.basic.inout = "바깥이 좋아요"
    if "inout" not in c.filled:
        c.filled.append("inout")
    return c, ["inout"]


_LABELS = {
    "time": {"반나절": "3시간쯤", "한나절": "6시간쯤", "하루 종일": "하루 종일"},
    "body": {"가뿐해요": "몸 가뿐", "보통이에요": "몸 보통", "좀 무거워요": "몸 무거움"},
    "walk": {"많이 걸어요": "많이 걷기", "보통이에요": "보통 걷기", "조금만요": "조금만 걷기"},
    "inout": {"실내가 좋아요": "실내", "바깥이 좋아요": "바깥", "둘 다 좋아요": "실내 · 바깥 다"},
}


def _value(cond: Conditions, key: str):
    if key in ("body", "time"):
        return getattr(cond, key)
    if key in ("want", "walk", "inout"):
        return getattr(cond.basic, key)
    return getattr(cond.extra, key)


def heard(cond: Conditions, filled: list[str]) -> dict:
    items = []
    for k in KEYS:
        if k not in filled:
            continue
        v = _value(cond, k)
        if not v:
            continue
        if k == "wish":
            for w in v:
                items.append({"key": "wish", "value": w, "label": w})
        elif k == "who":
            items.append({"key": k, "value": v, "label": "혼자" if v == "혼자" else f"{v}랑"})
        else:
            items.append({"key": k, "value": v, "label": _LABELS.get(k, {}).get(v, v)})
    if not items:
        return {"title": "몇 가지만 여쭤볼게요", "text": "몇 가지만 여쭤볼게요", "items": []}
    return {"title": "이렇게 들었어요", "text": "이렇게 들었어요: " + " · ".join(i["label"] for i in items),
            "items": items}


def forget(cond: Conditions, key: str, value: str | None) -> Conditions:
    if key not in KEYS:
        return cond
    c = cond.model_copy(deep=True)
    if key == "wish":
        c.extra.wish = [w for w in c.extra.wish if value is not None and w != value]
        if not c.extra.wish:
            c.filled = [f for f in c.filled if f != "wish"]
        return c
    if key in ("body", "time"):
        setattr(c, key, None)
    elif key in ("want", "walk", "inout"):
        setattr(c.basic, key, None)
    else:
        setattr(c.extra, key, None)
    c.filled = [f for f in c.filled if f != key]
    if key in ("body", "time", "walk"):
        c.range = compute_range(c.body, c.time, c.basic.walk)
    return c

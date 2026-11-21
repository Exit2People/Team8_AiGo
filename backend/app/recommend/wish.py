"""바람(하고 싶은 일) · 가고 싶은 곳 · 같이 가는 사람 맞추기 (질문 · 추천 공통)."""

_COMMON = {"구경", "보기", "하기", "가기", "걷기", "먹기", "한잔", "좀", "가서", "보러", "하러"}
_MOOD_KEYS = [
    (("차", "커피", "찻집", "카페"), "찻집"),
    (("물", "강", "호수", "개울", "냇가"), "물가"),
    (("숲", "나무"), "숲"),
    (("역사", "옛날", "옛"), "역사"),
    (("전통", "한옥"), "전통"),
    (("경치", "전망", "야경"), "전망"),
    (("전시", "그림", "작품"), "전시"),
    (("공연", "음악"), "공연"),
    (("동물",), "동물"),
    (("산책", "걷"), "산책"),
    (("골목",), "골목"),
    (("시장", "장보"), "시장"),
    (("앉", "벤치"), "벤치"),
    (("북적", "사람 구경"), "북적이는 곳"),
    (("조용",), "조용한 곳"),
]


def place_text(p: dict) -> str:
    ev = p.get("event") or {}
    parts = [p.get("name") or "", p.get("kind") or "", *(p.get("mood") or []), *(p.get("wants") or []),
             ev.get("sub") or "", ev.get("venue") or ""]
    return " ".join(x for x in parts if x)


def wish_tokens(wish: str) -> list[str]:
    return [w for w in (wish or "").split() if len(w) >= 2 and w not in _COMMON]


def wish_moods(wish: str) -> set[str]:
    text = wish or ""
    words = text.split()
    out: set[str] = set()
    for keys, mood in _MOOD_KEYS:
        for k in keys:
            if len(k) == 1:
                if any(w.startswith(k) for w in words):
                    out.add(mood)
            elif k in text:
                out.add(mood)
    return out


def wish_hits(p: dict, wish: str) -> bool:
    if wish_moods(wish) & set(p.get("mood") or []):
        return True
    text = place_text(p)
    return any(t in text for t in wish_tokens(wish))


def matched_wish(p: dict, wishes: list[str], expanded: list[str] | None = None) -> str | None:
    for w in wishes or []:
        if wish_hits(p, w):
            return w
    if wishes and expanded:
        text = place_text(p)
        if any(e in text for e in expanded):
            return wishes[0]
    return None


def matches_place(p: dict, place: str | None) -> bool:
    if not place:
        return False
    key = place.replace(" ", "")
    for v in (p.get("name"), p.get("gu"), p.get("station"), p.get("kind")):
        if v and key in v.replace(" ", ""):
            return True
    return False


# 명세(04_CONSTANTS)의 분위기는 손주 → 동물 · 넓은 곳, 혼자 → 조용한 곳이에요.
# 스냅숏 장소 DB에는 그 분위기 값이 0곳이라, 실제로 있는 값 중 같은 뜻인 것을 더해요 (09_ACCEPTANCE 3.10).
WHO_MOODS = {
    "손주": {"동물", "넓은 곳", "교육/체험", "산책"},
    "혼자": {"조용한 곳", "전시", "전시/미술", "역사"},
}


def matches_who(p: dict, who: str | None) -> bool:
    want = WHO_MOODS.get(who or "")
    if not want:
        return False
    return bool(set(p.get("mood") or []) & want)

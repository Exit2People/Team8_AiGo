"""장소 → 주제, 짧은 이름, 바람 말 → 주제."""

import re

_NAME_RULES = [
    ("궁 · 한옥", re.compile(r"(경복|창덕|창경|덕수|경희|경운)궁|운현궁|종묘|한옥|향교|고택|왕릉|선릉|정릉|태릉|사직단")),
    ("시장 · 거리", re.compile(r"시장|거리공연|골목|장터")),
    ("광장", re.compile(r"광장")),
]
_PARK_RULES = [
    ("물가", re.compile(r"한강|호수|강변|천변|저수지|계곡|폭포|연못|수변|물빛|하천|나루")),
    ("숲 · 산", re.compile(r"숲|산(근린|도시|자연|공원)|산$|수목원|둘레길|녹지|자연공원")),
    ("꽃 · 정원", re.compile(r"꽃|정원|식물원|수목원|장미|가든")),
    ("전망", re.compile(r"전망|타워|하늘|낙산|남산|봉수대")),
    ("자전거", re.compile(r"한강공원|서울숲|올림픽공원|월드컵공원|평화의공원|안양천|중랑천|탄천|양재천|홍제천|불광천|성내천")),
]
_SUB_THEMES = {
    "전시/미술": "그림 · 사진",
    "콘서트": "음악 공연", "클래식": "음악 공연", "국악": "음악 공연", "뮤지컬/오페라": "음악 공연",
    "오페라": "음악 공연", "독주/독창회": "음악 공연",
    "연극": "연극 · 영화", "영화": "연극 · 영화", "무용": "연극 · 영화", "뮤지컬": "연극 · 영화",
    "교육/체험": "만들기 체험",
}

ALL_THEMES = [
    "궁 · 한옥", "시장 · 거리", "광장", "물가", "숲 · 산", "꽃 · 정원", "전망", "자전거",
    "그림 · 사진", "음악 공연", "연극 · 영화", "만들기 체험", "축제", "공원", "박물관 · 기념관", "무료", "유료",
]

_WISH_KEYS = [
    (("숲", "산", "나무", "등산"), "숲 · 산"),
    (("물", "강", "한강", "호수", "바다"), "물가"),
    (("꽃", "정원", "식물"), "꽃 · 정원"),
    (("궁", "한옥", "옛", "역사"), "궁 · 한옥"),
    (("전시", "그림", "사진", "미술"), "그림 · 사진"),
    (("공연", "음악", "노래"), "음악 공연"),
    (("연극", "영화"), "연극 · 영화"),
    (("자전거", "따릉이"), "자전거"),
    (("체험", "만들"), "만들기 체험"),
    (("축제",), "축제"),
    (("시장",), "시장 · 거리"),
]


def themes_of(p: dict) -> set[str]:
    name = p.get("name") or ""
    ev = p.get("event") or {}
    text = name + " " + (ev.get("venue") or "")
    out: set[str] = set()
    for t, rx in _NAME_RULES:
        if rx.search(text):
            out.add(t)
    kind = p.get("kind")
    if kind == "공원":
        out.add("공원")
        for t, rx in _PARK_RULES:
            if rx.search(name):
                out.add(t)
    sub = ev.get("sub") or ""
    if sub in _SUB_THEMES:
        out.add(_SUB_THEMES[sub])
    if kind == "미술관":
        out.add("그림 · 사진")
    if kind == "박물관":
        out.add("박물관 · 기념관")
    if sub.startswith("축제"):
        out.add("축제")
    elif kind == "행사":
        out.add("실내 행사" if p.get("inout") == "실내" else "행사")
    fee = ((p.get("info") or {}).get("fee") or {}).get("free")
    if fee is True:
        out.add("무료")
    elif fee is False:
        out.add("유료")
    return out


def wish_themes(text: str | None) -> set[str]:
    out: set[str] = set()
    for w in (text or "").split():
        if w.startswith(("산책", "물건", "강아지")):
            continue
        for keys, t in _WISH_KEYS:
            if w.startswith(keys):
                out.add(t)
    return out


def short_name(p: dict, n: int = 14) -> str:
    orig = p.get("name") or ""
    s = re.sub(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>|〈[^〉]*〉|《[^》]*》", " ", orig)
    s = re.sub(r"^\s*(\d{4}년?|제?\d+회)\s*", "", s.strip())
    s = re.sub(r"\s+", " ", s).strip(" -·:_")
    if len(s) < 6:
        m = re.search(r"\[([^\]]*)\]", orig)
        s = f"{m.group(1)} {s}".strip() if m else orig
    if len(s) <= n:
        return s
    out = ""
    for w in s.split():
        cand = (out + " " + w).strip()
        if len(cand) > n:
            break
        out = cand
    return out or s[:n]

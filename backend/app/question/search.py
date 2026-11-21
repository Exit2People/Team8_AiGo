"""이름 조각(두 글자) + BM25 장소 검색 (04_CONSTANTS 7절). 질문 에이전트 find_places · 추천 에이전트 search_places 공통."""

import math
import re

from app.data import loader
from app.question.themes import ALL_THEMES, themes_of, wish_themes
from app.recommend.wish import matched_wish

K1, B = 1.2, 0.75
THEME_SCORE = 2.0
WISH_SCORE = 0.5
NAME_MIN = 2.0
KEEP_SHARE = 0.5
MIN_SCORE = 0.5
WORD_MIN, WORD_MAX = 2, 40
STOP = {"가고", "가서", "가요", "가기", "싶어요", "싶어", "싶다", "하고", "해요", "보고", "보러", "좋아요", "같이", "어디", "오늘",
        "그냥", "좀", "곳", "데"}
PARTICLES = ["이랑", "에서", "으로", "하고", "까지", "부터", "랑", "에", "로", "을", "를", "은", "는", "이", "가", "도", "와", "과", "의"]


def _words(text: str) -> list[str]:
    return re.findall(r"[0-9a-z가-힣]+", (text or "").lower())


def grams(text: str) -> list[str]:
    out = []
    for w in _words(text):
        out.extend([w] if len(w) == 1 else [w[i:i + 2] for i in range(len(w) - 1)])
    return out


def query_words(text: str) -> list[str]:
    out = []
    for w in _words(text):
        if w in STOP:
            continue
        for p in PARTICLES:
            if w.endswith(p) and len(w) - len(p) >= 2:
                w = w[: -len(p)]
                break
        out.append(w)
    return out


def query_grams(text: str) -> list[str]:
    return grams(" ".join(query_words(text)))


def word_ok(word: str) -> str | None:
    """도구 낱말 검사. 문제가 있으면 오류 글."""
    w = (word or "").strip()
    if not w:
        return "말이 비었어요. 낱말 하나로 찾아 주세요."
    if len(w) > WORD_MAX:
        return "40자보다 길어요. 낱말 몇 개(예: 한강, 꽃)로 다시 찾아 주세요."
    if len(w) < WORD_MIN and not (wish_themes(w) or w in ALL_THEMES):
        return "한 글자는 숲 · 산 · 꽃처럼 주제가 되는 말만 돼요. 2자 이상으로 찾아 주세요."
    return None


def place_scores(items: list[dict], word: str) -> list[tuple[dict, float]]:
    """(항목, 점수) 높은 순. 남기는 규칙은 3.6절."""
    if not items:
        return []
    names = [p.get("name") or "" for p in loader.places()] + [it["place"].get("name") or "" for it in items]
    docs = [grams(n) for n in names]
    n_docs = len(docs)
    avg = sum(len(d) for d in docs) / max(1, n_docs)
    df: dict[str, int] = {}
    for d in docs:
        for g in set(d):
            df[g] = df.get(g, 0) + 1
    q = query_grams(word)
    want_themes = set(wish_themes(word)) | ({word} if word in ALL_THEMES else set())
    rows = []
    for it in items:
        p = it["place"]
        d = grams(p.get("name") or "")
        name = 0.0
        for g in set(q):
            tf = d.count(g)
            if not tf:
                continue
            idf = math.log(1 + (n_docs - df.get(g, 0) + 0.5) / (df.get(g, 0) + 0.5))
            name += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(d) / max(avg, 1e-9)))
        if name < NAME_MIN:
            name = 0.0
        theme = THEME_SCORE if want_themes & themes_of(p) else 0.0
        wish = WISH_SCORE if matched_wish(p, [word]) else 0.0
        rows.append((it, name, theme, name + theme + wish))
    top = max((r[1] for r in rows), default=0.0)
    keep = [r for r in rows if r[2] > 0 or (r[1] > 0 and r[1] >= KEEP_SHARE * top)]
    if not keep:
        keep = [r for r in rows if r[3] >= MIN_SCORE]
    keep.sort(key=lambda r: (-r[3], r[0]["route"].get("totalMin", 0)))
    return [(r[0], r[3]) for r in keep]

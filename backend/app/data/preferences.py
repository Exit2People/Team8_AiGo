"""질문 5 기준(kind · event · fee · inout · mood) 세기 · 복원."""

from app.schemas import Conditions

QUESTION_PREFIX = {"kind": "장소 종류는", "event": "행사는", "fee": "입장료는", "inout": "실내외는", "mood": "분위기는"}
DEFAULT_QUESTION = {
    "kind": "장소 종류는 어떤 게 좋으세요?",
    "event": "행사는 어떤 게 끌리세요?",
    "fee": "입장료는 어느 쪽이 좋으세요?",
    "inout": "실내외는 어느 쪽이 좋으세요?",
    "mood": "분위기는 어떤 게 좋으세요?",
}
_SHOW = {"콘서트", "클래식", "연극", "국악", "무용", "뮤지컬", "뮤지컬/오페라", "오페라", "독주/독창회"}


def place_values(p: dict, crit: str) -> set[str]:
    if crit == "kind":
        return {p.get("kind")} if p.get("kind") else set()
    if crit == "event":
        sub = (p.get("event") or {}).get("sub") or ""
        if p.get("kind") != "행사" or not sub:
            return set()
        if sub.startswith("축제"):
            return {"축제"}
        if sub in _SHOW:
            return {"공연"}
        if sub == "전시/미술":
            return {"전시"}
        if sub == "교육/체험":
            return {"체험"}
        return set()
    if crit == "fee":
        f = ((p.get("info") or {}).get("fee") or {}).get("free")
        return {"무료"} if f is True else ({"유료"} if f is False else set())
    if crit == "inout":
        v = p.get("inout")
        if v == "둘 다":
            return {"실내", "바깥"}
        return {v} if v else set()
    if crit == "mood":
        return set(p.get("mood") or [])
    return set()


def split_score(groups: list[int], total: int) -> float:
    if not groups or total <= 0:
        return 0.0
    return round(1 - sum(groups) / (len(groups) * total), 3)


def criteria(places: list[dict], skip: set[str] | None = None) -> list[dict]:
    skip = skip or set()
    total = len(places)
    out = []
    for crit in QUESTION_PREFIX:
        if crit in skip:
            continue
        by: dict[str, set[str]] = {}
        for p in places:
            for v in place_values(p, crit):
                by.setdefault(v, set()).add(p.get("id"))
        seen: list[set[str]] = []
        choices: list[tuple[str, int]] = []
        for v, ids in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            if not (1 <= len(v) <= 10) or len(ids) >= total or ids in seen:
                continue
            seen.append(ids)
            choices.append((v, len(ids)))
            if len(choices) == 4:
                break
        if len(choices) >= 2:
            out.append({
                "id": crit, "prefix": QUESTION_PREFIX[crit], "question": DEFAULT_QUESTION[crit],
                "choices": [c for c, _ in choices], "counts": {c: n for c, n in choices},
                "score": split_score([n for _, n in choices], total),
            })
    out.sort(key=lambda c: -c["score"])
    return out


def selected(cond: Conditions) -> tuple[str, str] | None:
    for x in reversed(cond.ai):
        if not x.a:
            continue
        for crit, pre in QUESTION_PREFIX.items():
            if x.q.startswith(pre + " "):
                return crit, x.a
    return None

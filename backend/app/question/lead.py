"""발전 질문: 질문 0에서 들은 말을 오늘 갈 수 있는 곳 이름으로 이어 물어요 (AI 없음)."""

from app.question import variety
from app.question.themes import short_name, themes_of, wish_themes
from app.recommend.wish import matched_wish
from app.schemas import Conditions

LOOSE_SHARE = 0.6
_STRICT_SKIP = {"구경", "산책", "하기", "보기", "가기", "한잔"}


def _norm(s: str) -> str:
    for ch in " ?.!,·~":
        s = s.replace(ch, "")
    return s


def eun_neun(word: str) -> str:
    if not word:
        return "은"
    c = word[-1]
    if "가" <= c <= "힣":
        return "은" if (ord(c) - 0xAC00) % 28 else "는"
    return "은"


def _strict(p: dict, wish: str) -> bool:
    name = p.get("name") or ""
    for w in wish.split():
        if len(w) >= 2 and w not in _STRICT_SKIP and w in name:
            return True
    return bool(wish_themes(wish) & themes_of(p))


def already_led(cond: Conditions) -> bool:
    return any(x.q.endswith("어디가 끌리세요?") or x.q.endswith("어디가 좋으세요?") for x in cond.ai)


def lead_question(cond: Conditions, items: list[dict]) -> dict | None:
    if not items or already_led(cond):
        return None
    asked = {_norm(x.q) for x in cond.ai}
    tries: list[tuple[str, list[dict]]] = []
    place = cond.extra.place
    if place:
        key = place.replace(" ", "")
        tries.append((variety.pick_text([f"{place} 쪽, 어디가 끌리세요?", f"{place} 근처는 어디가 끌리세요?"]),
                      [it for it in items if key in (it["place"].get("name") or "").replace(" ", "")]))
        for t in sorted(wish_themes(place)):
            word = t.replace(" · ", "이나 ")
            tries.append((f"{word} 중에선 어디가 끌리세요?", [it for it in items if t in themes_of(it["place"])]))
    for w in cond.extra.wish:
        q = variety.pick_text([f"{w}{eun_neun(w)} 어디가 좋으세요?", f"{w}{eun_neun(w)} 이 중 어디가 좋으세요?"])
        tries.append((q, [it for it in items if _strict(it["place"], w)]))
        loose = [it for it in items if matched_wish(it["place"], [w])]
        if len(loose) <= LOOSE_SHARE * len(items):
            tries.append((q, loose))
    for q, found in tries:
        if _norm(q) in asked or len(q) > 25:
            continue
        found = sorted(found, key=lambda it: it["route"]["totalMin"])
        names: list[str] = []
        for it in found:
            n = short_name(it["place"])
            if n not in names:
                names.append(n)
            if len(names) == 3:
                break
        if len(names) >= 2:
            return {"done": False, "id": "lead", "question": q, "choices": variety.shuffle(names), "slot": None, "source": "lead"}
    return None


def lead_bonus(p: dict, cond: Conditions) -> float:
    n = short_name(p)
    return 6.0 if any(x.a == n for x in cond.ai) else 0.0

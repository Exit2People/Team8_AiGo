"""다녀온 곳 기억: 기기가 보낸 30일 안 id만 써요. 따로 저장하지 않아요. AI에는 이름 · 종류 · 구만."""

from collections import Counter

from app.data import loader


def visits_from_ids(ids: list[str]) -> list[dict]:
    out = []
    for pid in ids or []:
        p = loader.place_by_id(pid)
        if p:
            out.append(p)
    return out


def profile_text(ids: list[str]) -> str:
    vs = visits_from_ids(ids)
    if not vs:
        return "다녀온 곳 기록이 없어요."
    kinds = ", ".join(f"{k} {n}번" for k, n in Counter(p.get("kind") for p in vs).most_common(3))
    gus = ", ".join(f"{g} {n}번" for g, n in Counter(p.get("gu") for p in vs if p.get("gu")).most_common(3))
    return f"최근에 {len(vs)}곳을 다녀왔어요. 자주 간 종류: {kinds}. 자주 간 구: {gus}."


def history(ids: list[str], limit: int = 10) -> list[dict]:
    vs = visits_from_ids(ids)[-limit:]
    return [{"이름": p.get("name"), "종류": p.get("kind"), "구": p.get("gu")} for p in vs]

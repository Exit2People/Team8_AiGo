"""exp/agent-full 실측: 시험용 말마다 화면처럼 질문 7개(+1) → 추천을 돌려 JSON으로 남겨요.

쓰는 법 (서버를 먼저 띄워요: cd backend && uv run uvicorn app.main:app --port 8011)
    cd backend && uv run python ../docs/experiments/run_agent_full.py --base http://127.0.0.1:8011 --out ../docs/experiments/results_agent-full_key.json

- 화면(frontend/components/Flow.tsx)처럼 움직여요: 첫 말 → 몸 · 시간(못 들었으면) → 조건 묶음만 /questions/next 를 done까지.
  fallback 이면 화면처럼 기본 칸 질문(BASIC: want → walk → inout)으로 대신 묻고, 그 뒤로는 fallback: true 로 보내요.
- 화면의 MAX_FLEX_QUESTIONS(3) 제한은 따르지 않아요 (질문 7개 목표를 재려고). 답은 늘 첫 선택지예요.
- 키 · 좌표 같은 값은 출력하지 않아요. 결과에는 질문 · 답 · 추천 이름 · 걸린 시간만 남겨요.
"""

import argparse
import json
import pathlib
import time

import httpx

ORIGIN = {"id": "1120059000", "name": "금호1가동", "type": "동", "lat": 37.553669, "lng": 127.025056}
BASIC = [("want", "뭘 하고 싶으세요?", ["바람 쐬기", "구경하기", "맛있는 것", "조용히 쉬기"]),
         ("walk", "걷는 건 괜찮으세요?", ["많이 걸어요", "보통이에요", "조금만요"]),
         ("inout", "실내가 좋으세요, 바깥이 좋으세요?", ["실내가 좋아요", "바깥이 좋아요", "둘 다 좋아요"])]
FALLBACK_SIX = ["손주랑 자전거 타고 싶어", "무릎이 아파서 많이 못 걸어", "손주랑 공룡 보러 가고 싶어", "조용히 책 읽을 데",
                "맛있는 거 먹고 싶어", "잘 모르겠어"]
INOUT_WORDS = ("실내", "바깥", "야외")
WALK_WORDS = ("걷", "걸어", "걸으")


def base_cond() -> dict:
    return {"mode": "text", "origin": ORIGIN, "body": None, "time": None,
            "range": {"oneWayMin": 60, "walk": "제한 없음", "avoid": []},
            "basic": {"want": None, "walk": None, "inout": None}, "ai": [], "freeText": None,
            "extra": {"mood": None, "avoid": [], "place": None, "who": None, "wish": [], "expanded": []},
            "filled": [], "fallback": False, "exclude": []}


def compute_range(body, t, walk) -> dict:
    one = {"반나절": 30, "한나절": 45, "하루 종일": 60}.get(t or "", 60)
    order = ["가장 적게", "조금만", "보통", "많이", "제한 없음"]
    lvl, avoid = "제한 없음", []
    if body == "보통이에요":
        lvl = "보통"
    if body == "좀 무거워요":
        one, lvl, avoid = min(one, 30), "조금만", ["산", "버스 환승"]
    w = {"많이 걸어요": "많이", "보통이에요": "보통", "조금만요": "조금만"}.get(walk or "")
    if w:
        lvl = order[min(order.index(lvl), order.index(w))]
    return {"oneWayMin": one, "walk": lvl, "avoid": avoid}


def reasked(cond: dict, heard: set[str], q: dict) -> str | None:
    """첫 말에서 들은 칸을 다시 물었는지."""
    slot = q.get("slot")
    text = q.get("question") or ""
    if slot in heard:
        return slot
    if "inout" in heard and any(w in text for w in INOUT_WORDS):
        return "inout"
    if ("walk" in heard or cond.get("body") == "좀 무거워요") and any(w in text for w in WALK_WORDS):
        return "walk"
    if "who" in heard and ("누구" in text or "누구랑" in text):
        return "who"
    return None


def run_one(c: httpx.Client, text: str) -> dict:
    out: dict = {"text": text, "questions": [], "errors": []}
    cond = base_cond()
    t0 = time.monotonic()
    r = c.post("/questions/open", json={"conditions": cond, "text": text})
    out["openSec"] = round(time.monotonic() - t0, 2)
    r.raise_for_status()
    o = r.json()
    cond, filled = o["conditions"], o["filled"]
    out["heard"] = [i["label"] for i in o["heard"]["items"]]
    heard = set(filled)
    out["questions"].append({"no": 0, "question": "오늘 어떤 하루 보내고 싶으세요?", "answer": text, "source": "fixed"})
    if "body" not in filled:
        cond["body"] = "보통이에요"
        out["questions"].append({"no": 1, "question": "컨디션은 어떠세요?", "answer": "보통이에요", "source": "fixed"})
    if "time" not in filled:
        cond["time"] = "한나절"
        out["questions"].append({"no": 2, "question": "얼마나 나가 계실 건가요?", "answer": "한나절", "source": "fixed"})
    cond["range"] = compute_range(cond["body"], cond["time"], cond["basic"]["walk"])
    used_slots = {s for s in ("want", "walk", "inout") if cond["basic"][s]}
    for _ in range(10):
        t1 = time.monotonic()
        r = c.post("/questions/next", json=cond)
        sec = round(time.monotonic() - t1, 2)
        r.raise_for_status()
        q = r.json()
        if q.get("done"):
            out["doneSec"] = sec
            break
        if q.get("fallback") is True:
            b = next((x for x in BASIC if x[0] not in used_slots), None)
            cond["fallback"] = True
            if b is None:
                out["doneSec"] = sec
                break
            q = {"no": q.get("no"), "question": b[1], "choices": b[2], "slot": b[0], "source": "basic(화면 대신 길)"}
        a = q["choices"][0]
        row = {"no": q.get("no"), "total": q.get("total"), "question": q["question"], "choices": q["choices"],
               "answer": a, "source": q.get("source"), "slot": q.get("slot"), "sec": sec}
        for k in ("follows", "extra", "why", "id"):
            if q.get(k):
                row[k] = q[k]
        again = reasked(cond, heard, q)
        if again:
            row["reasked"] = again
        out["questions"].append(row)
        if q.get("slot") in ("want", "walk", "inout"):
            cond["basic"][q["slot"]] = None if a == "잘 모르겠어요" else a
            used_slots.add(q["slot"])
            cond["range"] = compute_range(cond["body"], cond["time"], cond["basic"]["walk"])
        else:
            cond["ai"].append({"q": q["question"], "choices": q["choices"], "a": a})
    t2 = time.monotonic()
    r = c.post("/recommend", json={"conditions": cond, "visited": []})
    out["recommendSec"] = round(time.monotonic() - t2, 2)
    r.raise_for_status()
    j = r.json()
    out["by"] = j.get("by")
    out["notFound"] = j.get("notFound")
    out["places"] = [{"name": x["place"]["name"], "reason": x["reason"], "min": x["route"].get("totalMin")}
                     for x in j.get("candidates") or []]
    out["relaxed"] = bool(j.get("relaxed"))
    out["expanded"] = j.get("expanded")
    qs = [x for x in out["questions"] if x["no"] is not None and x["no"] >= 3]
    out["summary"] = {
        "questionsTotal": len(out["questions"]),
        "free": len(qs),
        "followed": sum(1 for x in qs if x.get("follows") or x.get("source") == "lead"),
        "agent": sum(1 for x in qs if x.get("source") == "agent"),
        "extra": any(x.get("extra") for x in qs),
        "reasked": [x["reasked"] for x in qs if x.get("reasked")],
        "maxQuestionSec": max([x["sec"] for x in qs if "sec" in x] or [0]),
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8011")
    ap.add_argument("--out", required=True)
    ap.add_argument("--utterances", default=str(pathlib.Path(__file__).resolve().parents[3] / "SHARED_utterances.json"))
    ap.add_argument("--only", type=int, default=0, help="앞에서 몇 개만")
    ap.add_argument("--repeat", type=int, default=1, help="같은 말을 몇 번씩 (매번 새로운 질문 재기)")
    ap.add_argument("--pick", default="", help="쉼표로 고른 말 번호 (1부터), 예: 1,3,6")
    args = ap.parse_args()
    p = pathlib.Path(args.utterances)
    texts = [u["text"] for u in json.loads(p.read_text(encoding="utf-8"))] if p.exists() else FALLBACK_SIX
    if args.pick:
        texts = [texts[int(i) - 1] for i in args.pick.split(",")]
    if args.only:
        texts = texts[: args.only]
    texts = [t for t in texts for _ in range(args.repeat)]
    results = []
    with httpx.Client(base_url=args.base, timeout=40.0) as c:
        health = c.get("/health").json()
        for t in texts:
            try:
                res = run_one(c, t)
            except Exception as e:  # 한 말이 실패해도 나머지는 재요
                res = {"text": t, "error": type(e).__name__}
            results.append(res)
            s = res.get("summary", {})
            print(f"{t[:14]:14} | Q{s.get('questionsTotal')} 이어{s.get('followed')}/{s.get('free')} "
                  f"agent{s.get('agent')} | rec {res.get('by')} {res.get('recommendSec')}s | {res.get('error', '')}",
                  flush=True)
    variety = {}
    if args.repeat > 1:
        for t in dict.fromkeys(texts):
            runs = [r for r in results if r["text"] == t and "questions" in r]
            qs = [q["question"] for r in runs for q in r["questions"] if (q.get("no") or 0) >= 3]
            per_run = [len([q for q in r["questions"] if (q.get("no") or 0) >= 3]) for r in runs]
            variety[t] = {"runs": len(runs), "questions": len(qs), "distinct": len(set(qs)), "perRun": per_run}
            print(f"{t[:14]:14} | 질문 {len(qs)}개 중 서로 다른 문장 {len(set(qs))}개", flush=True)
    pathlib.Path(args.out).write_text(json.dumps({"health": {k: health.get(k) for k in ("ai", "jev", "agent", "question")},
                                                  "variety": variety, "results": results}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")


if __name__ == "__main__":
    main()

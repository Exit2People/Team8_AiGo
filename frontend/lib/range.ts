import type { Range, WalkLevel } from "./types";

/** 11_FRONTEND_SPEC 7절 · 04_CONSTANTS 4절 (서버 opening.compute_range 와 같은 표) */
const ORDER: WalkLevel[] = ["가장 적게", "조금만", "보통", "많이", "제한 없음"];
const WALK_ANS: Record<string, WalkLevel> = { "많이 걸어요": "많이", 보통이에요: "보통", 조금만요: "조금만" };

function narrower(a: WalkLevel, b: WalkLevel): WalkLevel {
  return ORDER.indexOf(a) <= ORDER.indexOf(b) ? a : b;
}

export function computeRange(body: string | null, time: string | null, walkAns: string | null): Range {
  let oneWayMin = time === "반나절" ? 30 : time === "한나절" ? 45 : 60;
  let walk: WalkLevel = "제한 없음";
  const avoid: string[] = [];
  if (body === "보통이에요") walk = "보통";
  if (body === "좀 무거워요") {
    oneWayMin = Math.min(oneWayMin, 30);
    walk = "조금만";
    avoid.push("산", "버스 환승");
  }
  if (walkAns && WALK_ANS[walkAns]) walk = narrower(walk, WALK_ANS[walkAns]);
  return { oneWayMin, walk, avoid };
}

const WALK_TEXT: Record<WalkLevel, string> = {
  "제한 없음": "걷는 양은 상관없는 곳",
  많이: "많이 걸어도 되는 곳",
  보통: "적당히 걷는 곳",
  조금만: "조금만 걷는 곳",
  "가장 적게": "거의 걷지 않는 곳",
};

export function rangeSentence(originName: string, r: Range): string {
  const av = r.avoid.filter((a) => a !== "버스 환승");
  return `${originName}에서 ${r.oneWayMin}분 안에 갈 수 있는, ${WALK_TEXT[r.walk]}${av.length ? ` (${av.join(" · ")} 빼고)` : ""}`;
}

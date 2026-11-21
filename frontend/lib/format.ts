import type { Candidate, Leg } from "./types";

/** 오전/오후 h:mm (15절) */
export function clockText(d = new Date()) {
  const h = d.getHours();
  const ap = h < 12 ? "오전" : "오후";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${ap} ${hh}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** "14:35" → "오후 2시 35분" (8.4) */
export function speakTime(t: string) {
  const m = /^(\d{1,2}):(\d{2})/.exec(t || "");
  if (!m) return t;
  const h = +m[1];
  const mm = +m[2];
  const ap = h < 12 ? "오전" : "오후";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${ap} ${hh}시${mm ? ` ${mm}분` : ""}`;
}

/** 노선 이름 묶기 (8.2) */
export function linesText(legs: Leg[]): string {
  const lines = Array.from(new Set(legs.map((l) => l.line).filter((x): x is string => !!x)));
  if (!lines.length) return "걸어서";
  if (lines.every((l) => /^\d+호선$/.test(l))) return lines.map((l) => l.replace("호선", "")).join("·") + "호선";
  return lines.join(" · ");
}

export function lastLeg(c: Candidate): Leg | undefined {
  const legs = c.route?.legs ?? [];
  return legs[legs.length - 1];
}

/** 타는 글 (8.4) */
export function rideText(l: Leg): string {
  const dir = l.direction;
  const stops = l.stops;
  const off = l.getOff;
  if (dir && stops) return `${dir} 열차로 ${stops}정거장 가요`;
  if (stops && off) return `${stops}정거장 가서 ${off}에서 내려요`;
  if (off) return `${off}에서 내려요`;
  if (stops) return `${stops}정거장 가요`;
  if (l.line) return `${l.line} 타고 가요`;
  return "타고 가요";
}

export function placeNameSize(name: string): number {
  const n = name.length;
  if (n <= 4) return 56;
  if (n === 5) return 48;
  if (n === 6) return 40;
  if (n <= 8) return 32;
  if (n <= 12) return 26;
  return 22;
}

export const fmtNum = (n: number) => n.toLocaleString("ko-KR");

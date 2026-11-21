/** 업적 배지 (11_FRONTEND_SPEC 11절) — 기기에만, 회원만 */
import data from "@/data/badges.json";
import { load, save, today } from "./device";

export type BadgeDef = { id: string; tier: number; hidden: boolean; name: string; condition: string; target: number; cheer: string; category?: string };
export type Tier = { tier: number; name: string; level: string };

export const BADGES = (data as unknown as { badges: BadgeDef[] }).badges;
export const TIERS = (data as unknown as { tiers: Tier[] }).tiers;

type Arrive = { id: string; kind: string; gu: string; date: string; hour: number; weather?: string };
type Log = { logins: number; recs: number; tickets: number; photos: number; reviews: number; chats: string[]; arrives: Arrive[]; runs: number; best: number };
type Rec = { log: Log; got: Record<string, number> };

const KEY = "aigo.badges";
const empty = (): Rec => ({ log: { logins: 0, recs: 0, tickets: 0, photos: 0, reviews: 0, chats: [], arrives: [], runs: 0, best: 0 }, got: {} });

function all(): Record<string, Rec> {
  return load<Record<string, Rec>>(KEY, {});
}
export function recOf(uid: string): Rec {
  const r = all()[uid];
  return r ? { log: { ...empty().log, ...r.log }, got: r.got ?? {} } : empty();
}
function put(uid: string, r: Rec) {
  const a = all();
  a[uid] = r;
  save(KEY, a);
}

const PARKS = ["공원", "산책길", "호수 산책길", "둘레길"];
const HOLIDAYS = [
  ["2026-02-16", "2026-02-18"], ["2026-09-24", "2026-09-26"], ["2027-02-06", "2027-02-09"],
  ["2027-09-14", "2027-09-16"], ["2028-01-26", "2028-01-28"], ["2028-10-02", "2028-10-05"],
];
const dayN = (d: string) => Math.floor((Date.parse(d + "T00:00:00Z") - Date.parse("1970-01-05T00:00:00Z")) / 86400_000);
const weekN = (d: string) => Math.floor(dayN(d) / 7);
const monthN = (d: string) => +d.slice(0, 4) * 12 + +d.slice(5, 7) - 1;
function longestRun(nums: number[]) {
  const u = Array.from(new Set(nums)).sort((a, b) => a - b);
  let best = 0;
  let cur = 0;
  for (let i = 0; i < u.length; i++) {
    cur = i && u[i] === u[i - 1] + 1 ? cur + 1 : 1;
    best = Math.max(best, cur);
  }
  return best;
}

/** 배지마다 지금 값 */
export function progress(id: string, r: Rec, hasHome: boolean): number {
  const l = r.log;
  const days = (list: Arrive[]) => new Set(list.map((a) => a.date)).size;
  switch (id) {
    case "b01-hello": return l.logins;
    case "b02-home": return hasHome ? 1 : 0;
    case "b03-question": return l.recs;
    case "b05-ticket": return l.tickets;
    case "b06-arrive": case "s01-steps": case "s02-ten": case "g03-fifty": return l.arrives.length;
    case "b07-photo": return l.photos;
    case "b08-review": case "s05-book": return l.reviews;
    case "b09-chat": return l.chats.length;
    case "b11-run": return l.runs;
    case "s03-regular": {
      const m: Record<string, Set<string>> = {};
      l.arrives.forEach((a) => (m[a.id] ??= new Set()).add(a.date));
      return Math.max(0, ...Object.values(m).map((s) => s.size));
    }
    case "s04-week": {
      const m: Record<number, Set<string>> = {};
      l.arrives.forEach((a) => (m[weekN(a.date)] ??= new Set()).add(a.date));
      return Math.max(0, ...Object.values(m).map((s) => s.size));
    }
    case "s06-greet": return new Set(l.chats).size;
    case "s07-park": return new Set(l.arrives.filter((a) => PARKS.includes(a.kind)).map((a) => a.id)).size;
    case "s08-palace": return new Set(l.arrives.filter((a) => a.kind === "고궁").map((a) => a.id)).size;
    case "s09-morning": return l.arrives.some((a) => a.hour < 8) ? 1 : 0;
    case "s10-rain": return l.arrives.some((a) => /비|눈|소나기/.test(a.weather ?? "")) ? 1 : 0;
    case "s11-run500": case "g08-landmarks": return l.best;
    case "g01-streak": return longestRun(l.arrives.map((a) => weekN(a.date)));
    case "g02-seoul": return new Set(l.arrives.map((a) => a.gu)).size;
    case "g04-seasons": return new Set(l.arrives.map((a) => { const m = +a.date.slice(5, 7); return m >= 3 && m <= 5 ? 0 : m <= 8 && m >= 6 ? 1 : m >= 9 && m <= 11 ? 2 : 3; })).size;
    case "g05-compass": return new Set(l.arrives.map((a) => a.kind)).size;
    case "g07-holiday": return l.arrives.some((a) => HOLIDAYS.some(([s, e]) => a.date >= s && a.date <= e)) ? 1 : 0;
    case "l01-seoul-all": return new Set(l.arrives.map((a) => a.id)).size;
    case "l02-year": return longestRun(l.arrives.map((a) => monthN(a.date)));
    case "l03-master": return BADGES.filter((b) => b.id !== "l03-master" && r.got[b.id]).length;
    default: return 0;
  }
}

export type BadgeEvent =
  | { ev: "login" | "recommend" | "ticket" | "photo" | "review" | "chat" | "check" }
  | { ev: "arrive"; id: string; kind: string; gu: string; weather?: string }
  | { ev: "run"; steps: number };

/** 기록하고 새로 얻은 배지를 돌려줘요 */
export function record(uid: string, e: BadgeEvent, hasHome: boolean): BadgeDef[] {
  const r = recOf(uid);
  const l = r.log;
  const d = today();
  switch (e.ev) {
    case "login": l.logins++; break;
    case "recommend": l.recs++; break;
    case "ticket": l.tickets++; break;
    case "photo": l.photos++; break;
    case "review": l.reviews++; break;
    case "chat": l.chats.push(d); break;
    case "run": l.runs++; l.best = Math.max(l.best, e.steps); break;
    case "arrive":
      if (!l.arrives.some((a) => a.id === e.id && a.date === d)) l.arrives.push({ id: e.id, kind: e.kind, gu: e.gu, date: d, hour: new Date().getHours(), weather: e.weather });
      break;
  }
  const fresh: BadgeDef[] = [];
  const judge = (b: BadgeDef) => {
    if (r.got[b.id]) return;
    if (progress(b.id, r, hasHome) >= b.target) {
      r.got[b.id] = Date.now();
      fresh.push(b);
    }
  };
  BADGES.filter((b) => b.id !== "l03-master").forEach(judge);
  BADGES.filter((b) => b.id === "l03-master").forEach(judge);
  put(uid, r);
  return fresh;
}

export const HIDDEN_IMG = "/aigo/badges/_hidden.svg";
export const badgeImg = (b: BadgeDef, got: boolean) => (b.hidden && !got ? HIDDEN_IMG : `/aigo/badges/${b.id}.svg`);

/** 화면에 보여 줄 배지 하나의 상태 */
export type BadgeState = { def: BadgeDef; earnedAt: string | null; cur: number; target: number };

/** 업적 화면 · 내 정보 카드에 보여 줄 모든 배지 상태(얻은 때 · 진행 정도) */
export function badgeStates(uid: string, hasHome: boolean): BadgeState[] {
  const r = recOf(uid);
  return BADGES.map((def) => {
    const at = r.got[def.id];
    const earnedAt = at ? new Date(at).toISOString() : null;
    const cur = progress(def.id, r, hasHome);
    return { def, earnedAt, cur: earnedAt ? def.target : Math.min(cur, def.target), target: def.target };
  });
}

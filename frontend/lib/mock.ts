/** 가짜 응답 (서버 없이 화면 흐름을 끝까지 돌리려고). 모양은 SHARED/03_API_CONTRACT.md 그대로 */
import { ApiError } from "./errors";
import { GUS, dongsOf } from "./geo";
import { computeRange } from "./range";
import type { ChatMessage, ChatState, Conditions, Me, OpenResp, QuestionResp, RankingResp, RecommendResp, ReviewsResp, Social } from "./types";
import { nickProblem } from "./nick";

export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

function flag(name: string) {
  try {
    return new URLSearchParams(location.search).has(name);
  } catch {
    return false;
  }
}
export const slowQuestion = () => flag("mockslow");

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

/* ---------- 질문 ---------- */
export function open(c: Conditions, text: string): OpenResp {
  const out = clone(c);
  const items: OpenResp["heard"]["items"] = [];
  const filled: string[] = [];
  const t = text || "";
  if (/한강/.test(t) && !out.extra.place) {
    out.extra.place = "한강";
    filled.push("place");
    items.push({ key: "place", value: "한강", label: "한강" });
  }
  const who = /손주/.test(t) ? "손주" : /친구/.test(t) ? "친구" : /혼자/.test(t) ? "혼자" : null;
  if (who && !out.extra.who) {
    out.extra.who = who;
    filled.push("who");
    items.push({ key: "who", value: who, label: who === "혼자" ? "혼자" : `${who}랑` });
  }
  if (/사진/.test(t)) {
    out.extra.wish = ["사진 찍기"];
    filled.push("wish");
    items.push({ key: "wish", value: "사진 찍기", label: "사진 찍기" });
  }
  if (/바람/.test(t) && !out.basic.want) {
    out.basic.want = "바람 쐬기";
    filled.push("want");
    items.push({ key: "want", value: "바람 쐬기", label: "바람 쐬기" });
  }
  if (/반나절|3시간/.test(t) && !out.time) {
    out.time = "반나절";
    filled.push("time");
    items.push({ key: "time", value: "반나절", label: "3시간쯤" });
  }
  out.filled = Array.from(new Set([...out.filled, ...filled]));
  out.range = computeRange(out.body, out.time, out.basic.walk);
  const title = items.length ? "이렇게 들었어요" : "몇 가지만 여쭤볼게요";
  return {
    conditions: out,
    filled,
    heard: { title, text: items.length ? `이렇게 들었어요: ${items.map((i) => i.label).join(" · ")}` : title, items },
    next: { done: false, no: 1, id: "body", question: "컨디션은 어떠세요?", choices: ["가뿐해요", "보통이에요", "좀 무거워요"], slot: "body", source: "fixed" },
  };
}

export function next(c: Conditions): QuestionResp {
  if (c.fallback) return { done: false, fallback: true };
  const n = c.ai.length + (c.basic.want ? 1 : 0) + (c.basic.walk ? 1 : 0) + (c.basic.inout ? 1 : 0);
  if (c.ai.length >= 3 || n >= 3) return { done: true };
  if (!c.ai.some((a) => a.q === "어떤 풍경이 좋으세요?"))
    return { done: false, question: "어떤 풍경이 좋으세요?", choices: ["물가", "숲길", "높은 곳 전망", "탁 트인 광장"], slot: null };
  if (!c.basic.want) return { done: false, question: "오늘은 뭐가 당기세요?", choices: ["바람 쐬기", "구경하기", "맛있는 것", "조용히 쉬기"], slot: "want" };
  if (!c.basic.inout) return { done: false, question: "실내가 좋으세요, 바깥이 좋으세요?", choices: ["실내가 좋아요", "바깥이 좋아요", "둘 다 좋아요"], slot: "inout" };
  return { done: true };
}

/* ---------- 추천 ---------- */
const PLACES: RecommendResp["candidates"] = [
  {
    place: { id: "PK-4", name: "서울숲", kind: "공원", gu: "성동구", lat: 37.5444, lng: 127.0374, photo: null },
    reason: "바람 쐬기 좋고\n갈아타지 않아도 돼요",
    open: { today: "항상 열림", lastEntry: null },
    route: {
      totalMin: 18,
      arriveAt: "10:48",
      transfers: 0,
      startWalkMin: 8,
      legs: [
        { kind: "탑승", station: "성수역", line: "2호선", mode: "지하철", getOff: "뚝섬역", stops: 1, tip: "출발 동에서 성수역까지 걸어서 약 8분" },
        { kind: "하차", station: "뚝섬역", exit: "8번", walkMin: 5 },
      ],
      source: "seoul",
    },
  },
  {
    place: { id: "PK-9", name: "여의도한강공원", kind: "한강공원", gu: "영등포구", lat: 37.5284, lng: 126.9327, photo: null },
    reason: "강바람을 맞으며\n천천히 걷기 좋아요",
    open: { today: "항상 열림", lastEntry: null },
    route: {
      totalMin: 34,
      arriveAt: "11:04",
      transfers: 1,
      startWalkMin: 6,
      legs: [
        { kind: "탑승", station: "왕십리역", line: "5호선", mode: "지하철", getOff: "여의나루역", stops: 11 },
        { kind: "하차", station: "여의나루역", exit: "2번", walkMin: 4 },
      ],
      source: "seoul",
    },
  },
  {
    place: { id: "CU-21", name: "국립중앙박물관", kind: "박물관", gu: "용산구", lat: 37.5239, lng: 126.9803, photo: null },
    reason: "실내라 편하게\n구경할 수 있어요",
    open: { today: "10:00~18:00", lastEntry: "17:30" },
    route: {
      totalMin: 29,
      arriveAt: "10:59",
      transfers: 1,
      startWalkMin: 7,
      legs: [
        { kind: "탑승", station: "왕십리역", line: "경의중앙선", mode: "지하철", getOff: "이촌역", stops: 4 },
        { kind: "환승", station: "이촌역", line: "4호선", mode: "지하철", getOff: "이촌역", stops: 0 },
        { kind: "하차", station: "이촌역", exit: "2번", walkMin: 6 },
      ],
      source: "seoul",
    },
  },
  {
    place: { id: "MK-3", name: "광장시장", kind: "전통시장", gu: "종로구", lat: 37.57, lng: 126.9996, photo: null },
    reason: "맛있는 걸 먹으며\n구경하기 좋아요",
    open: { today: "보통 09:00~19:00 (가게마다 달라요)", lastEntry: null },
    route: {
      totalMin: 22,
      arriveAt: "10:52",
      transfers: 0,
      startWalkMin: 6,
      legs: [
        { kind: "탑승", station: "왕십리역", line: "2호선", mode: "지하철", getOff: "을지로4가역", stops: 4 },
        { kind: "하차", station: "을지로4가역", exit: "4번", walkMin: 7 },
      ],
      source: "seoul",
    },
  },
];

export function recommend(c: Conditions): RecommendResp {
  if (flag("mocknone")) return { candidates: [], notFound: true, why: "none" };
  const now = new Date();
  const arrive = (min: number) => {
    const d = new Date(now.getTime() + min * 60_000);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };
  const left = PLACES.filter((p) => !c.exclude.includes(p.place.id));
  if (!left.length) return { candidates: [], notFound: true, why: "none" };
  return {
    candidates: clone(left.slice(0, 3)).map((p) => ({
      ...p,
      route: p.route && {
        ...p.route,
        arriveAt: arrive(p.route.totalMin),
        legs: p.route.legs.map((l, i) => (i === 0 && l.tip ? { ...l, tip: `${c.origin.name}에서 ${l.station}까지 걸어서 약 ${p.route?.startWalkMin}분` } : l)),
      },
    })),
    notFound: false,
    by: "rule",
    weather: { weather: "강수 없음", temperature: 8.2 },
    dataAsOf: now.toISOString(),
    expanded: null,
  };
}

const expected: Record<string, number> = { "PK-4": 3, "PK-9": 1 };
export function social(id: string): Social {
  return { expectedToday: expected[id] ?? 0, reviewCount: id === "PK-4" ? 6 : 0, topTags: [["걷기 편해요", 2]] };
}
export function expect(id: string, d: number) {
  expected[id] = Math.max(0, (expected[id] ?? 0) + d);
  return { expectedToday: expected[id] };
}

const REVIEWS = [
  { text: "단풍이 곱고 길이 완만했어요", tag: "걷기 편해요", nick: "솔바람" },
  { text: "벤치가 많아서 쉬어 가기 좋아요", tag: "쉴 곳이 많아요", nick: "꽃마중" },
  { text: "사슴을 봤어요. 손주가 좋아했어요", tag: "경치가 좋아요", nick: "도란도란" },
  { text: "아침에 오니 조용하고 좋았어요", tag: "", nick: "새벽길" },
  { text: "주말엔 사람이 많아요", tag: "사람이 많아요", nick: "봄나들이" },
  { text: "화장실이 깨끗했어요", tag: "", nick: "느림보" },
];
export function reviews(id: string, page: number): ReviewsResp {
  const all = id === "PK-4" ? REVIEWS : [];
  const pages = Math.max(1, Math.ceil(all.length / 4));
  const p = Math.min(Math.max(1, page), pages);
  return {
    total: all.length,
    page: p,
    pages,
    items: all.slice((p - 1) * 4, p * 4).map((r, i) => ({ id: String((p - 1) * 4 + i + 1), ...r, date: "11.20" })),
  };
}

/* ---------- 톡방 ---------- */
type Room = { members: Record<string, string>; msgs: ChatMessage[]; seq: number };
const rooms: Record<string, Room> = {};
function room(id: string): Room {
  if (!rooms[id]) {
    rooms[id] = {
      members: { other1: "솔바람", other2: "꽃마중" },
      msgs: [
        { id: 1, nick: "", kind: "system", text: "솔바람 님이 들어왔어요", at: "10:20", mine: false },
        { id: 2, nick: "솔바람", kind: "text", text: "날씨가 참 좋네요", at: "10:21", mine: false },
        { id: 3, nick: "꽃마중", kind: "quick", text: "반가워요", at: "10:30", mine: false },
      ],
      seq: 3,
    };
  }
  return rooms[id];
}
function hhmm() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function state(id: string, client: string, after: number): ChatState {
  const r = room(id);
  const me = r.members[client];
  const members = Object.values(r.members);
  const tomorrow = new Date();
  tomorrow.setHours(24, 0, 0, 0);
  return {
    members,
    count: members.length,
    joined: !!me,
    expiresAt: tomorrow.toISOString(),
    messages: r.msgs.filter((m) => m.id > after).map((m) => ({ ...m, mine: !!me && m.nick === me && m.kind !== "system" })),
  };
}
export function chatGet(id: string, client: string, after: number) {
  return state(id, client, after);
}
export function chatJoin(id: string, client: string, nick: string) {
  const r = room(id);
  if (!r.members[client]) {
    let n = nick;
    let k = 2;
    while (Object.values(r.members).includes(n)) n = `${nick}${k++}`;
    r.members[client] = n;
    r.msgs.push({ id: ++r.seq, nick: "", kind: "system", text: `${n} 님이 들어왔어요`, at: hhmm(), mine: false });
  }
  return { ...state(id, client, 0), nick: r.members[client] };
}
export function chatSend(id: string, client: string, text: string): ChatMessage {
  const r = room(id);
  const nick = r.members[client];
  if (!nick) throw new ApiError(403, "톡방에 먼저 들어와 주세요");
  if (/https?:\/\/|www\./.test(text)) throw new ApiError(400, "링크는 보낼 수 없어요");
  const quick = ["반가워요", "고마워요", "좋아요"].includes(text);
  const msg: ChatMessage = { id: ++r.seq, nick, kind: quick ? "quick" : "text", text: text.replace(/01[0-9][- ]?\d{3,4}[- ]?\d{4}/g, "(전화번호는 가렸어요)"), at: hhmm(), mine: true };
  r.msgs.push(msg);
  return msg;
}
export function chatLeave(id: string, client: string) {
  const r = room(id);
  const nick = r.members[client];
  if (nick) {
    delete r.members[client];
    r.msgs.push({ id: ++r.seq, nick: "", kind: "system", text: `${nick} 님이 나갔어요`, at: hhmm(), mine: false });
  }
  return { ok: true };
}

/* ---------- 구 · 동 ---------- */
export const districts = () => GUS;
export const districtDongs = (gu: string) => dongsOf(gu).map((d) => ({ id: d.id, name: d.name }));

/* ---------- 로그인 (기기 sessionStorage 로 흉내) ---------- */
type MockUser = Extract<Me, { loggedIn: true }>;
function getUser(): MockUser | null {
  try {
    return JSON.parse(sessionStorage.getItem("aigo.mock.user") || "null");
  } catch {
    return null;
  }
}
function setUser(u: MockUser | null) {
  try {
    if (u) sessionStorage.setItem("aigo.mock.user", JSON.stringify(u));
    else sessionStorage.removeItem("aigo.mock.user");
  } catch {
    /* */
  }
}
function newUser(provider: "kakao" | "email", extra: Partial<MockUser> = {}): MockUser {
  return {
    loggedIn: true,
    id: "mock-0001",
    provider,
    email: provider === "email" ? "damgo@aigo.kr" : "",
    name: "",
    nickname: "",
    age: "",
    homeDong1: null,
    homeDong2: null,
    joinedAt: new Date().toISOString().slice(0, 10),
    ...extra,
  };
}
export function me(): Me {
  const u = getUser();
  if (u) return u;
  let pending = false;
  try {
    pending = sessionStorage.getItem("aigo.mock.signup") === "1";
  } catch {
    /* */
  }
  return { loggedIn: false, signupPending: pending, restorePending: false };
}
export function signup(homeDong1: string | null) {
  setUser(newUser("kakao", { homeDong1 }));
  try {
    sessionStorage.removeItem("aigo.mock.signup");
  } catch {
    /* */
  }
}
export function logout() {
  setUser(null);
}
/** 가짜 응답: 형식만 보고, 몇 가지 예시 낱말은 욕설로 막아요 */
export function nicknameCheck(nickname: string) {
  const fmt = nickProblem(nickname);
  if (fmt) return { ok: false, reason: "format", message: fmt };
  if (/씨발|시발|병신|미친놈/.test(nickname)) return { ok: false, reason: "욕설", message: "욕설이나 비방이 감지되어 사용할 수 없는 닉네임이에요" };
  return { ok: true, reason: null, message: null };
}

export function patchProfile(p: Partial<MockUser>): Me {
  const u = getUser();
  if (!u) throw new ApiError(401, "로그인해 주세요");
  const next = { ...u, ...p };
  setUser(next);
  return next;
}
export function restoreInfo() {
  return { pending: true, id: "mock-0001", provider: "kakao" as const, nickname: "담고", deletedAt: "2026-11-20", purgeAfter: "2027-02-18" };
}
export function restoreChoose(choice: "restore" | "fresh") {
  if (choice === "restore") setUser(newUser("kakao", { nickname: "담고" }));
  return { restored: choice === "restore", id: "mock-0001", provider: "kakao" as const };
}
export function emailFinish(p: { name: string; nickname: string; age: string; homeDong1: string | null }) {
  setUser(newUser("email", p));
}
export function emailLogin(email: string) {
  setUser(newUser("email", { email, nickname: "담고" }));
}

export function ranking(): RankingResp {
  const top = [
    ["봄나들이", 1820], ["햇살마중", 1460], ["솔바람", 1190], ["도란도란", 940], ["꽃마중", 720],
  ].map(([n, s]) => ({ nickname: n as string, steps: s as number, at: new Date().toISOString(), mine: false }));
  return { top, me: null, total: top.length };
}

/** 화면 흐름 상태 모양 (11_FRONTEND_SPEC 2 · 3절) */
import type { Candidate, Conditions, HeardItem, Me, Origin, Slot, Social } from "./types";
import type { NearDong } from "./geo";
import { computeRange } from "./range";

export type Step =
  | { k: "start" }
  | { k: "origin" }
  | { k: "nearby"; list: NearDong[]; widened: boolean }
  | { k: "gu" }
  | { k: "dong"; gu: string }
  | { k: "open" }
  | { k: "body"; edit?: boolean }
  | { k: "time"; edit?: boolean }
  | { k: "flex"; i: number; edit?: boolean }
  | { k: "confirm" }
  | { k: "result" }
  | { k: "guestbook" }
  | { k: "route" }
  | { k: "arrive" }
  | { k: "chatjoin" }
  | { k: "chat" }
  | { k: "notFound"; why: "offline" | "timeout" | "none" }
  | { k: "login" }
  | { k: "kwait" }
  | { k: "agree" }
  | { k: "addr" }
  | { k: "restore" }
  | { k: "elogin" }
  | { k: "signup"; i: number }
  | { k: "welcome" }
  | { k: "my" }
  | { k: "myedit"; field: "name" | "nickname" | "age" | "home1" }
  | { k: "mine" }
  | { k: "upload"; key: string }
  | { k: "cut"; key: string }
  | { k: "stamped"; key: string }
  | { k: "review"; key: string; edit?: boolean }
  | { k: "sdetail"; key: string }
  | { k: "badges" }
  | { k: "game" }
  | { k: "rank" }
  | { k: "theme" }
  | { k: "blocked" };

export type StepKey = Step["k"];

export type Q = {
  question: string;
  choices: string[];
  slot: Slot;
  src: "ai" | "basic" | "open";
  answered: boolean;
  a: string | null;
  /** 잘 모르겠어요 허용 */
  dk: boolean;
};

export type User = Extract<Me, { loggedIn: true }>;

export type FlowState = {
  stack: Step[];
  busy: string | null;
  note: string | null;
  origin: Origin | null;
  body: string | null | undefined;
  time: string | null | undefined;
  qs: Q[];
  fallback: boolean;
  filled: string[];
  place: string | null;
  who: string | null;
  wish: string[];
  heard: HeardItem[];
  openText: string;
  cands: Candidate[];
  idx: number;
  seen: string[];
  receivedAt: number;
  closed: string[];
  social: Record<string, Social>;
  printed: Record<string, boolean>;
  tearing: boolean;
  user: User | null;
  coral: string;
  /** 질문 준비 중인 번호 (-1 = 없음) */
  preparing: number;
  qNotice: boolean;
  arrivedAt: string;
  weather: string;
};

export const initialState = (): FlowState => ({
  stack: [{ k: "start" }],
  busy: null,
  note: null,
  origin: null,
  body: undefined,
  time: undefined,
  qs: [],
  fallback: false,
  filled: [],
  place: null,
  who: null,
  wish: [],
  heard: [],
  openText: "",
  cands: [],
  idx: 0,
  seen: [],
  receivedAt: 0,
  closed: [],
  social: {},
  printed: {},
  tearing: false,
  user: null,
  coral: "#FF5A4F",
  preparing: -1,
  qNotice: false,
  arrivedAt: "",
  weather: "",
});

/** 조건 묶음 만들기 (02_ARCHITECTURE 3-1) */
export function buildConditions(s: FlowState, exclude: string[] = []): Conditions {
  const ans = (slot: string) => s.qs.find((q) => q.answered && q.slot === slot)?.a ?? null;
  let walk = ans("walk");
  if (!walk && s.filled.includes("walk")) walk = "조금만요";
  const body = s.body ?? null;
  const time = s.time ?? null;
  const want = ans("want");
  return {
    mode: "text",
    origin: s.origin ?? { id: "", name: "", type: "동", lat: null, lng: null },
    body,
    time,
    range: computeRange(body, time, walk),
    basic: { want: want === "잘 모르겠어요" ? null : want, walk, inout: ans("inout") },
    ai: s.qs.filter((q) => q.answered && q.slot == null).map((q) => ({ q: q.question, choices: q.choices, a: q.a })),
    freeText: null,
    extra: { mood: null, avoid: [], place: s.place, who: s.who, wish: s.wish, expanded: [] },
    filled: s.filled,
    fallback: s.fallback,
    exclude,
  };
}

/** 화면별 담고 자세 (4절 표) */
export function poseOf(step: Step, s: FlowState): string {
  switch (step.k) {
    case "start":
      return s.user ? "home" : "s1";
    case "origin":
      return "loc";
    case "nearby":
      return "near";
    case "gu":
    case "dong":
    case "open":
      return step.k === "dong" ? "st" : "gu";
    case "body":
      return "body";
    case "time":
      return "time";
    case "flex": {
      const q = s.qs[step.i];
      if (!q) return step.i === 0 ? "ask" : "ask2";
      return q.src === "ai" ? "q1" : "fb";
    }
    case "confirm":
      return "last";
    case "result":
      return s.printed[`${s.receivedAt}-${s.idx}`] ? "s4" : "s4p";
    case "guestbook":
      return "gb1";
    case "route":
      return "route";
    case "notFound":
      return step.why === "offline" ? "off" : "none";
    case "arrive":
    case "chatjoin":
    case "chat":
    case "login":
    case "kwait":
    case "agree":
    case "addr":
    case "elogin":
    case "welcome":
      return step.k === "welcome" ? "sud" : step.k;
    case "restore":
      return "agree";
    case "signup":
      return "su1";
    case "my":
    case "myedit":
    case "mine":
    case "upload":
    case "cut":
    case "stamped":
    case "review":
    case "sdetail":
      return step.k;
    case "game":
    case "rank":
      return "my";
    case "badges":
    case "theme":
    case "blocked":
      return "mine";
  }
}

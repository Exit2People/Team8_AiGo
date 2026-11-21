/** SHARED/02_ARCHITECTURE.md 3절 · SHARED/03_API_CONTRACT.md 모양 */

export type Origin = { id: string; name: string; type: "동" | "역"; lines?: string[]; lat: number | null; lng: number | null };

export type Range = { oneWayMin: number; walk: WalkLevel; avoid: string[] };
export type WalkLevel = "제한 없음" | "많이" | "보통" | "조금만" | "가장 적게";

export type Conditions = {
  mode: "text";
  origin: Origin;
  body: string | null;
  time: string | null;
  range: Range;
  basic: { want: string | null; walk: string | null; inout: string | null };
  ai: { q: string; choices: string[]; a: string | null }[];
  freeText: null;
  extra: { mood: null; avoid: string[]; place: string | null; who: string | null; wish: string[]; expanded: string[] };
  filled: string[];
  fallback: boolean;
  exclude: string[];
};

export type Slot = "want" | "walk" | "inout" | null;

/** /questions/next · /questions/open 의 next 응답 */
export type QuestionResp = {
  total?: number;
  extra?: boolean;
  done?: boolean;
  fallback?: boolean | QuestionResp | null;
  needsAi?: boolean;
  no?: number;
  id?: string;
  question?: string;
  choices?: string[];
  slot?: Slot | "body" | "time";
  source?: string;
  input?: string;
};

export type HeardItem = { key: string; value: string; label: string };

export type OpenResp = {
  conditions: Conditions;
  filled: string[];
  heard: { title: string; text: string; items: HeardItem[] };
  next?: QuestionResp;
};

export type Leg = {
  kind: "탑승" | "환승" | "하차" | string;
  station?: string;
  line?: string;
  mode?: string;
  getOff?: string;
  stops?: number;
  tip?: string;
  exit?: string | null;
  walkMin?: number;
  direction?: string;
  fastCar?: string;
};

export type Candidate = {
  place: { id: string; name: string; kind: string; gu: string; lat: number; lng: number; photo?: string | null; source?: string };
  reason: string;
  open: { today: string; lastEntry?: string | null } | null;
  route: {
    totalMin: number;
    arriveAt: string;
    transfers: number;
    startWalkMin?: number;
    legs: Leg[];
    source?: string;
    estimated?: boolean;
  } | null;
  info?: Record<string, unknown> | null;
  event?: Record<string, unknown> | null;
};

export type RecommendResp = {
  candidates: Candidate[];
  notFound: boolean;
  why?: "none" | "timeout" | string;
  by?: string;
  weather?: { weather: string; temperature: number | null } | null;
  dataAsOf?: string;
  expanded?: { from: string[]; words: string[]; places: string[]; found: number } | null;
  /** 범위 안에 0곳이라 편도 상한을 넓혀 찾았을 때만 true */
  relaxed?: boolean;
  destinationNote?: string;
};

export type Social = { expectedToday: number; reviewCount: number; topTags: [string, number][] };

export type Review = { id: string; text: string; tag: string; nick: string; date: string };
export type ReviewsResp = { total: number; page: number; pages: number; items: Review[] };

export type ChatMessage = { id: number; nick: string; kind: "system" | "text" | "quick"; text: string; at: string; mine: boolean };
export type ChatState = { members: string[]; count: number; joined: boolean; expiresAt: string; messages: ChatMessage[]; nick?: string };

export type Me =
  | { loggedIn: false; signupPending?: boolean; restorePending?: boolean }
  | {
      loggedIn: true;
      id: string;
      provider: "kakao" | "email";
      email: string;
      name: string;
      nickname: string;
      age: string;
      homeDong1: string | null;
      homeDong2: string | null;
      joinedAt: string;
    };

export type RankEntry = { nickname: string; steps: number; at: string; mine: boolean };
export type RankingResp = { top: RankEntry[]; me: { rank: number; entry: RankEntry } | null; total: number };

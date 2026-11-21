/**
 * 서버 호출 (SHARED/03_API_CONTRACT.md).
 * - 로그인 · 게임 랭킹: 화면 주소의 `/api/...` (쿠키, next.config rewrite)
 * - 나머지: NEXT_PUBLIC_API_BASE
 *
 * 가짜 응답 스위치: NEXT_PUBLIC_MOCK=1 이거나 주소에 ?mock=1 (이 탭에서만 기억, ?mock=0 으로 끔).
 * 둘 다 없으면 진짜 서버를 불러요.
 */
import * as mock from "./mock";
import { ApiError } from "./errors";
import type {
  ChatMessage,
  ChatState,
  Conditions,
  Me,
  OpenResp,
  QuestionResp,
  RankingResp,
  RecommendResp,
  ReviewsResp,
  Social,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, "");

let mockOn: boolean | null = null;
export function isMock(): boolean {
  if (mockOn != null) return mockOn;
  let on = process.env.NEXT_PUBLIC_MOCK === "1";
  if (typeof window !== "undefined") {
    try {
      const q = new URLSearchParams(location.search).get("mock");
      if (q === "1") sessionStorage.setItem("aigo.mock", "1");
      if (q === "0") sessionStorage.removeItem("aigo.mock");
      if (sessionStorage.getItem("aigo.mock") === "1") on = true;
      if (q === "0") on = false;
    } catch {
      /* */
    }
    mockOn = on;
  }
  return on;
}

export { ApiError };

/** 화면에 보여 줄 오류 문구: 서버가 준 문자열 detail, 없으면 기본 문구 */
export function errText(e: unknown, dflt = "잠시 뒤에 다시 해 주세요"): string {
  if (e instanceof ApiError && typeof e.detail === "string" && e.detail) return e.detail;
  return dflt;
}

type Opt = { method?: string; body?: unknown; signal?: AbortSignal; same?: boolean };

async function call<T>(path: string, { method = "GET", body, signal, same }: Opt = {}): Promise<T> {
  const url = same ? `/api${path}` : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method,
    signal,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: same ? "same-origin" : "omit",
    cache: "no-store",
  });
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) throw new ApiError(res.status, (data as { detail?: unknown } | null)?.detail ?? null);
  return data as T;
}

function m<T>(fn: () => T | Promise<T>, signal?: AbortSignal, ms = 450): Promise<T> {
  return mock.delay(ms, signal).then(fn);
}

const enc = encodeURIComponent;

/* ---------- 질문 ---------- */
export function questionsOpen(conditions: Conditions, text: string, signal?: AbortSignal) {
  if (isMock()) return m(() => mock.open(conditions, text), signal, 900);
  return call<OpenResp>("/questions/open", { method: "POST", body: { conditions, text }, signal });
}

export function questionsNext(conditions: Conditions, signal?: AbortSignal) {
  if (isMock()) return m(() => mock.next(conditions), signal, mock.slowQuestion() ? 9000 : 700);
  return call<QuestionResp>("/questions/next", { method: "POST", body: conditions, signal });
}

/* ---------- 추천 · 장소 ---------- */
export function recommend(conditions: Conditions, visited: string[], signal?: AbortSignal) {
  if (isMock()) return m(() => mock.recommend(conditions), signal, 1800);
  return call<RecommendResp>("/recommend", { method: "POST", body: { conditions, visited }, signal });
}

export function placeOpen(id: string) {
  if (isMock()) return m(() => ({ open: true, today: "항상 열림", lastEntry: null }));
  return call<{ open: boolean | null; today: string; lastEntry: string | null }>(`/places/${enc(id)}/open`);
}

export function social(id: string) {
  if (isMock()) return m(() => mock.social(id), undefined, 300);
  return call<Social>(`/places/${enc(id)}/social`);
}

export function expect(id: string, client: string) {
  if (isMock()) return m(() => mock.expect(id, 1));
  return call<{ expectedToday: number }>(`/places/${enc(id)}/expect`, { method: "POST", body: { client } });
}

export function expectCancel(id: string, client: string) {
  if (isMock()) return m(() => mock.expect(id, -1));
  return call<{ expectedToday: number }>(`/places/${enc(id)}/expect/cancel`, { method: "POST", body: { client } });
}

export function reviews(id: string, page: number) {
  if (isMock()) return m(() => mock.reviews(id, page), undefined, 350);
  return call<ReviewsResp>(`/places/${enc(id)}/reviews?page=${page}`);
}

/* ---------- 톡방 ---------- */
export function chatGet(id: string, client: string, after: number, signal?: AbortSignal) {
  if (isMock()) return m(() => mock.chatGet(id, client, after), signal, 200);
  return call<ChatState>(`/chat/${enc(id)}?client=${enc(client)}&after=${after}`, { signal });
}
export function chatJoin(id: string, client: string, nick: string) {
  if (isMock()) return m(() => mock.chatJoin(id, client, nick));
  return call<ChatState & { nick: string }>(`/chat/${enc(id)}/join`, { method: "POST", body: { client, nick } });
}
export function chatSend(id: string, client: string, text: string) {
  if (isMock()) return m(() => mock.chatSend(id, client, text), undefined, 250);
  return call<ChatMessage>(`/chat/${enc(id)}/messages`, { method: "POST", body: { client, text } });
}
export function chatLeave(id: string, client: string) {
  if (isMock()) return m(() => mock.chatLeave(id, client));
  return call<{ ok: boolean }>(`/chat/${enc(id)}/leave`, { method: "POST", body: { client } });
}
export function chatReport(id: string, client: string, target: string) {
  if (isMock()) return m(() => ({ ok: true }));
  return call<{ ok: boolean }>(`/chat/${enc(id)}/report`, { method: "POST", body: { client, target } });
}

/* ---------- 구 · 동 (사는 곳 고르기) ---------- */
export function districts() {
  if (isMock()) return m(() => mock.districts(), undefined, 200);
  return call<string[]>("/districts");
}
export function districtDongs(gu: string) {
  if (isMock()) return m(() => mock.districtDongs(gu), undefined, 200);
  return call<{ id: string; name: string }[]>(`/districts/${enc(gu)}/dongs`);
}

/* ---------- 로그인 (화면 주소 /api/auth/*) ---------- */
export const KAKAO_START = "/api/auth/kakao/start";

export function me() {
  if (isMock()) return m(() => mock.me(), undefined, 200);
  return call<Me>("/auth/me", { same: true });
}
export function signup(homeDong1: string | null) {
  if (isMock()) return m(() => mock.signup(homeDong1));
  return call<void>("/auth/signup", { method: "POST", body: { agree: true, homeDong1, homeDong2: null }, same: true });
}
export function logout() {
  if (isMock()) return m(() => mock.logout());
  return call<void>("/auth/logout", { method: "POST", same: true });
}
export function deleteAccount() {
  if (isMock()) return m(() => mock.logout());
  return call<void>("/auth/account", { method: "DELETE", same: true });
}
/** 닉네임을 저장하기 전에 서버가 미리 확인해요. 안 되면 message에 이유 문장이 와요 */
export function nicknameCheck(nickname: string) {
  if (isMock()) return m(() => mock.nicknameCheck(nickname));
  return call<{ ok: boolean; reason: string | null; message: string | null }>("/auth/nickname/check", { method: "POST", body: { nickname }, same: true });
}
export function patchProfile(p: Partial<{ homeDong1: string; homeDong2: string; name: string; nickname: string; age: string }>) {
  if (isMock()) return m(() => mock.patchProfile(p));
  return call<Me>("/auth/profile", { method: "PATCH", body: p, same: true });
}
export function restoreInfo() {
  if (isMock()) return m(() => mock.restoreInfo());
  return call<{ pending: boolean; id: string; provider: "kakao" | "email"; nickname: string; deletedAt: string; purgeAfter: string }>(
    "/auth/restore",
    { same: true },
  );
}
export function restoreChoose(choice: "restore" | "fresh") {
  if (isMock()) return m(() => mock.restoreChoose(choice));
  return call<{ restored: boolean; id: string; provider: "kakao" | "email" }>("/auth/restore", {
    method: "POST",
    body: { choice },
    same: true,
  });
}
export function emailStart(email: string, password: string) {
  if (isMock()) return m(() => undefined);
  return call<void>("/auth/email/start", { method: "POST", body: { email, password }, same: true });
}
export function emailVerify(code: string) {
  if (isMock()) return m(() => ({ email: "damgo@aigo.kr", restorable: false }));
  return call<{ email: string; restorable: boolean }>("/auth/email/verify", { method: "POST", body: { code }, same: true });
}
export function emailFinish(p: { name: string; nickname: string; age: string; homeDong1: string | null }) {
  if (isMock()) return m(() => mock.emailFinish(p));
  return call<void>("/auth/email/finish", { method: "POST", body: { ...p, homeDong2: null }, same: true });
}
export function emailLogin(email: string, password: string) {
  if (isMock()) return m(() => mock.emailLogin(email));
  return call<void>("/auth/email/login", { method: "POST", body: { email, password }, same: true });
}

/* ---------- 게임 랭킹 (화면 주소 /api/game/*) ---------- */
export function gameScore(steps: number) {
  if (isMock()) return m(() => ({ rank: 3, best: steps, isBest: true }));
  return call<{ rank: number; best: number; isBest: boolean }>("/game/scores", { method: "POST", body: { steps }, same: true });
}
export function gameRanking(limit = 10) {
  if (isMock()) return m(() => mock.ranking(), undefined, 300);
  return call<RankingResp>(`/game/ranking?limit=${limit}`, { same: true });
}

// 담고 달리기 랭킹. 화면(Game · Rank)은 아래 `ranking` 하나만 불러 써요. (TestTon lib/ranking.ts와 같은 방식)
//
//   기본: localStore — 이 기기(localStorage)에만 저장해요. 화면 확인용 예시 기록이 섞여 있어요.
//   서버: apiStore   — NEXT_PUBLIC_RANKING_SOURCE=api 일 때 /api/game/* 를 불러요(lib/api.ts, 가짜 응답 스위치도 따라가요).
//                      서버가 로그인 쿠키로 누구인지 알아서 걸음 수만 보내요.
// 랭킹은 회원만 올라가요(업적 배지와 같아요). 손님은 보기만 해요.

import * as api from "./api";
import type { RankEntry, RankingResp } from "./types";

export type { RankEntry };
export type RankBoard = RankingResp;
export type Submitted = { rank: number; best: number; isBest: boolean };
export type Player = { id: string; nickname: string };

export interface RankingStore {
  readonly source: "local" | "api";
  /** 한 판 끝난 기록을 올려요. 사람마다 최고 기록 하나만 남아요. */
  submit(player: Player, steps: number): Promise<Submitted>;
  /** 랭킹표: 위에서 limit명 + 내 순위 */
  board(player: Player | null, limit?: number): Promise<RankBoard>;
}

// ── 이 기기에만 ──

type Stored = { userId: string; nickname: string; steps: number; at: string };
const KEY = "aigo.game.ranking";
// 화면 확인용 예시 기록 (서버를 켜면 쓰지 않아요). 혼자 하면 랭킹이 비어 보여서 넣었어요
const SAMPLES: Stored[] = (
  [["봄나들이", 1820], ["햇살마중", 1460], ["솔바람", 1190], ["도란도란", 940], ["꽃마중", 720], ["느림보", 510], ["새벽길", 330], ["산들바람", 160]] as const
).map(([nickname, steps], i) => ({ userId: `sample-${i + 1}`, nickname, steps, at: "2026-11-01T00:00:00.000Z" }));

const readLocal = (): Stored[] => {
  try {
    const v = localStorage.getItem(KEY);
    const list = v ? (JSON.parse(v) as Stored[]) : [];
    return Array.isArray(list) ? list.filter((s) => s && typeof s.userId === "string") : []; // 예전 모양(userId 없음)은 건너뛰어요
  } catch {
    return [];
  }
};
const writeLocal = (v: Stored[]) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(v));
  } catch {
    /* 저장 못 해도 이번 판 화면은 이어 가요 */
  }
};

function boardOf(userId: string | null, limit: number): RankBoard {
  const sorted = [...SAMPLES, ...readLocal()].sort((a, b) => b.steps - a.steps || a.at.localeCompare(b.at));
  const view = (s: Stored): RankEntry => ({ nickname: s.nickname, steps: s.steps, at: s.at, mine: s.userId === userId });
  const i = userId ? sorted.findIndex((s) => s.userId === userId) : -1;
  return { top: sorted.slice(0, limit).map(view), me: i >= 0 ? { rank: i + 1, entry: view(sorted[i]) } : null, total: sorted.length };
}

const localStore: RankingStore = {
  source: "local",
  async submit(player, steps) {
    const all = readLocal();
    const prev = all.find((s) => s.userId === player.id);
    const isBest = !prev || steps > prev.steps;
    const next: Stored = isBest ? { userId: player.id, nickname: player.nickname, steps, at: new Date().toISOString() } : { ...prev!, nickname: player.nickname };
    writeLocal([...all.filter((s) => s.userId !== player.id), next]);
    return { rank: boardOf(player.id, 10).me?.rank ?? 0, best: next.steps, isBest };
  },
  async board(player, limit = 10) {
    return boardOf(player?.id ?? null, limit);
  },
};

// ── 서버 ──

const apiStore: RankingStore = {
  source: "api",
  submit: (_player, steps) => api.gameScore(steps),
  board: (_player, limit = 10) => api.gameRanking(limit),
};

export const ranking: RankingStore = process.env.NEXT_PUBLIC_RANKING_SOURCE === "api" ? apiStore : localStore;

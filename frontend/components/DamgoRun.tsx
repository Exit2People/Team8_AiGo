"use client";

// 담고 달리기: 내 정보에서 들어가는 작은 쉬어 가기 게임. (TestTon components/Game.tsx에서 그대로 옮겼어요)
// 담고가 나들이 길을 달리고, 큰 버튼(또는 게임 화면 · 스페이스 · 위 화살표)을 누르면 폴짝 뛰어 장애물을 넘어요.
// 하늘 · 먼 풍경 · 나무 색은 모두 테마 색(color)에서 만들어요. 내 정보에서 테마를 바꾸면 게임도 같이 바뀌어요.
// 어르신도 하기 쉽게: 버튼 하나, 느리게 시작해서 천천히 빨라지고, 부딪힘 판정은 그림보다 조금 너그러워요.

import { useCallback, useEffect, useRef, useState } from "react";
import { ranking, type Player } from "@/lib/ranking";
import { isPaused } from "@/lib/pause";

// ── 게임 세계 (393 화면 기준 좌표, 카드 안쪽 345 × 300) ──
const W = 345;
const H = 300;
const GROUND = 248; // 땅 높이(Y)
const RX = 70; // 담고가 달리는 자리(X)
const GRAV = 2600; // 내려오는 힘(px/s²)
const JUMP_V = 660; // 폴짝 힘 → 최고 약 84px(제일 높은 우체통의 두 배쯤), 공중 약 0.5초
const START_SPEED = 220; // px/s
const ACCEL = 5; // 1초마다 빨라지는 정도. 끝 없이 계속 빨라져요(위 한도 없음)
const SUB_PX = 10; // 한 번에 움직이는 거리 상한: 아주 빨라져도 장애물을 그냥 지나치지 않게 잘게 나눠 계산해요
const STEP_PX = 8; // 8px = 1걸음
const MILESTONE = 500; // 500걸음마다 칭찬
const BEST_KEY = "aigo.game.best"; // 손님은 이 기기에 하나, 회원은 회원 번호를 붙여 사람마다 따로 둬요
const bestKey = (uid?: string | null) => (uid ? `${BEST_KEY}.${uid}` : BEST_KEY);

export function loadBest(uid?: string | null): number {
  try { return Number(localStorage.getItem(bestKey(uid))) || 0; } catch { return 0; }
}
function saveBest(n: number, uid?: string | null) {
  try { localStorage.setItem(bestKey(uid), String(n)); } catch { /* 저장하지 못해도 이번 판 기록은 보여요 */ }
}
// 계정을 지우면 그 사람의 최고 기록도 이 기기에서 지워요
export function clearBest(uid: string) {
  try { localStorage.removeItem(bestKey(uid)); } catch { /* */ }
}
export const fmtSteps = (n: number) => n.toLocaleString("ko-KR");

type Kind = "pot" | "post" | "bench" | "bird";
type Ob = { kind: Kind; x: number; w: number; h: number; lift: number };
const SIZE: Record<Kind, [number, number]> = { pot: [24, 34], post: [28, 46], bench: [54, 26], bird: [32, 20] };
type Phase = "ready" | "run" | "pause" | "over";

type World = {
  y: number; vy: number; air: boolean; queued: number; // 담고: 땅에서 높이 · 속도 · 공중 · 미리 누른 때
  speed: number; dist: number; t: number; obs: Ob[]; gap: number;
  flash: number; flashText: string; crashed: boolean;
};
const fresh = (): World => ({ y: 0, vy: 0, air: false, queued: -9, speed: START_SPEED, dist: 0, t: 0, obs: [], gap: 260, flash: 0, flashText: "", crashed: false });

// ── 색: 테마 색 하나로 하늘 · 풍경을 만들어요 ──
function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", "").slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a: string, b: string, t: number) {
  const A = rgb(a), B = rgb(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(", ")})`;
}
type Palette = { skyTop: string; skyLow: string; far: string; mark: string; near: string; deep: string; tag: string };
const palette = (c: string): Palette => ({
  skyTop: c,
  skyLow: mix(c, "#ffffff", 0.45),
  far: mix(c, "#ffffff", 0.24), // 먼 빌딩
  mark: mix(c, "#000000", 0.05), // 서울 랜드마크
  near: mix(c, "#000000", 0.14), // 가까운 나무
  deep: mix(c, "#000000", 0.28),
  tag: mix(c, "#000000", 0.45), // 랜드마크 이름 글자
});

const INK = "#111111";
const PAPER = "#fffefb";
const TILE = "#ede9e2";
const TAIL = "#dedede";
const AMBER = "#f2a33a";
const rand = (a: number, b: number) => a + Math.random() * (b - a);

// 담고 머리 그림 (components/Damgo.tsx와 같은 원본 SVG 경로)
const HEAD_D = "M22 112 C18 64 52 36 94 36 C138 36 170 62 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z";
const FACE_D = "M22 112 C24 94 40 82 58 80 C74 78 84 88 94 84 C106 78 122 76 138 80 C156 86 168 96 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z";

// ── 그리기 ──
function rr(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number | number[]) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

function drawSky(ctx: CanvasRenderingContext2D, p: Palette, w: World) {
  const g = ctx.createLinearGradient(0, 0, 0, GROUND);
  g.addColorStop(0, p.skyTop);
  g.addColorStop(1, p.skyLow);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, GROUND);

  // 해: 은은한 흰 빛
  ctx.fillStyle = "rgba(255, 255, 255, 0.22)";
  ctx.beginPath(); ctx.arc(286, 58, 34, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
  ctx.beginPath(); ctx.arc(286, 58, 20, 0, Math.PI * 2); ctx.fill();

  // 구름 (아주 느리게)
  const co = (w.dist * 0.06 + w.t * 5) % 420;
  ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
  for (const [cx, cy, s] of [[60, 70, 1], [230, 44, 0.8], [380, 96, 0.9]] as const) {
    let x = cx - co;
    if (x < -60) x += 420;
    cloud(ctx, x, cy, s);
  }

  // 먼 풍경: 빌딩 (반복 폭 360)
  const fo = (w.dist * 0.15) % 360;
  ctx.fillStyle = p.far;
  for (let k = 0; k < 2; k++) skyline(ctx, k * 360 - fo);

  // 서울 랜드마크: 멀리 갈수록 차례로 지나가요 (광화문 → 경복궁 → 남산서울타워 → 63빌딩 → 잠실종합운동장 → 롯데월드타워 → 다시 광화문)
  const far = w.dist * LM_PARALLAX;
  const first = Math.floor((far - LM_START - 160) / LM_GAP);
  const last = Math.floor((far - LM_START + W + 160) / LM_GAP);
  for (let j = Math.max(0, first); j <= last; j++) {
    const x = LM_START + j * LM_GAP - far;
    if (x < -160 || x > W + 160) continue;
    const lm = LANDMARKS[j % LANDMARKS.length];
    ctx.fillStyle = p.mark;
    lm.draw(ctx, x, p);
    nameTag(ctx, x, GROUND - lm.h - 16, lm.name, p);
  }

  // 가까운 나무 (반복 폭 240)
  const no = (w.dist * 0.42) % 240;
  for (let k = 0; k < 3; k++) trees(ctx, k * 240 - no, p);
}

function cloud(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
  ctx.beginPath();
  ctx.arc(x, y, 12 * s, 0, Math.PI * 2);
  ctx.arc(x + 14 * s, y - 7 * s, 15 * s, 0, Math.PI * 2);
  ctx.arc(x + 30 * s, y, 11 * s, 0, Math.PI * 2);
  ctx.fill();
  rr(ctx, x - 6 * s, y, 44 * s, 11 * s, 6 * s);
  ctx.fill();
}

function skyline(ctx: CanvasRenderingContext2D, ox: number) {
  for (const [x, bw, bh] of [[8, 26, 54], [38, 20, 78], [62, 30, 42], [98, 22, 62], [126, 16, 36], [176, 24, 48], [214, 18, 66], [258, 30, 40], [300, 28, 50], [332, 22, 70]] as const) {
    rr(ctx, ox + x, GROUND - bh, bw, bh + 2, 3); ctx.fill();
  }
}

// ── 서울 랜드마크 (실루엣, x = 가운데, 바닥 = GROUND) ──
const LM_PARALLAX = 0.15; // 먼 풍경과 같은 빠르기
const LM_START = 290; // 첫 랜드마크(광화문) 자리: 처음부터 오른쪽에 보여요
const LM_GAP = 400; // 랜드마크 사이 → 약 330걸음마다 하나

// 한옥 기와지붕: 처마 끝이 살짝 들려요
function roof(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number) {
  ctx.beginPath();
  ctx.moveTo(x - w, y - 7);
  ctx.quadraticCurveTo(x - w * 0.86, y + 1, x - w * 0.66, y);
  ctx.lineTo(x + w * 0.66, y);
  ctx.quadraticCurveTo(x + w * 0.86, y + 1, x + w, y - 7);
  ctx.quadraticCurveTo(x + w * 0.74, y - h * 0.55, x + w * 0.56, y - h);
  ctx.lineTo(x - w * 0.56, y - h);
  ctx.quadraticCurveTo(x - w * 0.74, y - h * 0.55, x - w, y - 7);
  ctx.fill();
}

type Landmark = { name: string; h: number; draw: (ctx: CanvasRenderingContext2D, x: number, p: Palette) => void };
const G = GROUND;
const LANDMARKS: Landmark[] = [
  { name: "광화문", h: 96, draw: (ctx, x, p) => {
    rr(ctx, x - 62, G - 36, 124, 38, 3); ctx.fill(); // 돌 석축
    ctx.fillRect(x - 44, G - 58, 88, 22); // 아래층
    roof(ctx, x, G - 56, 64, 14);
    ctx.fillRect(x - 32, G - 82, 64, 14); // 위층
    roof(ctx, x, G - 80, 50, 16);
    ctx.fillStyle = p.skyLow; // 홍예문 세 개
    for (const dx of [-36, 0, 36]) { const ww = dx ? 14 : 18; rr(ctx, x + dx - ww / 2, G - 26, ww, 28, [ww / 2, ww / 2, 0, 0]); ctx.fill(); }
  } },
  { name: "경복궁", h: 104, draw: (ctx, x, p) => {
    ctx.fillStyle = p.far; // 뒤쪽 북악산
    ctx.beginPath(); ctx.moveTo(x - 110, G); ctx.quadraticCurveTo(x - 40, G - 70, x + 6, G - 104); ctx.quadraticCurveTo(x + 50, G - 70, x + 120, G); ctx.fill();
    ctx.fillStyle = p.mark;
    rr(ctx, x - 82, G - 10, 164, 12, 2); ctx.fill(); // 2단 월대
    rr(ctx, x - 66, G - 20, 132, 12, 2); ctx.fill();
    ctx.fillRect(x - 48, G - 42, 96, 24); // 근정전
    roof(ctx, x, G - 40, 72, 15);
    ctx.fillRect(x - 32, G - 66, 64, 12);
    roof(ctx, x, G - 64, 56, 17);
  } },
  { name: "남산서울타워", h: 152, draw: (ctx, x) => {
    ctx.beginPath(); ctx.ellipse(x, G, 118, 58, 0, Math.PI, 0); ctx.fill(); // 남산
    ctx.fillRect(x - 3.5, G - 126, 7, 74); // 기둥
    rr(ctx, x - 13, G - 124, 26, 14, 7); ctx.fill(); // 전망대
    rr(ctx, x - 9, G - 106, 18, 5, 2.5); ctx.fill();
    ctx.fillRect(x - 1.2, G - 152, 2.4, 30); // 안테나
  } },
  { name: "63빌딩", h: 122, draw: (ctx, x, p) => {
    ctx.beginPath(); ctx.moveTo(x - 20, G); ctx.lineTo(x - 20, G - 92); ctx.lineTo(x + 2, G - 122); ctx.lineTo(x + 20, G - 112); ctx.lineTo(x + 20, G); ctx.fill();
    ctx.strokeStyle = p.far; ctx.lineWidth = 1.2; // 유리 창 줄
    ctx.beginPath();
    for (let y = G - 84; y < G - 6; y += 10) { ctx.moveTo(x - 15, y); ctx.lineTo(x + 15, y); }
    ctx.stroke();
  } },
  { name: "잠실종합운동장", h: 58, draw: (ctx, x, p) => {
    ctx.beginPath(); // 백자 달항아리처럼 휜 지붕선
    ctx.moveTo(x - 86, G);
    ctx.quadraticCurveTo(x - 90, G - 40, x - 66, G - 58);
    ctx.quadraticCurveTo(x, G - 36, x + 66, G - 58);
    ctx.quadraticCurveTo(x + 90, G - 40, x + 86, G);
    ctx.fill();
    ctx.strokeStyle = p.far; ctx.lineWidth = 1.4; // 기둥 줄
    ctx.beginPath();
    for (let dx = -64; dx <= 64; dx += 16) { const top = G - 40 - Math.abs(dx) * 0.22; ctx.moveTo(x + dx, top); ctx.lineTo(x + dx, G - 4); }
    ctx.stroke();
  } },
  { name: "롯데월드타워", h: 186, draw: (ctx, x) => {
    ctx.beginPath();
    ctx.moveTo(x - 17, G);
    ctx.lineTo(x - 12, G - 118);
    ctx.quadraticCurveTo(x - 5, G - 170, x, G - 186);
    ctx.quadraticCurveTo(x + 5, G - 170, x + 12, G - 118);
    ctx.lineTo(x + 17, G);
    ctx.fill();
  } },
];

// 이름표: 흰 바탕 · 검은 글자는 튀어서, 반투명 흰 바탕에 테마 색을 진하게 한 글자로 풍경에 녹아들게
function nameTag(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, p: Palette) {
  ctx.font = '800 11px "Pretendard Variable", Pretendard, sans-serif';
  const tw = ctx.measureText(text).width + 14;
  ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
  rr(ctx, x - tw / 2, y - 9, tw, 18, 9); ctx.fill();
  ctx.fillStyle = p.tag;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + 0.5);
}

function trees(ctx: CanvasRenderingContext2D, ox: number, p: Palette) {
  for (const [x, r] of [[20, 16], [44, 12], [128, 18], [154, 13], [204, 15]] as const) {
    ctx.fillStyle = p.deep;
    ctx.fillRect(ox + x - 1.5, GROUND - r - 2, 3, r + 2);
    ctx.fillStyle = p.near;
    ctx.beginPath(); ctx.arc(ox + x, GROUND - r - 8, r, 0, Math.PI * 2); ctx.fill();
  }
}

function drawGround(ctx: CanvasRenderingContext2D, w: World) {
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, GROUND, W, H - GROUND);
  // 보도블록 두 줄
  ctx.strokeStyle = TILE;
  ctx.lineWidth = 2;
  const o = w.dist % 44;
  ctx.beginPath();
  ctx.moveTo(0, GROUND + 22); ctx.lineTo(W, GROUND + 22);
  for (let x = -o; x < W + 44; x += 44) {
    ctx.moveTo(x, GROUND + 4); ctx.lineTo(x, GROUND + 22);
    ctx.moveTo(x + 22, GROUND + 22); ctx.lineTo(x + 22, H);
  }
  ctx.stroke();
  // 길 가장자리
  ctx.fillStyle = INK;
  ctx.fillRect(0, GROUND - 1.5, W, 3);
}

function drawOb(ctx: CanvasRenderingContext2D, o: Ob, t: number) {
  const base = GROUND - o.lift;
  const x = o.x;
  if (o.kind === "pot") {
    // 화분: 검은 화분 + 흰 꽃
    ctx.fillStyle = INK;
    ctx.beginPath();
    ctx.moveTo(x + 1, base - 18); ctx.lineTo(x + 23, base - 18); ctx.lineTo(x + 20, base); ctx.lineTo(x + 4, base); ctx.closePath(); ctx.fill();
    rr(ctx, x - 1, base - 21, 26, 5, 2); ctx.fill();
    ctx.strokeStyle = INK; ctx.lineWidth = 2.4; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(x + 12, base - 21); ctx.lineTo(x + 12, base - 28);
    ctx.moveTo(x + 12, base - 24); ctx.quadraticCurveTo(x + 5, base - 26, x + 4, base - 30);
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2;
      ctx.beginPath(); ctx.arc(x + 12 + Math.cos(a) * 4, base - 30 + Math.sin(a) * 4, 3.4, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = AMBER;
    ctx.beginPath(); ctx.arc(x + 12, base - 30, 2.6, 0, Math.PI * 2); ctx.fill();
  } else if (o.kind === "post") {
    // 우체통: 검은 몸통, 흰 투입구 · 편지
    ctx.fillStyle = INK;
    rr(ctx, x, base - o.h, o.w, o.h, [14, 14, 3, 3]); ctx.fill();
    ctx.fillStyle = "#ffffff";
    rr(ctx, x + 6, base - 34, 16, 3.5, 2); ctx.fill();
    rr(ctx, x + 7, base - 25, 14, 10, 2); ctx.fill();
    ctx.strokeStyle = INK; ctx.lineWidth = 1.6; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(x + 8, base - 24); ctx.lineTo(x + 14, base - 19.5); ctx.lineTo(x + 20, base - 24); ctx.stroke();
  } else if (o.kind === "bench") {
    // 벤치: 흰 판자 + 검은 다리
    ctx.fillStyle = INK;
    ctx.fillRect(x + 6, base - 14, 4, 14);
    ctx.fillRect(x + o.w - 10, base - 14, 4, 14);
    ctx.fillRect(x + 8, base - 26, 3, 12);
    ctx.fillRect(x + o.w - 11, base - 26, 3, 12);
    ctx.lineWidth = 2;
    ctx.strokeStyle = INK;
    ctx.fillStyle = "#ffffff";
    rr(ctx, x, base - 17, o.w, 5, 2); ctx.fill(); ctx.stroke();
    rr(ctx, x + 2, base - 26, o.w - 4, 5, 2); ctx.fill(); ctx.stroke();
  } else {
    // 비둘기: 담고 쪽(왼쪽)을 보고 날아와요
    const top = base - o.h;
    const flap = Math.sin(t * 16 + x * 0.05);
    ctx.fillStyle = "#8a8580";
    ctx.beginPath(); ctx.ellipse(x + 17, top + 12, 13, 7.5, -0.08, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x + 6, top + 8, 6, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x + 28, top + 10); ctx.lineTo(x + 34, top + 7); ctx.lineTo(x + 33, top + 15); ctx.closePath(); ctx.fill();
    ctx.fillStyle = INK;
    ctx.beginPath(); ctx.moveTo(x + 0.5, top + 7); ctx.lineTo(x - 4, top + 9); ctx.lineTo(x + 0.5, top + 10.5); ctx.closePath(); ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.beginPath(); ctx.arc(x + 4.5, top + 7, 1.6, 0, Math.PI * 2); ctx.fill();
    ctx.save();
    ctx.translate(x + 17, top + 9);
    ctx.scale(1, flap);
    ctx.beginPath(); ctx.ellipse(0, -7, 8, 9, 0.25, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
}

type Paths = { head: Path2D; face: Path2D };

// 담고 전신 (머리 SVG와 같은 좌표계, 발바닥 Y = 232).
// 흰 귀 · 흰 머리에 검은 얼굴, 동글동글 검은 몸, 짧은 팔다리, 흰 끈 가방, 회색 큰 꼬리(원 두 개).
const S = 0.33; // 게임 속 크기: 키 약 75px
const FEET = 232;
const BODY = { cx: 92, cy: 176, rx: 54, ry: 48 };
const TAILS: [number, number, number][] = [[177, 92, 68], [190, 170, 46]];
const TAIL_PIVOT = [146, 204]; // 꼬리 밑동(몸 뒤 엉덩이 쪽)

function drawDamgo(ctx: CanvasRenderingContext2D, paths: Paths, w: World, running: boolean) {
  const feet = GROUND - w.y;
  const moving = running && !w.air;
  const cyc = w.t * (running ? 9 + w.speed / 40 : 0);
  const sw = moving ? Math.sin(cyc) : 0;
  const bob = moving ? Math.abs(Math.sin(cyc)) * 7 : 0;

  // 그림자
  const k = Math.max(0.3, 1 - w.y / 160);
  ctx.fillStyle = `rgba(17, 17, 17, ${0.16 * k})`;
  ctx.beginPath(); ctx.ellipse(RX - 2, GROUND + 2, 28 * k, 5 * k, 0, 0, Math.PI * 2); ctx.fill();

  // 달릴 때 발 뒤로 흙먼지가 폴폴
  if (moving) {
    for (let i = 0; i < 3; i++) {
      const f = ((w.t * 2.4 + i / 3) % 1);
      ctx.fillStyle = `rgba(222, 222, 222, ${0.9 * (1 - f)})`;
      ctx.beginPath(); ctx.arc(RX - 22 - f * 34, GROUND - 4 - f * 10, 3 + f * 5, 0, Math.PI * 2); ctx.fill();
    }
  }

  const tilt = w.crashed ? 0.2 : w.air ? (w.vy > 0 ? -0.12 : 0.05) : moving ? 0.06 : 0;
  ctx.save();
  ctx.translate(RX, feet);
  ctx.rotate(tilt);
  ctx.scale(-S, S); // 좌우를 뒤집어 꼬리가 뒤(왼쪽)로 가요. 이 안에서 앞쪽 = -X
  ctx.translate(-95, -FEET);

  // 꼬리: 몸에 붙은 밑동(TAIL_PIVOT)을 축으로 흔들어요. 끝(큰 원)은 조금 늦게 · 더 크게 따라와서 채찍처럼 휘청여요.
  // 공중에서는 오를 때 뒤로 휘날리고, 내려올 때 위로 떠올라요
  const ph = w.t * (moving ? 16 : 3.2);
  let a1: number, a2: number;
  if (w.crashed) { a1 = -0.25; a2 = -0.1; }
  else if (w.air) { const up = Math.max(-1, Math.min(1, w.vy / JUMP_V)); a1 = 0.18 * up + Math.sin(ph) * 0.05; a2 = 0.32 * up - 0.12; }
  else if (moving) { a1 = Math.sin(ph) * 0.2; a2 = Math.sin(ph - 1.1) * 0.34; }
  else { a1 = Math.sin(ph) * 0.06; a2 = Math.sin(ph - 0.8) * 0.1; }
  const puff = moving ? 1 + Math.sin(ph * 2) * 0.05 : 1;
  ctx.fillStyle = TAIL;
  ctx.save();
  ctx.translate(TAIL_PIVOT[0], TAIL_PIVOT[1] - bob * 0.6);
  ctx.rotate(a1);
  ctx.beginPath(); ctx.arc(TAILS[1][0] - TAIL_PIVOT[0], TAILS[1][1] - TAIL_PIVOT[1], TAILS[1][2], 0, Math.PI * 2); ctx.fill();
  ctx.rotate(a2);
  ctx.beginPath(); ctx.arc(TAILS[0][0] - TAIL_PIVOT[0], TAILS[0][1] - TAIL_PIVOT[1], TAILS[0][2] * puff, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  // 다리: 달릴 때는 번갈아 들고, 공중에서는 접어요
  ctx.fillStyle = INK;
  const lift1 = w.air ? 16 : Math.max(0, sw) * 16;
  const lift2 = w.air ? 8 : Math.max(0, -sw) * 16;
  rr(ctx, 62 + sw * 7, 196 - lift1, 28, 36, 14); ctx.fill();
  rr(ctx, 104 - sw * 7, 196 - lift2, 28, 36, 14); ctx.fill();

  // 윗몸(몸 · 팔 · 머리 · 가방)은 함께 들썩여요
  ctx.save();
  ctx.translate(0, -bob);
  ctx.beginPath(); ctx.ellipse(BODY.cx, BODY.cy, BODY.rx, BODY.ry, 0, 0, Math.PI * 2); ctx.fill();
  if (w.air) { // 만세
    ctx.beginPath(); ctx.ellipse(34, 166, 13, 22, 1.1, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(152, 168, 13, 22, -1.1, 0, Math.PI * 2); ctx.fill();
  } else {
    ctx.beginPath(); ctx.ellipse(40, 182, 13, 22, 0.5 + sw * 0.45, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(146, 186, 12, 20, -0.4 + sw * 0.45, 0, Math.PI * 2); ctx.fill();
  }

  // 머리
  ctx.fillStyle = "#ffffff";
  ctx.beginPath(); ctx.arc(60, 32, 22, 0, Math.PI * 2); ctx.arc(126, 28, 22, 0, Math.PI * 2); ctx.fill();
  ctx.fill(paths.head);
  ctx.fillStyle = INK;
  ctx.fill(paths.face);
  if (w.crashed) { // 아이고! 눈을 꼭 감아요 (> <)
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 9; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(58, 100); ctx.lineTo(74, 112); ctx.lineTo(58, 124);
    ctx.moveTo(122, 98); ctx.lineTo(106, 110); ctx.lineTo(122, 122);
    ctx.stroke();
  } else {
    const blink = !running && w.t % 4 < 0.14 ? 0.12 : 1;
    const lx = running ? -7 : 0; // 뒤집혀 있어서 -X가 달리는 쪽
    const ly = w.air ? (w.vy > 0 ? -4 : 3) : 0;
    ctx.fillStyle = "#ffffff";
    ctx.save(); ctx.translate(68 + lx, 113 + ly); ctx.rotate(-0.14); ctx.scale(1, blink);
    ctx.beginPath(); ctx.ellipse(0, 0, 9.5, 15, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    ctx.save(); ctx.translate(110 + lx, 110 + ly); ctx.rotate(0.1); ctx.scale(1, blink);
    ctx.beginPath(); ctx.ellipse(0, 0, 9.5, 15, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  }

  // 흰 끈 가방 (어깨에서 엉덩이로)
  const swing = sw * 3;
  ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 9; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(52, 160); ctx.lineTo(126, 206 + swing); ctx.stroke();
  ctx.fillStyle = "#ffffff";
  rr(ctx, 112, 200 + swing, 38, 30, 7); ctx.fill();
  ctx.fillStyle = INK;
  rr(ctx, 126.5, 210 + swing, 9, 9, 2); ctx.fill();
  ctx.restore();
  ctx.restore();

  // 부딪히면 말풍선
  if (w.crashed) {
    const bx = RX + 24, by = feet - 118;
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = INK; ctx.lineWidth = 2.4;
    rr(ctx, bx, by, 74, 30, 15); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(bx + 14, by + 28); ctx.lineTo(bx + 6, by + 40); ctx.lineTo(bx + 24, by + 29); ctx.fill();
    ctx.beginPath(); ctx.moveTo(bx + 14, by + 30); ctx.lineTo(bx + 6, by + 40); ctx.lineTo(bx + 24, by + 30.5); ctx.stroke();
    ctx.fillStyle = INK;
    ctx.font = '900 16px "Pretendard Variable", Pretendard, sans-serif';
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("아이고!", bx + 37, by + 15.5);
  }
}

function drawFlash(ctx: CanvasRenderingContext2D, w: World) {
  if (w.flash <= 0) return;
  const a = Math.min(1, w.flash / 0.3);
  const rise = (1.4 - w.flash) * 10;
  ctx.globalAlpha = a;
  ctx.font = '900 20px "Pretendard Variable", Pretendard, sans-serif';
  const tw = ctx.measureText(w.flashText).width + 32;
  ctx.fillStyle = INK;
  rr(ctx, (W - tw) / 2, 26 - rise, tw, 38, 19); ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(w.flashText, W / 2, 45.5 - rise);
  ctx.globalAlpha = 1;
}

// ── 게임 화면 ──

export type { Player } from "@/lib/ranking";
// 한 판 결과. rank: 'wait' 올리는 중 · 숫자 = 랭킹 순위 · 'fail' 못 올림 · 'guest' 손님(랭킹은 회원만)
type Result = { steps: number; newBest: boolean; rank: number | "wait" | "fail" | "guest" };

export default function DamgoRun({ color, player, onRanking, onOver }: {
  color: string; player: Player | null; onRanking: () => void;
  onOver?: (steps: number) => void; // 한 판이 끝날 때 (업적 배지 세기)
}) {
  const cv = useRef<HTMLCanvasElement>(null);
  const scoreEl = useRef<HTMLElement>(null);
  const world = useRef<World>(fresh());
  const phaseRef = useRef<Phase>("ready");
  const colorRef = useRef(color);
  const playerRef = useRef(player);
  const onOverRef = useRef(onOver);
  const bestRef = useRef(0);
  const crashAt = useRef(0);
  const lastKey = useRef(0);
  const [phase, setPhaseState] = useState<Phase>("ready");
  const [best, setBest] = useState(0);
  const [result, setResult] = useState<Result | null>(null);

  const setPhase = useCallback((p: Phase) => { phaseRef.current = p; setPhaseState(p); }, []);

  useEffect(() => { colorRef.current = color; }, [color]); // 테마를 바꾸면 다음 그림부터 새 색
  useEffect(() => { playerRef.current = player; }, [player]);
  useEffect(() => { onOverRef.current = onOver; }, [onOver]);
  useEffect(() => { const b = loadBest(player?.id); bestRef.current = b; setBest(b); }, [player?.id]); // 사람이 바뀌면 그 사람의 최고 기록

  const act = useCallback(() => {
    if (isPaused()) return; // 업적 축하 화면이 떠 있는 동안은 누르지 않은 것으로
    const p = phaseRef.current;
    const w = world.current;
    if (p === "ready" || p === "over") {
      if (p === "over" && performance.now() - crashAt.current < 600) return; // 부딪히자마자 잘못 눌러 다시 시작하지 않게
      world.current = fresh();
      setResult(null);
      setPhase("run");
    } else if (p === "pause") {
      setPhase("run");
    } else if (!w.air) {
      w.vy = JUMP_V; w.air = true;
    } else {
      w.queued = w.t; // 내려오기 직전에 눌러도 땅에 닿자마자 뛰어요
    }
  }, [setPhase]);

  // 그리기 · 움직이기
  useEffect(() => {
    const c = cv.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const paths: Paths = { head: new Path2D(HEAD_D), face: new Path2D(FACE_D) };
    let scale = 1;
    const fit = () => { // 화면 배율(--zoom) × 기기 화소로 또렷하게
      const app = c.closest(".app") as HTMLElement | null;
      const z = parseFloat(app ? getComputedStyle(app).getPropertyValue("--zoom") : "1") || 1;
      scale = Math.min(4, (window.devicePixelRatio || 1) * z);
      c.width = Math.round(W * scale);
      c.height = Math.round(H * scale);
    };
    fit();
    let pal = palette(colorRef.current);
    let palFor = colorRef.current;
    let shown = -1;
    let last = performance.now();
    let raf = 0;

    const crash = () => {
      const w = world.current;
      w.crashed = true;
      const steps = Math.floor(w.dist / STEP_PX);
      const newBest = steps > bestRef.current;
      if (newBest) { bestRef.current = steps; setBest(steps); saveBest(steps, playerRef.current?.id); }
      crashAt.current = performance.now();
      const me = playerRef.current;
      setResult({ steps, newBest, rank: me ? "wait" : "guest" });
      setPhase("over");
      if (me) { // 끝나자마자 랭킹에 올려요 (사람마다 최고 기록 하나)
        const done = (rank: Result["rank"]) => setResult((r) => (r && r.steps === steps ? { ...r, rank } : r));
        ranking.submit(me, steps).then((s) => done(s.rank), () => done("fail"));
      }
      try { navigator.vibrate?.(80); } catch { /* 진동이 없는 기기 */ }
      onOverRef.current?.(steps);
    };

    const spawn = () => {
      const w = world.current;
      const steps = w.dist / STEP_PX;
      const r = Math.random();
      let kind: Kind = r < 0.42 ? "pot" : r < 0.68 ? "post" : "bench";
      if (steps > 350 && Math.random() < 0.2) kind = "bird";
      const [ow, oh] = SIZE[kind];
      const lift = kind === "bird" ? rand(24, 32) : 0;
      w.obs.push({ kind, x: W + 12, w: ow, h: oh, lift });
      let width = ow;
      if (kind === "pot" && steps > 250 && Math.random() < 0.3) { // 화분 두 개 나란히
        w.obs.push({ kind, x: W + 12 + ow + 2, w: ow, h: oh, lift: 0 });
        width += ow + 2;
      }
      // 다음 장애물까지: 뛰고 내려와서 숨 돌릴 틈은 꼭 남겨요
      w.gap = width + w.speed * 0.95 + rand(0, 170 + w.speed * 0.35);
    };

    const step = (dt: number) => {
      const w = world.current;
      w.t += dt;
      w.speed += ACCEL * dt;
      const dx = w.speed * dt;
      w.dist += dx;
      if (w.air) {
        w.vy -= GRAV * dt;
        w.y += w.vy * dt;
        if (w.y <= 0) {
          w.y = 0; w.vy = 0; w.air = false;
          if (w.t - w.queued < 0.16) { w.vy = JUMP_V; w.air = true; w.queued = -9; }
        }
      }
      for (const o of w.obs) o.x -= o.kind === "bird" ? dx * 1.12 : dx;
      w.obs = w.obs.filter((o) => o.x + o.w > -16);
      w.gap -= dx;
      if (w.gap <= 0) spawn();

      const before = Math.floor((w.dist - dx) / STEP_PX / MILESTONE);
      const now = Math.floor(w.dist / STEP_PX / MILESTONE);
      if (now > before) { w.flash = 1.4; w.flashText = `${fmtSteps(now * MILESTONE)}걸음!`; }
      if (w.flash > 0) w.flash -= dt;

      // 부딪힘: 그림보다 조금 작은 상자끼리 (너그럽게)
      const L = RX - 18, R = RX + 18, B = w.y + 3, T = w.y + 66;
      for (const o of w.obs) {
        const ol = o.x + 4, or = o.x + o.w - 4, ob = o.lift + 2, ot = o.lift + o.h - 5;
        if (R > ol && L < or && T > ob && B < ot) { crash(); break; }
      }
    };

    const draw = () => {
      if (palFor !== colorRef.current) { palFor = colorRef.current; pal = palette(palFor); }
      const w = world.current;
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      drawSky(ctx, pal, w);
      drawGround(ctx, w);
      for (const o of w.obs) drawOb(ctx, o, w.t);
      drawDamgo(ctx, paths, w, phaseRef.current === "run");
      drawFlash(ctx, w);
      const steps = Math.floor(w.dist / STEP_PX);
      if (steps !== shown && scoreEl.current) { shown = steps; scoreEl.current.textContent = fmtSteps(steps); }
    };

    const frame = (now: number) => {
      const dt = Math.min(0.033, (now - last) / 1000);
      last = now;
      if (isPaused()) { raf = requestAnimationFrame(frame); return; } // 업적 축하 화면이 떠 있으면 그 자리에 멈춰요
      if (phaseRef.current === "run") {
        const n = Math.max(1, Math.ceil((world.current.speed * dt) / SUB_PX));
        for (let i = 0; i < n && phaseRef.current === "run"; i++) step(dt / n);
      }
      else if (phaseRef.current === "ready") world.current.t += dt; // 기다리는 동안 눈 깜빡 · 꼬리 살랑
      draw();
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    const onVis = () => { // 다른 앱으로 가면 잠깐 멈춰요
      if (document.hidden && phaseRef.current === "run") setPhase("pause");
      last = performance.now();
    };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("resize", fit);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("resize", fit);
    };
  }, [setPhase]);

  // 키보드: 스페이스 · 위 화살표
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== " " && e.key !== "ArrowUp") return;
      if (isPaused()) return; // 축하 화면의 버튼을 스페이스로 누를 수 있게 그대로 둬요
      e.preventDefault();
      if (e.repeat && phaseRef.current !== "run") return;
      lastKey.current = performance.now();
      act();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [act]);

  const label = phase === "run" ? "폴짝!" : phase === "pause" ? "이어 달리기" : phase === "over" ? "다시 달리기" : "출발하기";

  return (
    <div className="run">
      <div className="runHud">
        <span className="runNow" aria-hidden="true"><b ref={scoreEl}>0</b>걸음</span>
        <button className="runBest" onClick={onRanking} disabled={phase === "run"}>
          최고 <b>{fmtSteps(best)}</b>걸음<span className="runBestGo">랭킹 ›</span>
        </button>
      </div>
      <div className="runCard" onPointerDown={(e) => { if (e.button === 0) act(); }}>
        <canvas ref={cv} className="runCanvas" role="img" aria-label="담고가 나들이 길을 달리는 게임 화면" />
        {phase === "ready" ? (
          <div className="runOver">
            <b>담고와 나들이 가요</b>
            <span>큰 버튼을 누르면 출발하고,{"\n"}한 번 더 누르면 폴짝 뛰어요</span>
          </div>
        ) : phase === "pause" ? (
          <div className="runOver"><b>잠깐 쉬는 중이에요</b><span>버튼을 누르면 이어서 달려요</span></div>
        ) : phase === "over" && result ? (
          <div className="runOver pop">
            <b className="runBig">{fmtSteps(result.steps)}걸음</b>
            <span>{result.newBest ? "최고 기록이에요! 정말 잘하셨어요" : "다시 하면 더 멀리 갈 수 있어요"}</span>
            <em className="runRank">{rankLine(result.rank)}</em>
            {result.newBest ? <i className="runChip">새 기록</i> : null}
          </div>
        ) : null}
      </div>
      <button
        className={`btn dark center runBtn${phase === "run" ? " jump" : ""}`}
        onPointerDown={(e) => { if (e.button !== 0) return; e.preventDefault(); act(); }}
        onClick={(e) => { if (e.detail === 0 && performance.now() - lastKey.current > 400) act(); }}
      >{label}</button>
      {phase === "over" ? (
        <button className="btn white center runRankBtn" onClick={onRanking}>랭킹 보기<span className="arrow" aria-hidden="true">→</span></button>
      ) : (
        <p className="caption">게임 화면을 눌러도 뛰어요 · 500걸음마다 칭찬해요</p>
      )}
      <p className="srOnly" aria-live="polite">{phase === "over" && result ? `아이고! ${fmtSteps(result.steps)}걸음 걸었어요.${result.newBest ? " 최고 기록이에요." : ""} ${rankLine(result.rank)}` : ""}</p>
    </div>
  );
}

const rankLine = (r: Result["rank"]) =>
  r === "wait" ? "랭킹에 올리는 중이에요…"
  : r === "fail" ? "랭킹에 올리지 못했어요. 다음 판에 다시 올려요"
  : r === "guest" ? "로그인하면 랭킹에 이름이 올라가요"
  : `랭킹 ${r}위예요`;

// 내 정보 카드: 게임으로 들어가는 곳
export function GameCard({ best, onOpen }: { best: number; onOpen: () => void }) {
  return (
    <button className="gameCard" onClick={onOpen}>
      <svg className="gcThumb" width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
        <rect width="56" height="56" rx="16" fill="var(--coral)" />
        <g transform="translate(5.5 5) scale(0.198)">
          <DamgoBodySvg />
        </g>
      </svg>
      <span className="profileText"><b>담고 달리기</b><span>{best ? `최고 ${fmtSteps(best)}걸음 · 한 판 더 할까요?` : "쉬는 틈에 폴짝폴짝 한 판"}</span></span>
      <span className="pillWhite">시작</span>
    </button>
  );
}

// 담고 전신 (정면, 꼬리는 오른쪽). 게임 속 그림과 같은 좌표 · 모양이에요
export function DamgoBodySvg() {
  return (
    <g>
      {TAILS.map(([cx, cy, r]) => <circle key={cx} cx={cx} cy={cy} r={r} fill={TAIL} />)}
      <rect x="62" y="196" width="28" height="36" rx="14" fill={INK} />
      <rect x="104" y="196" width="28" height="36" rx="14" fill={INK} />
      <ellipse cx={BODY.cx} cy={BODY.cy} rx={BODY.rx} ry={BODY.ry} fill={INK} />
      <ellipse cx="40" cy="182" rx="13" ry="22" transform="rotate(29 40 182)" fill={INK} />
      <ellipse cx="146" cy="186" rx="12" ry="20" transform="rotate(-23 146 186)" fill={INK} />
      <circle cx="60" cy="32" r="22" fill="#fff" /><circle cx="126" cy="28" r="22" fill="#fff" />
      <path d={HEAD_D} fill="#fff" /><path d={FACE_D} fill={INK} />
      <ellipse cx="68" cy="113" rx="9.5" ry="15" transform="rotate(-8 68 113)" fill="#fff" />
      <ellipse cx="110" cy="110" rx="9.5" ry="15" transform="rotate(6 110 110)" fill="#fff" />
      <path d="M52 160 L126 206" stroke="#fff" strokeWidth="9" strokeLinecap="round" />
      <rect x="112" y="200" width="38" height="30" rx="7" fill="#fff" />
      <rect x="126.5" y="210" width="9" height="9" rx="2" fill={INK} />
    </g>
  );
}

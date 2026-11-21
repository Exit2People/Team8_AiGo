"use client";

import { useEffect, useRef, type RefObject } from "react";

/**
 * 꼬리 살랑 — 귀엽게 살랑살랑, 실제 동물처럼 불규칙하게
 * (figma-plugin 07 움직임 "꼬리 살랑": 빠르게 몇 번 → 천천히 → 쉬기)
 *
 * 꼬리는 원 두 개(뿌리 · 끝)지만 한 덩어리예요. 꼬리 뿌리(머리 쪽 끝)를 축으로
 * 두 원을 함께 좌우로 기울여요 → 두 원이 절대 떨어지지 않고, 뱀처럼 꿈틀대지 않아요.
 * 끝 원만 아주 조금 더 기울여 부드럽게 휘어 보이게 해요 (뿌리 원 둘레를 도는 거라 역시 붙어 있어요).
 *
 * 정해진 반복 대신 동작을 그때그때 골라 이어 붙여요.
 *  - 살랑: 0.5 ~ 0.7초짜리 좌우 흔들기 2 ~ 3번
 *  - 톡톡: 0.24 ~ 0.3초짜리 작은 흔들기 2 ~ 3번
 *  - 쉬기: 숨 쉬듯 아주 작게만
 *
 * mode
 *  - "idle":  가끔 살랑이고 쉬어요
 *  - "think": 고민하는 화면(찾는 중 · 질문 고르는 중 …) — 쉬지 않고 계속 살랑여요
 *  - "off":   움직임 줄이기 · 담고가 없는 화면
 *
 * 화면마다 다시 그리지 않도록 DOM의 translate 속성만 직접 바꿔요 (자세 전환용 transform과 겹치지 않아요).
 */
export type TailMode = "idle" | "think" | "off";
/** [가운데 x, 가운데 y, 지름] */
export type Circle = [number, number, number];
export type TailGeom = { base: Circle; tip: Circle; head: [number, number] };

type Seg = { t0: number; dur: number; kind: "sway" | "pat" | "rest"; amp: number; cycles: number; dir: number };

const rand = (a: number, b: number) => a + Math.random() * (b - a);

function nextSeg(t0: number, mode: TailMode, prev?: Seg): Seg {
  const think = mode === "think";
  if (prev && prev.kind !== "rest") {
    const r = think ? rand(0.08, 0.35) : Math.random() < 0.3 ? rand(0.3, 0.7) : rand(1.4, 4.2);
    return { t0, dur: r, kind: "rest", amp: 0, cycles: 0, dir: 1 };
  }
  const dir = Math.random() < 0.5 ? -1 : 1;
  if (Math.random() < (think ? 0.7 : 0.6)) {
    const cycles = 2 + Math.floor(Math.random() * 2);
    return { t0, dur: cycles * rand(0.5, 0.7), kind: "sway", amp: rand(0.7, 1), cycles, dir };
  }
  const cycles = 2 + Math.floor(Math.random() * 2);
  return { t0, dur: cycles * rand(0.24, 0.3), kind: "pat", amp: rand(0.4, 0.6), cycles, dir };
}

function segValue(s: Seg, t: number): number {
  if (s.kind === "rest") return 0;
  const u = Math.min(1, Math.max(0, (t - s.t0) / s.dur));
  // 부드럽게 들어왔다 나가는 좌우 흔들기 (갑자기 튀지 않아요)
  return s.amp * Math.sin(Math.PI * u) * Math.sin(2 * Math.PI * s.cycles * u) * s.dir;
}

function rot(x: number, y: number, deg: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
}

export function useTail(base: RefObject<HTMLDivElement | null>, tip: RefObject<HTMLDivElement | null>, mode: TailMode, geom: TailGeom) {
  const modeRef = useRef(mode);
  const geomRef = useRef(geom);
  useEffect(() => {
    modeRef.current = mode;
    geomRef.current = geom;
  }, [mode, geom]);

  useEffect(() => {
    const clear = () => {
      for (const el of [base.current, tip.current]) if (el) el.style.translate = "";
    };
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return clear;

    let raf = 0;
    let segs: Seg[] = [];
    let lastMode = modeRef.current;
    let amp = lastMode === "think" ? 1 : 0; // 고민 중엔 더 크게 (부드럽게 바뀜)
    const now = performance.now() / 1000;
    segs.push({ t0: now, dur: rand(0.3, 1.2), kind: "rest", amp: 0, cycles: 0, dir: 1 });

    const valueAt = (t: number) => {
      const s = segs.find((x) => t >= x.t0 && t < x.t0 + x.dur);
      return s ? segValue(s, t) : 0;
    };

    const frame = (ms: number) => {
      const t = ms / 1000;
      const m = modeRef.current;
      if (m === "off") {
        clear();
        raf = requestAnimationFrame(frame);
        return;
      }
      if (m !== lastMode) {
        const cur = segs[segs.length - 1];
        if (m === "think" && cur.kind === "rest") cur.dur = Math.max(0, t - cur.t0); // 고민 화면이면 바로 살랑
        lastMode = m;
      }
      while (segs[segs.length - 1].t0 + segs[segs.length - 1].dur <= t + 0.1) {
        const last = segs[segs.length - 1];
        segs.push(nextSeg(last.t0 + last.dur, m, last));
      }
      segs = segs.filter((s) => s.t0 + s.dur > t - 0.2);

      amp += ((m === "think" ? 1 : 0) - amp) * 0.05;
      // 숨 쉬듯 아주 작은 흔들림 + 동작
      const breath = 0.08 * Math.sin(t * 1.7) + 0.04 * Math.sin(t * 2.9 + 1.1);
      const v = valueAt(t) + breath;
      const vLate = valueAt(t - 0.05) + breath;
      const deg = v * (7 + 3 * amp); // 쉬는 화면 최대 7도, 고민 화면 10도

      const g = geomRef.current;
      const [bx, by, bd] = g.base;
      const [tx, ty] = g.tip;
      // 꼬리 뿌리: 뿌리 원에서 머리 쪽으로 반지름 0.8만큼
      const hx = g.head[0] - bx;
      const hy = g.head[1] - by;
      const hl = Math.hypot(hx, hy) || 1;
      const px = bx + (hx / hl) * bd * 0.4;
      const py = by + (hy / hl) * bd * 0.4;

      // 뿌리 원: 축을 중심으로 회전한 만큼 옮겨요
      const [rbx, rby] = rot(bx - px, by - py, deg);
      const nbx = px + rbx;
      const nby = py + rby;
      // 끝 원: 같은 회전 + 뿌리 원 둘레로 조금 더 (늦게 따라오는 살짝 휨)
      const [rtx, rty] = rot(tx - px, ty - py, deg);
      const [ex, ey] = rot(px + rtx - nbx, py + rty - nby, vLate * 3);
      const ntx = nbx + ex;
      const nty = nby + ey;

      if (base.current) base.current.style.translate = `${(nbx - bx).toFixed(2)}px ${(nby - by).toFixed(2)}px`;
      if (tip.current) tip.current.style.translate = `${(ntx - tx).toFixed(2)}px ${(nty - ty).toFixed(2)}px`;
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      clear();
    };
  }, [base, tip]);
}

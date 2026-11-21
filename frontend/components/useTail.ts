"use client";

import { useEffect, useRef, type RefObject } from "react";

/**
 * 꼬리 살랑 — 귀엽게 살랑살랑, 실제 동물처럼 불규칙하게
 * (figma-plugin 07 움직임 "꼬리 살랑": 빠르게 몇 번 → 천천히 → 쉬기)
 *
 * 꼬리 모양(lib/poses.ts): 작은 원 = 머리 옆에 붙은 꼬리 뿌리, 큰 원 = 뿌리에서 위 · 바깥으로 이어져 부푼 꼬리 끝.
 *  - 작은 뿌리는 머리 쪽 끝을 축으로 조금만 기울어요
 *  - 부푼 큰 원은 털뭉치라 늦게 따라오며 더 크게 살랑여요 (관성)
 *  - 빨리 흔들 땐 큰 원이 살짝 바깥으로 늘어지고, 멈추면 제자리로 돌아와요
 *
 * 꼬리는 원 두 개(뿌리 · 끝)지만 한 덩어리예요. 꼬리 뿌리(머리 쪽 끝)를 축으로
 * 두 원을 함께 좌우로 기울여요 → 두 원이 절대 떨어지지 않고, 뱀처럼 꿈틀대지 않아요.
 * 끝 원(위쪽)은 용수철로 뿌리를 늦게 따라와요(관성): 뿌리보다 더 크게 휘고, 뿌리가 멈춰도
 * 한두 번 더 출렁이다 가라앉아요. 끝 원은 뿌리 원 둘레를 도는 거라 역시 붙어 있어요.
 *
 * 정해진 반복 대신 동작을 그때그때 골라 이어 붙여요.
 *  - 살랑: 1.3 ~ 1.7초짜리 느긋한 좌우 흔들기 1.5 ~ 2.5번 (대부분)
 *  - 톡톡: 가끔, 0.55 ~ 0.65초짜리 작은 흔들기 2번
 *  - 쉬기: 숨 쉬듯 아주 작게만
 *
 * mode
 *  - "idle":  가끔 살랑이고 쉬어요
 *  - "think": 고민하는 화면(찾는 중 · 질문 고르는 중 …) — 로딩 중임을 알 수 있게 멈추지 않고 계속 살랑여요.
 *             흔들기를 끊어 이어 붙이면 커졌다 작아졌다 출렁여서, 한 번 이어진 느긋한 좌우 흔들기(한 번 약 1.5초)로
 *             흔들고 속도 · 폭만 아주 천천히 달라지게 해요. 멈춘 게 아닌 걸 알 수 있게 폭은 이 화면만 더 커요(20도)
 *  - "off":   움직임 줄이기 · 담고가 없는 화면
 *
 * 머리도 꼬리에 맞춰 움직여요: 꼬리 뿌리가 기우는 반대쪽으로 살짝 갸웃하고(몸이 꼬리를 흔드는 느낌),
 * 꼬리가 양 끝으로 갈 때마다 아주 조금 들썩여요. 큰 원(털뭉치)의 출렁임도 반 박자 늦게 조금 받아요.
 *
 * 화면마다 다시 그리지 않도록 DOM의 translate · rotate 속성만 직접 바꿔요 (자세 전환용 transform과 겹치지 않아요).
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
    const r = think ? rand(1.2, 2.2) : Math.random() < 0.2 ? rand(0.8, 1.4) : rand(2.6, 5.5);
    return { t0, dur: r, kind: "rest", amp: 0, cycles: 0, dir: 1 };
  }
  const dir = Math.random() < 0.5 ? -1 : 1;
  if (Math.random() < 0.88) {
    const cycles = [1.5, 2, 2.5][Math.floor(Math.random() * 3)];
    return { t0, dur: cycles * rand(1.3, 1.7), kind: "sway", amp: rand(0.85, 1), cycles, dir };
  }
  // 가끔 작은 톡톡 (느긋하게, 작게)
  const cycles = 2;
  return { t0, dur: cycles * rand(0.55, 0.65), kind: "pat", amp: rand(0.35, 0.5), cycles, dir };
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

export function useTail(
  base: RefObject<HTMLDivElement | null>,
  tip: RefObject<HTMLDivElement | null>,
  mode: TailMode,
  geom: TailGeom,
  head?: RefObject<HTMLDivElement | null>,
) {
  const modeRef = useRef(mode);
  const geomRef = useRef(geom);
  useEffect(() => {
    modeRef.current = mode;
    geomRef.current = geom;
  }, [mode, geom]);

  useEffect(() => {
    const headSvg = () => (head?.current?.firstElementChild as HTMLElement | SVGElement | null) ?? null;
    const clear = () => {
      for (const el of [base.current, tip.current]) if (el) el.style.translate = "";
      const h = headSvg();
      if (h) {
        h.style.translate = "";
        h.style.rotate = "";
      }
    };
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return clear;

    let raf = 0;
    let segs: Seg[] = [];
    let lastMode = modeRef.current;
    // 끝 원의 관성: 각도(도)와 각속도. 용수철(K)로 뿌리 각도 × TIP_GAIN을 따라가고, 덜 꺾인 감쇠(C)라 살짝 넘쳤다 돌아와요
    const K = 70; // 고유 진동 약 1.3Hz
    const C = 2 * 0.32 * Math.sqrt(K); // 감쇠비 0.32
    const TIP_GAIN = 1.7; // 위쪽(끝)이 아래쪽(뿌리)보다 더 크게
    let tipDeg = 0;
    let tipVel = 0;
    let open = 0; // 큰 원이 바깥으로 늘어진 정도 (0 ~ 0.05)
    let lastT = 0;
    // 고민 화면의 이어진 살랑: 위상(0~1 반복)과 섞는 정도(쉬는 화면 ↔ 고민 화면을 부드럽게 오가요)
    let phase = 0;
    let mix = lastMode === "think" ? 1 : 0;
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

      // 숨 쉬듯 아주 작은 흔들림 + 동작
      const breath = 0.04 * Math.sin(t * 1.3) + 0.02 * Math.sin(t * 2.3 + 1.1);
      // 이어진 살랑 (속도 1.35~1.65초 · 폭 0.8~1.0이 천천히 바뀌어요)
      const step = lastT ? Math.min(0.05, t - lastT) : 0;
      phase = (phase + step / (1.5 + 0.15 * Math.sin(t * 0.45))) % 1;
      const steady = (0.9 + 0.1 * Math.sin(t * 0.7 + 0.5)) * Math.sin(2 * Math.PI * phase);
      mix += ((m === "think" ? 1 : 0) - mix) * Math.min(1, step * 2.5);
      const v = (1 - mix) * valueAt(t) + mix * steady + breath;
      // 뿌리: 다른 화면 최대 12도, 로딩(고민) 화면만 20도 — 멈춘 게 아니라 일하는 중인 게 잘 보이게
      const deg = v * (12 + 8 * mix);

      // 끝 원 관성 (탭이 숨었다 돌아오면 크게 튀지 않게 한 번에 최대 0.05초씩만 적분)
      let dt = lastT ? Math.min(0.05, t - lastT) : 0;
      lastT = t;
      while (dt > 0) {
        const h = Math.min(dt, 1 / 120);
        tipVel += (K * (deg * TIP_GAIN - tipDeg) - C * tipVel) * h;
        tipDeg += tipVel * h;
        // 빨리 움직일수록 살짝 풀리고, 느려지면 천천히 다시 말려요
        const want = Math.min(0.05, Math.abs(tipVel) * 0.0008);
        open += (want - open) * Math.min(1, h * (want > open ? 6 : 2.5));
        dt -= h;
      }
      // 뿌리 원 둘레로 더 꺾이는 각도 (귀엽게 보이도록 ±28도까지)
      const bend = Math.max(-28, Math.min(28, tipDeg - deg));

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
      // 끝 원: 같은 회전 + 뿌리 원 둘레로 관성만큼 더 (늦게 따라와 더 크게 휘고, 멈춘 뒤에도 살짝 출렁여요)
      const [rtx, rty] = rot(tx - px, ty - py, deg);
      const [ex0, ey0] = rot(px + rtx - nbx, py + rty - nby, bend);
      // 풀린 만큼 뿌리 원에서 조금 더 멀어져요 (두 원은 여전히 겹쳐 붙어 있어요)
      const ex = ex0 * (1 + open);
      const ey = ey0 * (1 + open);
      const ntx = nbx + ex;
      const nty = nby + ey;

      // 머리: 뿌리 반대쪽으로 갸웃(최대 약 2.4도) + 큰 원 출렁임 조금, 꼬리가 기울수록 살짝 들썩 (머리 SVG 단위라 크기 따라 커져요)
      const h = headSvg();
      if (h) {
        const tilt = -deg * 0.16 + bend * 0.04;
        const bob = -Math.min(1, Math.abs(deg) / 15) * 1.6;
        h.style.rotate = `${tilt.toFixed(2)}deg`;
        h.style.translate = `0px ${bob.toFixed(2)}px`;
      }

      if (base.current) base.current.style.translate = `${(nbx - bx).toFixed(2)}px ${(nby - by).toFixed(2)}px`;
      if (tip.current) tip.current.style.translate = `${(ntx - tx).toFixed(2)}px ${(nty - ty).toFixed(2)}px`;
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      clear();
    };
  }, [base, tip, head]);
}

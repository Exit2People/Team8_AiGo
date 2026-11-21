"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { DamgoBack, DamgoPaws } from "./Damgo";
import { bgFor, getPose } from "@/lib/poses";
import type { Pose } from "@/lib/poses";
import { isIOS, nudgeSafari, setThemeColor, toHex, visibleColorAt } from "@/lib/bars";

const W = 393;
const H = 852;

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function over(base: string, top: [number, number, number], a: number) {
  const b = hexToRgb(base);
  const c = b.map((v, i) => Math.round(v * (1 - a) + top[i] * a));
  return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
}

/** 상단 막대 색 (11_FRONTEND_SPEC 1.4) */
function barColor(coral: string, flat: boolean, isCoralTheme: boolean) {
  if (flat) return coral;
  return isCoralTheme ? over(coral, [242, 163, 58], 0.3) : over(coral, [255, 255, 255], 0.22);
}

type Props = {
  poseKey: string;
  /** 자동 움직임 등으로 덮어쓴 자세 (없으면 poseKey) */
  pose?: Pose;
  coral: string;
  still?: boolean;
  inert?: boolean;
  blink?: boolean;
  wag?: boolean;
  /** 담고가 옮겨 가는 시간 (초) */
  move?: number;
  /** 화면이 바뀐 걸 알리는 값 (바뀌면 막대 색을 다시 읽어요) */
  scene?: string;
  overlay?: ReactNode;
  children: ReactNode;
};

export default function Stage({ poseKey, pose, coral, still, inert, overlay, children, blink, wag, move = 0.6, scene = "" }: Props) {
  const appRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);
  const botRef = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState<{ zoom: number; bleed: number; ch: number } | null>(null);
  const lastH = useRef(0);

  useLayoutEffect(() => {
    function measure() {
      const notch = topRef.current?.getBoundingClientRect().height ?? 0;
      const below = botRef.current?.getBoundingClientRect().height ?? 0;
      const cs = getComputedStyle(document.body);
      const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
      const w = document.documentElement.clientWidth - padX;
      const vv = window.visualViewport?.height ?? window.innerHeight;
      const h = Math.min(window.innerHeight, vv) - notch - below;
      if (!(w > 0) || !(h > 0)) return;
      const ae = document.activeElement;
      const typing = ae instanceof HTMLInputElement || ae instanceof HTMLTextAreaElement;
      if (typing && lastH.current && h < lastH.current) return;
      lastH.current = h;
      const zoom = Math.min(w / W, h / H);
      setFit({ zoom, bleed: Math.max(0, (w / zoom - W) / 2), ch: Math.max(H, h / zoom) });
    }
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("orientationchange", measure);
    window.visualViewport?.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("orientationchange", measure);
      window.visualViewport?.removeEventListener("resize", measure);
    };
  }, []);

  const bg = bgFor(poseKey);
  const p = pose ?? getPose(poseKey);

  const isA = coral.toUpperCase() === "#FF5A4F";
  // 처음 그릴 때 쓰는 어림값 (곧 화면에서 실제로 보이는 색을 읽어 바꿔요)
  const bar = barColor(coral, bg.warm === 0 && bg.deep === 0 && bg.coralY === 0, isA);

  /* ---------- 브라우저 막대 색 (lib/bars.ts) ----------
     위: 화면 맨 위에 실제로 보이는 색 → 안드로이드는 theme-color, 아이폰 사파리는 맨 위 고정 띠
     아래: 화면 맨 아래에 실제로 보이는 색 → 아이폰 사파리는 html · body 바탕색 */
  const [band, setBand] = useState<{ color: string; n: number } | null>(null);
  const bandRef = useRef<HTMLDivElement>(null);
  const seen = useRef({ top: "", bottom: "" });
  const readRef = useRef<() => void>(() => {});
  useEffect(() => {
    // 아이폰 · 아이패드(데스크톱 모드 포함)에만 ios 클래스 → 입력칸 확대 막기 · 막대 띠 보이기 (globals.css)
    document.documentElement.classList.toggle("ios", isIOS());
  }, []);
  useEffect(() => {
    readRef.current = () => {
      const ios = document.documentElement.classList.contains("ios");
      const inset = topRef.current?.getBoundingClientRect().height ?? 0;
      const x = window.innerWidth / 2;
      const top = toHex(visibleColorAt(x, inset + 1, bandRef.current));
      const bottom = toHex(visibleColorAt(x, window.innerHeight - 1, bandRef.current));
      let changed = false;
      if (top !== seen.current.top) {
        seen.current.top = top;
        setThemeColor(top);
        changed = true;
      }
      if (ios && bottom !== seen.current.bottom) {
        seen.current.bottom = bottom;
        document.documentElement.style.background = bottom;
        document.body.style.background = bottom;
        changed = true;
      }
      // 위 · 아래 어느 쪽이 바뀌어도 띠를 새 요소로 갈아 끼워요 (사파리는 고정 요소가 바뀔 때 막대 색을 다시 읽어요) + 1px 스크롤
      if (ios && changed) {
        setBand((b) => ({ color: top, n: (b?.n ?? 0) + 1 }));
        requestAnimationFrame(() => requestAnimationFrame(nudgeSafari));
      }
    };
  });
  // 화면이 바뀔 때 · 움직임이 끝날 때(0.15 · 0.5 · 0.95초 뒤) 다시 읽어요
  useEffect(() => {
    const ts = [150, 500, 950].map((ms) => setTimeout(() => readRef.current(), ms));
    return () => ts.forEach(clearTimeout);
  }, [scene, poseKey, coral, fit?.zoom]);
  // 안쪽이 스크롤될 때도 (잦은 스크롤은 멈춘 뒤 한 번)
  useEffect(() => {
    let t: ReturnType<typeof setTimeout> | undefined;
    const onScroll = () => {
      clearTimeout(t);
      t = setTimeout(() => readRef.current(), 150);
    };
    document.addEventListener("scroll", onScroll, true);
    return () => {
      clearTimeout(t);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, []);

  const style = fit
    ? ({
        "--zoom": fit.zoom,
        "--bleed": `${fit.bleed}px`,
        "--canvas-h": `${fit.ch}px`,
        "--coral": coral,
        "--t-move": `${move}s`,
      } as React.CSSProperties)
    : ({ "--coral": coral, "--t-move": `${move}s`, width: "100%", height: "100dvh" } as React.CSSProperties);

  return (
    <div className="viewport">
      {/* 아이폰 사파리만: 상태 표시줄 자리를 이 띠 색으로 칠해요. 화면 맨 위와 같은 색이라 보이지 않아요.
          사파리는 6px 이상 · 숨기지 않은 고정 요소만 알아봐요. 색이 바뀌면 key로 새 요소를 끼워 다시 읽게 해요 */}
      <div
        key={band?.n ?? 0}
        ref={bandRef}
        className="bar-band"
        aria-hidden="true"
        style={{ background: band?.color ?? bar }}
      />
      <div ref={topRef} style={{ position: "fixed", top: 0, height: "env(safe-area-inset-top)", width: 1, visibility: "hidden" }} />
      <div ref={botRef} style={{ position: "fixed", bottom: 0, height: "env(safe-area-inset-bottom)", width: 1, visibility: "hidden" }} />
      <div ref={appRef} className={`app${still ? " still" : ""}`} style={style}>
        <div className="canvas">
          <div className="bg bg-coral" style={{ transform: `translateY(${bg.coralY}px)` }} />
          <div className="bg bg-deep" style={{ opacity: bg.deep }} />
          <div className="bg bg-warm" style={{ opacity: bg.warm }} />
          <DamgoBack pose={p} blink={blink} wag={wag} still={still} />
          <div className="content-wrap" inert={inert || undefined}>
            {children}
          </div>
          <DamgoPaws pose={p} />
          {overlay}
        </div>
      </div>
    </div>
  );
}

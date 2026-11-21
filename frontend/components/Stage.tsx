"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { DamgoBack, DamgoPaws } from "./Damgo";
import { bgFor, getPose } from "@/lib/poses";
import type { Pose } from "@/lib/poses";

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

function setThemeColor(color: string) {
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
  const m = document.createElement("meta");
  m.name = "theme-color";
  m.content = color;
  document.head.appendChild(m);
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
  overlay?: ReactNode;
  children: ReactNode;
  /** 배지 축하 화면이 떠 있는 동안: 뒤 화면의 CSS 애니메이션을 그 자리에 멈춰요(globals.css .app.paused) */
  paused?: boolean;
};

export default function Stage({ poseKey, pose, coral, still, inert, paused, overlay, children, blink, wag, move = 0.6 }: Props) {
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

  // 배지 축하 중: CSS 애니메이션은 .app.paused로 멈추지만, 자세가 바뀔 때의 전환(transition)은 CSS로 멈출 수 없어서
  // 뒤 화면에서 돌고 있는 애니메이션 · 전환을 모두 일시정지했다가, 축하 화면을 닫으면 그 자리에서 이어서 재생해요
  useEffect(() => {
    const app = appRef.current;
    if (!paused || !app || typeof app.getAnimations !== "function") return;
    const held = app.getAnimations({ subtree: true }).filter((a) => {
      const t = (a.effect as KeyframeEffect | null)?.target as Element | null;
      return a.playState === "running" && !!t && !t.closest(".celebrateDim");
    });
    held.forEach((a) => a.pause());
    return () => {
      held.forEach((a) => {
        try {
          if (a.playState === "paused") a.play();
        } catch {
          /* 그 사이 끝났거나 사라진 애니메이션 */
        }
      });
    };
  }, [paused]);

  const bg = bgFor(poseKey);
  const p = pose ?? getPose(poseKey);

  const isA = coral.toUpperCase() === "#FF5A4F";
  const bar = barColor(coral, bg.warm === 0 && bg.deep === 0 && bg.coralY === 0, isA);
  useEffect(() => {
    setThemeColor(bar);
  }, [bar]);
  useEffect(() => {
    // 아이폰 · 아이패드(데스크톱 모드 포함)에만 ios 클래스 → 입력칸 확대 막기 (globals.css)
    const ua = navigator.userAgent;
    const ios = !/Android/.test(ua) && (/iPhone|iPod|iPad/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
    document.documentElement.classList.toggle("ios", ios);
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
      {/* 아이폰 사파리가 상태 표시줄을 이 띠 색으로 칠해요 (1.4) */}
      <div aria-hidden="true" style={{ position: "fixed", left: 0, right: 0, top: 0, height: "max(env(safe-area-inset-top), 6px)", background: bar, zIndex: 100, transition: "background .3s" }} />
      <div ref={topRef} style={{ position: "fixed", top: 0, height: "env(safe-area-inset-top)", width: 1, visibility: "hidden" }} />
      <div ref={botRef} style={{ position: "fixed", bottom: 0, height: "env(safe-area-inset-bottom)", width: 1, visibility: "hidden" }} />
      <div ref={appRef} className={`app${still ? " still" : ""}${paused ? " paused" : ""}`} style={style}>
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

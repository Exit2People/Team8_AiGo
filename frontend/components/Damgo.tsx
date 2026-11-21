"use client";

import type { CSSProperties } from "react";
import type { Pose } from "@/lib/poses";

/** 담고 머리 원본 (design_handoff/1-svg/damgo_head.svg, 190×170, 중심 95·97) */
export function DamgoHeadSvg({ look = [0, 0] }: { look?: [number, number] }) {
  return (
    <svg width="190" height="170" viewBox="0 0 190 170" aria-hidden="true">
      <circle cx="60" cy="32" r="22" fill="#FFFFFF" />
      <circle cx="126" cy="28" r="22" fill="#FFFFFF" />
      <path
        d="M22 112 C18 64 52 36 94 36 C138 36 170 62 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z"
        fill="#FFFFFF"
      />
      <path
        d="M22 112 C24 94 40 82 58 80 C74 78 84 88 94 84 C106 78 122 76 138 80 C156 86 168 96 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z"
        fill="#111111"
      />
      <g className="damgo-eyes" style={{ transform: `translate(${look[0]}px, ${look[1]}px)` }}>
        <g transform="rotate(-8 68 113)">
          <ellipse className="damgo-eye" cx="68" cy="113" rx="9.5" ry="15" fill="#FFFFFF" />
        </g>
        <g transform="rotate(6 110 110)">
          <ellipse className="damgo-eye" cx="110" cy="110" rx="9.5" ry="15" fill="#FFFFFF" />
        </g>
      </g>
    </svg>
  );
}

function headStyle(p: Pose): CSSProperties {
  const [px, py, s, r] = p.h;
  return { transform: `translate(${px - 95}px, ${py - 97}px) rotate(${r}deg) scale(${s})` };
}

function circle(cx: number, cy: number, d: number, on: number): CSSProperties {
  return {
    width: d,
    height: d,
    transform: `translate(${cx - d / 2}px, ${cy - d / 2}px)`,
    opacity: on ? 1 : 0,
  };
}

function paw([cx, cy, rx, ry, rot, on]: Pose["p"][number]): CSSProperties {
  return {
    width: rx * 2,
    height: ry * 2,
    transform: `translate(${cx - rx}px, ${cy - ry}px) rotate(${rot}deg)`,
    opacity: on ? 1 : 0,
  };
}

/** 꼬리 + 머리 (화면 내용 뒤) */
export function DamgoBack({ pose, blink, wag }: { pose: Pose; blink?: boolean; wag?: boolean }) {
  return (
    <div
      className={`damgo${blink || pose.e[2] ? " blink" : ""}${wag ? " wag" : ""}`}
      style={{ opacity: pose.x ? 0 : 1 }}
      aria-hidden="true"
    >
      {pose.t.map(([cx, cy, d, on], i) => (
        <div key={i} className={`damgo-tail tail-${i + 1}`} style={circle(cx, cy, d, on)} />
      ))}
      <div className="damgo-head" style={headStyle(pose)}>
        <DamgoHeadSvg look={[pose.e[0], pose.e[1]]} />
      </div>
    </div>
  );
}

/** 앞발 (화면 내용 위) */
export function DamgoPaws({ pose }: { pose: Pose }) {
  return (
    <div className="damgo damgo-front" style={{ opacity: pose.x ? 0 : 1 }} aria-hidden="true">
      {pose.p.map((v, i) => (
        <div key={i} className="damgo-paw" style={paw(v)} />
      ))}
    </div>
  );
}

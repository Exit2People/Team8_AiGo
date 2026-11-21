"use client";

import type { CSSProperties, ReactNode } from "react";

export function Primary({
  y, x = 24, w = 345, children, onClick, disabled, arrow = true, label,
}: { y: number; x?: number; w?: number; children: ReactNode; onClick?: () => void; disabled?: boolean; arrow?: boolean; label?: string }) {
  return (
    <button className="btn btn-primary" style={{ left: x, top: y, width: w }} onClick={onClick} disabled={disabled} aria-label={label}>
      <span>{children}</span>
      {arrow && <span className="arrow" aria-hidden="true">→</span>}
    </button>
  );
}

export function Secondary({
  y, x = 24, w = 345, children, onClick, disabled, white, label,
}: { y: number; x?: number; w?: number; children: ReactNode; onClick?: () => void; disabled?: boolean; white?: boolean; label?: string }) {
  return (
    <button className={`btn ${white ? "btn-white" : "btn-secondary"}`} style={{ left: x, top: y, width: w }} onClick={onClick} disabled={disabled} aria-label={label}>
      {children}
    </button>
  );
}

export function Title({ y, x = 24, children, size = "s", align = "left", style }: { y: number; x?: number; children: ReactNode; size?: "s" | "m" | "l"; align?: "left" | "right" | "center"; style?: CSSProperties }) {
  const cls = size === "s" ? "t-title-s" : size === "l" ? "t-title-l" : "t-title";
  const pos: CSSProperties = align === "left" ? { left: x, right: 24 } : align === "right" ? { right: 24, left: 24, textAlign: "right" } : { left: 24, right: 24, textAlign: "center" };
  return (
    <h1 className={`abs pre ${cls}`} style={{ top: y, ...pos, ...style }} tabIndex={-1}>
      {children}
    </h1>
  );
}

export function Sub({ y, x = 24, children, align = "left", mute, style }: { y: number; x?: number; children: ReactNode; align?: "left" | "right" | "center"; mute?: boolean; style?: CSSProperties }) {
  const pos: CSSProperties = align === "left" ? { left: x, right: 24 } : align === "right" ? { right: 24, left: 24, textAlign: "right" } : { left: 24, right: 24, textAlign: "center" };
  return (
    <p className={`abs pre t-sub ${mute ? "c-mute" : "c-sub"}`} style={{ top: y, ...pos, ...style }}>
      {children}
    </p>
  );
}

export function Caption({ y, children, onClick, dark }: { y: number; children: ReactNode; onClick?: () => void; dark?: boolean }) {
  const cls = `abs center-x t-caption pre ${dark ? "c-mute" : "c-sub"}`;
  if (onClick)
    return (
      <button className={cls} style={{ top: y - 8, left: 100, right: 100, height: 34, textDecoration: "underline", textUnderlineOffset: 3 }} onClick={onClick}>
        {children}
      </button>
    );
  return (
    <p className={cls} style={{ top: y }}>
      {children}
    </p>
  );
}

/** 진행 막대 (4칸) + 글 */
/** 진행 표시. bar={false}면 막대 없이 글자("질문 1")만 보여요 (AI가 고른 질문은 몇 개일지 정해져 있지 않아서) */
export function Progress({ on, text, right, bar: showBar = true }: { on: number; text: string; right?: boolean; bar?: boolean }) {
  const bar = showBar && (
    <span className="progress-bar" aria-hidden="true">
      {[1, 2, 3, 4].map((i) => (
        <i key={i} className={i <= on ? "on" : ""} />
      ))}
    </span>
  );
  return (
    <div className="progress" style={right ? { right: 24, flexDirection: "row-reverse" } : { left: 24 }} aria-label={`진행 ${text}`}>
      {bar}
      <span className="t-count">{text}</span>
    </div>
  );
}

export function Sheet({ y }: { y: number }) {
  return <div className="sheet" style={{ top: y }} />;
}

export function Dots({ y }: { y: number }) {
  return (
    <div className="dots" style={{ top: y }} aria-hidden="true">
      <i />
      <i />
      <i />
    </div>
  );
}

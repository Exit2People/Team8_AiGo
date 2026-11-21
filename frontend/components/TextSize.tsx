"use client";

import { useEffect, useState } from "react";
import { TEXT_SIZES, useTextSize } from "@/lib/textSize";

export const OPEN_TEXT_SIZE = "aigo:textsize-open";

/** 글씨 크기 표시: 작은 '가' + 큰 '가'. 글자가 커진다는 뜻이 한눈에 보이게(설정과 상관없이 늘 같은 크기) */
export function TextSizeIcon({ color = "currentColor" }: { color?: string }) {
  return (
    <span aria-hidden="true" style={{ display: "inline-flex", alignItems: "flex-end", gap: 1, color, fontWeight: 900, lineHeight: 1, letterSpacing: "-0.04em" }}>
      <span style={{ fontSize: 11 }}>가</span>
      <span style={{ fontSize: 17 }}>가</span>
    </span>
  );
}

/** 글씨 크기 판을 여는 버튼 (첫 화면 · 톡방). '[작은가 큰가] 글씨 크기' */
export function TextSizeButton({ light }: { light?: boolean }) {
  return (
    <button
      className="chip chip-top"
      onClick={() => window.dispatchEvent(new CustomEvent(OPEN_TEXT_SIZE))}
      aria-label="글씨 크기 바꾸기"
      style={light ? { background: "var(--white)", color: "var(--ink)", boxShadow: "var(--sh-row)" } : undefined}
    >
      <TextSizeIcon />
      글씨 크기
    </button>
  );
}

/** 글씨 크기 고르기: 큰 버튼 3개. 누르면 바로 화면 전체가 바뀌어요 */
export function TextSizePicker() {
  const [cur, set] = useTextSize();
  return (
    <div role="radiogroup" aria-label="글씨 크기" style={{ display: "flex", gap: 8 }}>
      {TEXT_SIZES.map((t) => {
        const on = t.id === cur;
        return (
          <button
            key={t.id}
            role="radio"
            aria-checked={on}
            onClick={() => set(t.id)}
            style={{
              flex: 1,
              minHeight: 76,
              borderRadius: 18,
              background: on ? "var(--ink)" : "var(--soft)",
              color: on ? "#fff" : "var(--ink)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
              boxShadow: on ? "0 0 0 3px var(--coral)" : "none",
            }}
          >
            {/* 미리 보기 '가'는 고르기 전에도 크기 차이가 보이게 배율을 직접 곱해요 */}
            <span aria-hidden="true" style={{ fontSize: 24 * t.scale, fontWeight: 900, lineHeight: 1 }}>
              가
            </span>
            <span style={{ fontSize: 15, fontWeight: 800 }}>{t.name}</span>
          </button>
        );
      })}
    </div>
  );
}

/** 어디서든 여는 글씨 크기 판 (첫 화면 위 '가 글씨 크기' 버튼) */
export function TextSizeSheet() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = () => setOpen(true);
    window.addEventListener(OPEN_TEXT_SIZE, on);
    return () => window.removeEventListener(OPEN_TEXT_SIZE, on);
  }, []);
  if (!open) return null;
  return (
    <div className="modal-bg" style={{ zIndex: 96 }} onClick={() => setOpen(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="tsTitle">
        <h2 id="tsTitle" className="t-tile">
          글씨 크기
        </h2>
        <p className="t-sub c-mute" style={{ marginTop: 6, marginBottom: 16 }}>
          누르면 바로 바뀌어요 · 마이메뉴에서도 바꿀 수 있어요
        </p>
        <TextSizePicker />
        <button className="btn btn-primary" style={{ justifyContent: "center", marginTop: 18 }} onClick={() => setOpen(false)}>
          다 됐어요
        </button>
      </div>
    </div>
  );
}

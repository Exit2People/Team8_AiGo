/**
 * 글씨 크기 (내 정보 · 첫 화면 · 톡방에서 바꿔요). 이 기기에만 저장해요.
 * 화면의 글씨는 모두 `calc(Npx * var(--fs))`로 그려서, 여기서 --fs 하나만 바꾸면 전체가 같이 커지고 작아져요.
 * 제목은 --fs-t(배율의 절반만 커져요), 아주 큰 제목(40px 이상)은 바꾸지 않아요(globals.css).
 */
import { useEffect, useState } from "react";
import { load, save } from "./device";

export type TextSize = "normal" | "large" | "xlarge";

/** 지금 화면 크기가 '크게'(기준)예요 */
export const TEXT_SIZES: { id: TextSize; name: string; scale: number }[] = [
  { id: "normal", name: "보통", scale: 0.9 },
  { id: "large", name: "크게", scale: 1 },
  { id: "xlarge", name: "아주 크게", scale: 1.15 },
];

const KEY = "aigo.textSize";
const EVENT = "aigo:textsize";

export function readTextSize(): TextSize {
  const v = load<TextSize>(KEY, "large");
  return TEXT_SIZES.some((t) => t.id === v) ? v : "large";
}

/** 화면에 적용 (--fs를 문서 맨 위에 둬서 모든 화면이 물려받아요) */
export function applyTextSize(id: TextSize) {
  const t = TEXT_SIZES.find((x) => x.id === id) ?? TEXT_SIZES[1];
  document.documentElement.style.setProperty("--fs", String(t.scale));
}

export function setTextSize(id: TextSize) {
  save(KEY, id);
  applyTextSize(id);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: id }));
}

/** 지금 글씨 크기 (다른 화면에서 바꿔도 따라와요) */
export function useTextSize(): [TextSize, (id: TextSize) => void] {
  const [v, setV] = useState<TextSize>(() => (typeof window === "undefined" ? "large" : readTextSize()));
  useEffect(() => {
    const on = (e: Event) => setV((e as CustomEvent<TextSize>).detail);
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, []);
  return [v, setTextSize];
}

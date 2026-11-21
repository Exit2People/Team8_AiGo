"use client";

import { useEffect, useState, type CSSProperties } from "react";

/** 가방 담기 (11_FRONTEND_SPEC 8.1, 4-animation 4-3) — grow 0.6 · 카드당 0.18 · close 0.55 · snap 0.5 · morph 0.7 */
export type PackPhase = "grow" | "pack" | "close" | "snap" | "morph";

type Row = { name: string; value: string };

const BG = ["#FFFFFF", "#F4F2EF", "#EDE9E2", "#DEDEDE"];
const PRINTER = "linear-gradient(to bottom, #3a3a3a 0%, #141414 40%, #0b0b0b 100%)";

export default function Pack({ rows, onPose, onDone }: { rows: Row[]; onPose: (k: string | null) => void; onDone: () => void }) {
  const [phase, setPhase] = useState<PackPhase | "start">("start");
  const [inN, setInN] = useState(0);
  const cards = rows.slice(0, 6);

  useEffect(() => {
    const ts: ReturnType<typeof setTimeout>[] = [];
    const at = (ms: number, fn: () => void) => ts.push(setTimeout(fn, ms));
    let t = 30;
    at(t, () => {
      setPhase("grow");
      onPose("pack1");
    });
    t += 600 + 200;
    at(t, () => {
      setPhase("pack");
      onPose("pack2");
    });
    cards.forEach((_, i) => at(t + 120 + i * 180, () => setInN(i + 1)));
    t += 120 + cards.length * 180 + 300;
    at(t, () => {
      setPhase("close");
      onPose("pack3");
    });
    t += 550;
    at(t, () => setPhase("snap"));
    t += 500;
    at(t, () => {
      setPhase("morph");
      onPose("morph");
    });
    t += 700;
    at(t, onDone);
    return () => {
      ts.forEach(clearTimeout);
      onPose(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const morph = phase === "morph";
  const up = phase !== "start";
  const bagTop = up ? 410 : 900;
  const back: CSSProperties = morph
    ? { left: 24, top: 672, width: 345, height: 84, borderRadius: 22 }
    : { left: 61.5, top: bagTop, width: 270, height: 320, borderRadius: "38px 38px 50px 50px" };
  const ease = "cubic-bezier(.42,0,.58,1)";

  return (
    <div className="abs" style={{ inset: 0, zIndex: 20, pointerEvents: "none" }} aria-hidden="true">
      <div
        style={{
          position: "absolute",
          background: PRINTER,
          boxShadow: "var(--sh-printer)",
          transition: `all ${morph ? 0.7 : 0.6}s ${ease}`,
          ...back,
        }}
      >
        <div style={{ position: "absolute", inset: 9, height: 70, border: "2px dashed #DEDEDE", borderBottom: 0, borderRadius: "30px 30px 0 0", opacity: morph ? 0 : 0.6, transition: "opacity .3s" }} />
      </div>
      {cards.map((r, i) => {
        const inBag = i < inN;
        const fromY = 262 + i * 54;
        const style: CSSProperties =
          phase === "start"
            ? { top: fromY, left: 24, width: 345, transform: "none" }
            : inBag
              ? { top: 470, left: 80.5, width: 232, transform: `rotate(0deg) scale(.9)`, opacity: 0 }
              : { top: 232 + i * 50, left: 80.5, width: 232, transform: `rotate(${[-2, 1.5, -1, 2, -1.5, 1][i]}deg)` };
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              height: 64,
              borderRadius: 12,
              background: BG[i % 4],
              boxShadow: "var(--sh-row)",
              padding: "6px 14px",
              transition: `all ${inBag ? 0.5 : 0.6}s ${inBag ? "cubic-bezier(.22,1,.36,1)" : ease}`,
              ...style,
            }}
          >
            <span className="t-label c-deep">{String(i + 1).padStart(2, "0")}</span>{" "}
            <span className="t-item c-mute">{r.name}</span>
            <p className="t-answer" style={{ marginTop: 6, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {r.value}
            </p>
          </div>
        );
      })}
      {/* 주머니 (카드 앞) */}
      <div
        style={{
          position: "absolute",
          left: 61.5,
          top: bagTop + 90,
          width: 270,
          height: 230,
          background: PRINTER,
          borderRadius: "16px 16px 50px 50px",
          transition: `all .6s ${ease}, opacity .3s`,
          opacity: morph ? 0 : 1,
          transform: phase === "pack" && inN > 0 ? `scale(${1 + 0.02 * (inN % 2)})` : "none",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "rgba(222,222,222,.5)",
        }}
      >
        <div style={{ position: "absolute", inset: 10, border: "2px dashed rgba(222,222,222,.6)", borderRadius: "10px 10px 42px 42px" }} />
        <span className="t-answer">담고의 가방</span>
        <span className="t-item" style={{ marginTop: 8, opacity: 0.8 }}>
          오늘의 선택
        </span>
      </div>
      {/* 똑딱이 */}
      <div
        style={{
          position: "absolute",
          left: morph ? 333 : 166.5,
          top: morph ? 702 : bagTop + 80,
          width: 60,
          height: 72,
          transformOrigin: "0 0",
          transform: morph ? "scale(.14)" : phase === "snap" ? "translateY(4px)" : "none",
          transition: `all ${morph ? 0.7 : 0.4}s ${ease}`,
        }}
      >
        <div style={{ position: "absolute", left: 4, top: 7, width: 52, height: 60, background: "var(--amber)", borderRadius: "9px 9px 26px 26px", boxShadow: "0 4px 8px rgba(89,20,15,.3)" }} />
        <div style={{ position: "absolute", left: 17, top: 26, width: 26, height: 26, borderRadius: 13, background: "radial-gradient(circle at 40% 35%, #fff, #bbb 60%, #888)", transform: phase === "snap" ? "scale(.85)" : "none", transition: "transform .2s" }} />
      </div>
      {phase === "snap" && (
        <span className="t-label" style={{ position: "absolute", left: 236, top: bagTop + 70, color: "var(--ink)" }}>
          딸깍
        </span>
      )}
    </div>
  );
}
